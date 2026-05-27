# -*- coding: utf-8 -*-
"""
因子 IC (Information Coefficient) 分析

计算每个因子与下期收益率的截面相关系数 (Pearson IC)。
"""

import pandas as pd
import numpy as np
import logging
from typing import Dict

logger = logging.getLogger(__name__)


def compute_factor_ic(
    factors_snapshot: pd.DataFrame,
    returns_snapshot: pd.Series,
    min_samples: int = 10,
) -> Dict[str, float]:
    """
    计算因子 IC (Information Coefficient)。

    IC = corr(factor_value, next_period_return) 截面 Pearson 相关系数。

    Args:
        factors_snapshot: 截面因子数据, index=ts_code, columns=factor_ids
        returns_snapshot: 下期收益率, index=ts_code
        min_samples: 最少有效样本数，低于此值不计算 IC

    Returns:
        dict of factor_id -> IC value (float, range [-1, 1])
    """
    ic_scores: Dict[str, float] = {}
    valid_returns = returns_snapshot.dropna()

    if valid_returns.empty:
        logger.warning("No valid returns for IC computation")
        return ic_scores

    for col in factors_snapshot.columns:
        factor_values = factors_snapshot[col].dropna()
        common_index = factor_values.index.intersection(valid_returns.index)

        if len(common_index) < min_samples:
            continue

        correlation = factor_values.loc[common_index].corr(
            valid_returns.loc[common_index]
        )
        ic_scores[col] = float(correlation) if not pd.isna(correlation) else 0.0

    logger.info(f"Computed IC for {len(ic_scores)} factors")
    return ic_scores


def compute_ic_series(
    get_factors_fn,
    get_returns_fn,
    rebalance_dates: list,
    min_samples: int = 10,
) -> Dict[str, list]:
    """
    计算因子 IC 时间序列。

    对每个调仓点计算截面 IC，汇总为时间序列。

    Args:
        get_factors_fn: callable(date) -> DataFrame(index=ts_code, cols=factor_ids)
        get_returns_fn: callable(date) -> Series(index=ts_code) 下期收益率
        rebalance_dates: 调仓日期列表 (date objects)
        min_samples: 最少有效样本数

    Returns:
        dict of factor_id -> list of (date_iso, IC) tuples
    """
    from collections import defaultdict

    ic_history: Dict[str, list] = defaultdict(list)

    for rdate in rebalance_dates:
        factors = get_factors_fn(rdate)
        returns = get_returns_fn(rdate)

        if factors is None or factors.empty:
            continue
        if returns is None or returns.empty:
            continue

        ic_scores = compute_factor_ic(factors, returns, min_samples=min_samples)
        date_iso = rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate)

        for factor_id, ic_val in ic_scores.items():
            ic_history[factor_id].append((date_iso, ic_val))

    # Convert defaultdict to dict
    result = {k: v for k, v in ic_history.items()}

    logger.info(
        f"IC series computed: {len(result)} factors, "
        f"{len(rebalance_dates)} periods"
    )
    return result


def summarize_ic(ic_series: Dict[str, list]) -> Dict[str, dict]:
    """
    汇总 IC 时间序列统计量。

    Args:
        ic_series: dict of factor_id -> list of (date_iso, IC) tuples

    Returns:
        dict of factor_id -> {mean_ic, std_ic, icir, positive_rate}
    """
    summary: Dict[str, dict] = {}

    for factor_id, series in ic_series.items():
        if not series:
            continue

        ic_values = np.array([v for _, v in series])
        mean_ic = float(np.mean(ic_values))
        std_ic = float(np.std(ic_values, ddof=1)) if len(ic_values) > 1 else 0.0

        # ICIR = mean(IC) / std(IC)
        icir = float(mean_ic / std_ic) if std_ic > 0 else 0.0

        # IC > 0 的比例
        positive_rate = float(np.sum(ic_values > 0) / len(ic_values))

        summary[factor_id] = {
            "mean_ic": round(mean_ic, 4),
            "std_ic": round(std_ic, 4),
            "icir": round(icir, 3),
            "positive_rate": round(positive_rate, 3),
            "periods": len(ic_values),
        }

    return summary
