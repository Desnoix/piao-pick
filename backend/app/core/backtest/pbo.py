"""
PBO (Probability of Backtest Overfitting)

基于 Bailey & de Prado (2014) "The deflated Sharpe ratio: correcting for
selection bias, backtest overfitting and non-normality" 的实现。

核心思想:
  将回测区间分成 S 个子区间，取 S/2 个作为"训练集"组合。
  对每种组合，在其上找到最优参数 θ*，然后在剩余的"测试集"上评估。
  PBO = P(θ* 在测试集上的表现低于中位数)
"""

import calendar
import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from itertools import combinations

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PBOConfig:
    """PBO 计算配置"""

    n_sub_periods: int = 16  # 子区间数量 S (必须为偶数)
    risk_free_rate: float = 0.03


@dataclass
class PBOResult:
    """PBO 计算结果"""

    pbo: float  # 过拟合概率, 范围 [0, 1]
    is_sharpe_mean: float  # 训练集 Sharpe 均值
    oos_sharpe_mean: float  # 测试集 Sharpe 均值
    oos_sharpe_std: float  # 测试集 Sharpe 标准差
    n_combinations: int  # 组合总数
    lambda_star_mean: float  # 最优参数在 IS 的平均 Sharpe
    pbo_interpretation: str  # 文字说明


class PBOCalculator:
    """PBO 过拟合概率计算器"""

    def __init__(self, config: PBOConfig | None = None):
        self.config = config or PBOConfig()

    def compute(
        self,
        strategy_name: str,
        overall_start: date,
        overall_end: date,
        run_backtest_fn: Callable[[str, str, str], dict],
        parameter_variants: list[dict] | None = None,
    ) -> PBOResult:
        """
        计算 PBO。

        Args:
            strategy_name: 策略名称
            overall_start: 数据总起始日期
            overall_end: 数据总截止日期
            run_backtest_fn: callable(strategy_name, start_date, end_date) -> dict
            parameter_variants: 参数变体列表（可选）。
                若提供，对每个变体运行回测，选 IS 最优的变体评估 OOS。
                若不提供，只用默认参数。

        Returns:
            PBOResult
        """
        S = self.config.n_sub_periods
        if S % 2 != 0:
            raise ValueError(f"n_sub_periods must be even, got {S}")

        # 将总区间等分为 S 个子区间
        total_months = (overall_end.year - overall_start.year) * 12 + (overall_end.month - overall_start.month)

        if total_months < S:
            raise ValueError(f"Total months ({total_months}) < n_sub_periods ({S}). Need at least {S} months of data.")

        sub_months = total_months // S
        sub_boundaries: list[date] = []
        for i in range(S + 1):
            sub_boundaries.append(_add_months(overall_start, sub_months * i))

        # 子区间列表: [(start, end), ...]
        sub_periods: list[tuple[date, date]] = [(sub_boundaries[i], sub_boundaries[i + 1]) for i in range(S)]

        # 枚举所有 C(S, S/2) 种训练集组合
        half = S // 2
        all_combos = list(combinations(range(S), half))

        logger.info(
            f"PBO: S={S}, C({S},{half})={len(all_combos)} combinations, "
            f"{len(parameter_variants or [None])} parameter variants"
        )

        # 预计算每个子区间、每个参数变体的 Sharpe
        # sharpes[variant_idx][sub_period_idx] = sharpe
        n_variants = len(parameter_variants) if parameter_variants else 1
        sub_sharpes = np.zeros((n_variants, S))

        for sub_idx, (sp_start, sp_end) in enumerate(sub_periods):
            for var_idx in range(n_variants):
                result = run_backtest_fn(
                    strategy_name,
                    sp_start.isoformat(),
                    sp_end.isoformat(),
                )
                sharpe = result.get("metrics", {}).get("sharpe_ratio", 0.0)
                sub_sharpes[var_idx, sub_idx] = sharpe

        # 对每种组合，找到 IS 最优的参数变体，评估其 OOS Sharpe
        oos_sharpes: list[float] = []
        is_sharpes_optimal: list[float] = []

        for combo in all_combos:
            train_indices = set(combo)
            test_indices = [i for i in range(S) if i not in train_indices]

            # 对每个参数变体，计算 IS Sharpe（训练子区间的均值）
            best_variant_idx = 0
            best_is_sharpe = -np.inf

            for var_idx in range(n_variants):
                is_values = [sub_sharpes[var_idx, i] for i in train_indices]
                is_mean = float(np.mean(is_values))
                if is_mean > best_is_sharpe:
                    best_is_sharpe = is_mean
                    best_variant_idx = var_idx

            # 用最优变体在 OOS 上评估
            oos_values = [sub_sharpes[best_variant_idx, i] for i in test_indices]
            oos_mean = float(np.mean(oos_values))

            oos_sharpes.append(oos_mean)
            is_sharpes_optimal.append(best_is_sharpe)

        # 计算 PBO
        # PBO = P(OOS Sharpe of θ* < median of all OOS Sharpes)
        oos_arr = np.array(oos_sharpes)
        oos_median = float(np.median(oos_arr))

        # 用经验累积分布函数
        # 对每个组合的 OOS Sharpe，检查它是否低于中位数
        pbo = float(np.mean(oos_arr < oos_median))

        # 解释
        if pbo >= 0.9:
            interp = "严重过拟合: 策略在样本外系统性失败"
        elif pbo >= 0.5:
            interp = "存在过拟合风险: 建议调整参数或使用更简单的模型"
        elif pbo >= 0.1:
            interp = "过拟合风险可控: 策略表现出一定的样本外稳健性"
        else:
            interp = "低过拟合风险: 策略在样本外表现稳定"

        return PBOResult(
            pbo=round(pbo, 4),
            is_sharpe_mean=round(float(np.mean(is_sharpes_optimal)), 3),
            oos_sharpe_mean=round(float(np.mean(oos_arr)), 3),
            oos_sharpe_std=round(float(np.std(oos_arr)), 3),
            n_combinations=len(all_combos),
            lambda_star_mean=round(float(np.mean(is_sharpes_optimal)), 3),
            pbo_interpretation=interp,
        )


def _add_months(d: date, months: int) -> date:
    """日期加减月份"""
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)
