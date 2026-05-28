"""
因子动态赋权计算器

支持三种赋权方法:
- fixed: YAML 固定权重
- icir: 基于滚动 ICIR 的动态权重
- equal: 等权重

核心公式 (ICIR 赋权):
  raw_weight_i = max(ICIR_i, 0)    # 仅保留 ICIR > 0 的因子
  weight_i = raw_weight_i / sum(raw_weight)
  weight_i = min(weight_i, max_single_weight)  # 截断
  weight_i = weight_i / sum(weight)  # 再归一化
"""

import logging

logger = logging.getLogger(__name__)


def compute_dynamic_weights(
    factor_ids: list[str],
    icir_snapshot: dict[str, float] | None,
    fallback_weights: dict[str, float],
    method: str = "fixed",
    max_single_weight: float = 0.40,
) -> dict[str, float]:
    """
    计算因子权重。

    Args:
        factor_ids: 当前可用因子 ID 列表
        icir_snapshot: 各因子 ICIR 值 (仅 method='icir' 时使用)
        fallback_weights: YAML 中定义的固定权重 (method='fixed' 或兜底时用)
        method: 'fixed' | 'icir' | 'equal'
        max_single_weight: 单因子最大权重上限

    Returns:
        dict of factor_id -> weight (float, 总和 = 1.0)
    """
    if not factor_ids:
        return {}

    if method == "equal":
        return _equal_weights(factor_ids)

    if method == "icir":
        if icir_snapshot is None:
            logger.warning("ICIR snapshot not available, falling back to fixed weights")
            return _apply_fixed_weights(factor_ids, fallback_weights, max_single_weight)
        return _icir_weights(factor_ids, icir_snapshot, fallback_weights, max_single_weight)

    # method == "fixed" (default)
    return _apply_fixed_weights(factor_ids, fallback_weights, max_single_weight)


def _equal_weights(factor_ids: list[str]) -> dict[str, float]:
    """等权分配"""
    n = len(factor_ids)
    w = 1.0 / n if n > 0 else 0.0
    return {fid: w for fid in factor_ids}


def _apply_fixed_weights(
    factor_ids: list[str],
    fallback_weights: dict[str, float],
    max_single_weight: float,
) -> dict[str, float]:
    """
    固定权重 + 截断 + 归一化。
    """
    raw = {}
    for fid in factor_ids:
        raw[fid] = fallback_weights.get(fid, 0.0)

    total = sum(raw.values())
    if total <= 0:
        return _equal_weights(factor_ids)

    # 归一化
    weights = {fid: w / total for fid, w in raw.items()}

    # 截断 + 再归一化
    weights = _cap_and_renormalize(weights, max_single_weight)
    return weights


def _icir_weights(
    factor_ids: list[str],
    icir_snapshot: dict[str, float],
    fallback_weights: dict[str, float],
    max_single_weight: float,
) -> dict[str, float]:
    """
    ICIR 动态赋权:
    1. 取 ICIR > 0 的因子
    2. 按 ICIR 值归一化
    3. 截断到 max_single_weight 后重新归一化

    若所有因子 ICIR <= 0, 降级到 equal 权重。
    """
    # 仅取 ICIR > 0 的因子
    positive = {}
    for fid in factor_ids:
        icir_val = icir_snapshot.get(fid, 0.0)
        if icir_val > 0:
            positive[fid] = icir_val

    if not positive:
        logger.info("All ICIR <= 0, falling back to equal weights")
        return _equal_weights(factor_ids)

    total = sum(positive.values())
    weights = {fid: v / total for fid, v in positive.items()}

    # 对 ICIR <= 0 的因子赋权 0 (不参与合成)
    for fid in factor_ids:
        if fid not in weights:
            weights[fid] = 0.0

    # 截断 + 再归一化
    weights = _cap_and_renormalize(weights, max_single_weight)
    return weights


def _cap_and_renormalize(
    weights: dict[str, float],
    cap: float,
) -> dict[str, float]:
    """
    截断超限权重并重新归一化 (water-filling 算法)。

    核心思路: 超限权重固定在 cap, 剩余权重 (1 - sum_capped) 按原比例分配给未超限因子。
    迭代至所有未锁定权重都不超过 cap。

    Args:
        weights: 原始权重 dict (已归一化, 总和 = 1.0)
        cap: 单因子最大权重上限

    Returns:
        截断后的权重 dict, 总和 = 1.0
    """
    weights = dict(weights)

    # 分离: 超限 (将锁定在 cap) 和 未超限 (待分配)
    locked: dict[str, float] = {}
    free: dict[str, float] = {}
    for k, v in weights.items():
        if v > cap:
            locked[k] = cap
        else:
            free[k] = v

    # 迭代分配: 将剩余权重按原比例分给 free 因子, 若有超限则移入 locked
    for _ in range(10):
        locked_sum = sum(locked.values())
        remaining = 1.0 - locked_sum
        free_sum = sum(free.values())

        if free_sum <= 0 or remaining <= 0:
            break

        # 按 free 中的原始比例分配 remaining
        overflow = False
        for k in free:
            free[k] = free[k] / free_sum * remaining
            if free[k] > cap:
                overflow = True

        if not overflow:
            break

        # 将超限的移入 locked
        newly_locked = {k: v for k, v in free.items() if v > cap}
        for k in newly_locked:
            locked[k] = cap
            del free[k]

    # 合并结果
    result = {**locked, **free}
    # 零权重因子保持 0
    for k in weights:
        if k not in result:
            result[k] = 0.0

    return result
