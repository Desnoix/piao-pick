"""
因子 IC (Information Coefficient) 分析

计算每个因子与下期收益率的截面相关系数。
支持 Spearman Rank IC (默认, 对离群点稳健) 和 Pearson IC (备选)。
"""

import logging
from typing import Literal

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

logger = logging.getLogger(__name__)


def compute_factor_ic(
    factors_snapshot: pd.DataFrame,
    returns_snapshot: pd.Series,
    min_samples: int = 30,
    method: Literal["spearman", "pearson"] = "spearman",
) -> dict[str, float]:
    """
    计算因子 IC (Information Coefficient)。

    支持两种方法:
    - spearman (默认): Spearman 秩相关 (Rank IC)，对离群点稳健
    - pearson: Pearson 线性相关系数，对极端值敏感

    Args:
        factors_snapshot: 截面因子数据, index=ts_code, columns=factor_ids
        returns_snapshot: 下期收益率, index=ts_code
        min_samples: 最少有效样本数，低于此值不计算 IC (默认 30)
        method: 相关系数方法, "spearman" 或 "pearson"

    Returns:
        dict of factor_id -> IC value (float, range [-1, 1])
    """
    ic_scores: dict[str, float] = {}
    valid_returns = returns_snapshot.dropna()

    if valid_returns.empty:
        logger.warning("No valid returns for IC computation")
        return ic_scores

    for col in factors_snapshot.columns:
        factor_values = factors_snapshot[col].dropna()
        common_index = factor_values.index.intersection(valid_returns.index)

        if len(common_index) < min_samples:
            continue

        if method == "spearman":
            corr, _ = spearmanr(
                factor_values.loc[common_index].values,
                valid_returns.loc[common_index].values,
            )
        else:
            corr = factor_values.loc[common_index].corr(valid_returns.loc[common_index])

        ic_scores[col] = float(corr) if not pd.isna(corr) else 0.0

    logger.info(f"Computed {method} IC for {len(ic_scores)} factors")
    return ic_scores


def compute_ic_series(
    get_factors_fn,
    get_returns_fn,
    rebalance_dates: list,
    min_samples: int = 30,
    method: Literal["spearman", "pearson"] = "spearman",
) -> dict[str, list]:
    """
    计算因子 IC 时间序列。

    对每个调仓点计算截面 IC，汇总为时间序列。

    Args:
        get_factors_fn: callable(date) -> DataFrame(index=ts_code, cols=factor_ids)
        get_returns_fn: callable(date) -> Series(index=ts_code) 下期收益率
        rebalance_dates: 调仓日期列表 (date objects)
        min_samples: 最少有效样本数 (默认 30)
        method: 相关系数方法, "spearman" 或 "pearson"

    Returns:
        dict of factor_id -> list of (date_iso, IC) tuples
    """
    from collections import defaultdict

    ic_history: dict[str, list] = defaultdict(list)

    for rdate in rebalance_dates:
        factors = get_factors_fn(rdate)
        returns = get_returns_fn(rdate)

        if factors is None or factors.empty:
            continue
        if returns is None or returns.empty:
            continue

        ic_scores = compute_factor_ic(factors, returns, min_samples=min_samples, method=method)
        date_iso = rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate)

        for factor_id, ic_val in ic_scores.items():
            ic_history[factor_id].append((date_iso, ic_val))

    # Convert defaultdict to dict
    result = {k: v for k, v in ic_history.items()}

    logger.info(f"IC series ({method}) computed: {len(result)} factors, {len(rebalance_dates)} periods")
    return result


def _assess_ic_quality(
    mean_ic: float,
    icir: float,
    positive_rate: float,
    t_stat: float,
) -> str:
    """
    根据 IC 均值、ICIR、胜率、t 统计量给出综合质量评级。

    评级规则 (从严格到宽松):
    - excellent: 所有指标达到"优秀"
    - good: mean_ic >= 0.05 且 icir >= 0.5
    - pass: mean_ic >= 0.03 且 icir >= 0.3
    - weak: 未达 pass 标准

    Args:
        mean_ic: IC 均值 (取绝对值)
        icir: 信息比率
        positive_rate: IC > 0 占比
        t_stat: 均值 t 检验统计量

    Returns:
        质量标签: "excellent", "good", "pass", "weak"
    """
    abs_mean = abs(mean_ic)

    if abs_mean >= 0.08 and icir >= 0.75 and positive_rate >= 0.60:
        return "excellent"
    if abs_mean >= 0.05 and icir >= 0.50 and positive_rate >= 0.55:
        return "good"
    if abs_mean >= 0.03 and icir >= 0.30 and positive_rate >= 0.50:
        return "pass"
    return "weak"


def summarize_ic(ic_series: dict[str, list]) -> dict[str, dict]:
    """
    汇总 IC 时间序列统计量。

    计算 IC 均值、标准差、ICIR、胜率、t 统计量和质量评级。

    Args:
        ic_series: dict of factor_id -> list of (date_iso, IC) tuples

    Returns:
        dict of factor_id -> {
            mean_ic, std_ic, icir, positive_rate, periods,
            t_statistic, p_value, is_significant, quality
        }
    """
    summary: dict[str, dict] = {}

    for factor_id, series in ic_series.items():
        if not series:
            continue

        ic_values = np.array([v for _, v in series])
        n = len(ic_values)
        mean_ic = float(np.mean(ic_values))
        std_ic = float(np.std(ic_values, ddof=1)) if n > 1 else 0.0

        # ICIR = mean(IC) / std(IC)
        icir = float(mean_ic / std_ic) if std_ic > 0 else 0.0

        # IC > 0 的比例
        positive_rate = float(np.sum(ic_values > 0) / n)

        # t 检验: H0: mean(IC) = 0
        # t = mean / (std / sqrt(n)), df = n - 1
        if std_ic > 0 and n > 1:
            se = std_ic / np.sqrt(n)
            t_stat = float(mean_ic / se)
            # 双侧 p-value，使用 scipy t 分布
            from scipy.stats import t as t_dist

            df = n - 1
            p_value = float(2.0 * (1.0 - t_dist.cdf(abs(t_stat), df)))
        else:
            t_stat = 0.0
            p_value = 1.0

        # 显著性判定: p < 0.05 且 |t| >= 3 (Harvey, Liu, Zhu 2016 多重检验门槛)
        is_significant = p_value < 0.05 and abs(t_stat) >= 3.0

        # 质量评级
        quality = _assess_ic_quality(mean_ic, icir, positive_rate, t_stat)

        summary[factor_id] = {
            "mean_ic": round(mean_ic, 4),
            "std_ic": round(std_ic, 4),
            "icir": round(icir, 3),
            "positive_rate": round(positive_rate, 3),
            "periods": n,
            "t_statistic": round(t_stat, 3),
            "p_value": round(p_value, 6),
            "is_significant": is_significant,
            "quality": quality,
        }

    return summary


def rolling_icir(
    ic_series: dict[str, list],
    lookback: int = 12,
    min_periods: int = 6,
) -> dict[str, dict[str, float]]:
    """
    计算滚动 ICIR (滚动窗口内 IC 均值 / IC 标准差)。

    对每个因子, 用最近 lookback 期的 IC 值计算 ICIR。
    返回每个日期截面上各因子的 ICIR 值。

    ICIR 公式: rolling_mean(IC) / rolling_std(IC)
    仅取 IC > 0 的因子权重; 全负时由调用方负责降级。

    Args:
        ic_series: dict of factor_id -> list of (date_iso, IC) tuples,
                   每个因子的 IC 时间序列 (按日期升序)
        lookback: 滚动窗口期数 (月度调仓下即为月数)
        min_periods: 最少有效 IC 期数, 低于此则 ICIR 为 0

    Returns:
        dict of date_iso -> {factor_id -> icir_value}
    """
    result: dict[str, dict[str, float]] = {}

    # 收集所有日期 (去重排序)
    all_dates: list[str] = []
    date_set: set[str] = set()
    for series in ic_series.values():
        for date_iso, _ in series:
            if date_iso not in date_set:
                all_dates.append(date_iso)
                date_set.add(date_iso)
    all_dates.sort()

    for target_date in all_dates:
        date_icir: dict[str, float] = {}

        for factor_id, series in ic_series.items():
            # 取 target_date 及之前的所有 IC 值
            ic_values = [ic_val for (d, ic_val) in series if d <= target_date]

            if len(ic_values) < min_periods:
                date_icir[factor_id] = 0.0
                continue

            # 取最近 lookback 期
            window = ic_values[-lookback:]
            mean_ic = float(np.mean(window))
            std_ic = float(np.std(window, ddof=1)) if len(window) > 1 else 0.0

            if std_ic > 0:
                date_icir[factor_id] = float(mean_ic / std_ic)
            else:
                # 标准差为 0 说明 IC 完全不变, 若均值为正给一个小的 ICIR
                date_icir[factor_id] = 1.0 if mean_ic > 0 else 0.0

        result[target_date] = date_icir

    return result
