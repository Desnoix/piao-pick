# -*- coding: utf-8 -*-
"""
回测风险指标计算

支持指标：
- 总收益率 / 年化收益率
- 年化波动率
- 夏普比率 (Sharpe Ratio)
- 最大回撤 (Max Drawdown)
- Calmar 比率
- 月度胜率
"""

import numpy as np
from typing import List, Tuple, Optional


def compute_metrics(
    nav: List[Tuple[str, float]],
    portfolio_returns: List[float],
    benchmark_nav: Optional[List[Tuple[str, float]]] = None,
    risk_free_rate: float = 0.03,
    trading_days_per_year: float = 252,
) -> dict:
    """
    计算回测风险指标。

    Args:
        nav: 净值序列 [(date_iso, value), ...]
        portfolio_returns: 区间收益率序列 (月度)
        benchmark_nav: 基准净值序列 (可选, 未使用)
        risk_free_rate: 无风险利率 (年化, 默认 3%)
        trading_days_per_year: 年交易日 (默认 252, 月度调仓用 12 换算)

    Returns:
        dict of metric_name -> value
    """
    nav_values = np.array([v for _, v in nav], dtype=float)
    returns = np.array(portfolio_returns, dtype=float)

    n_periods = len(returns)
    if n_periods < 2:
        return _empty_metrics()

    # 总收益率
    total_return = float(nav_values[-1] / nav_values[0] - 1.0)

    # 年化收益率 (月度 period → 年化)
    years = n_periods / 12.0
    if years > 0 and total_return > -1.0:
        annual_return = float((1.0 + total_return) ** (1.0 / years) - 1.0)
    else:
        annual_return = total_return

    # 年化波动率 (月度标准差 × sqrt(12))
    annual_vol = float(np.std(returns, ddof=1) * np.sqrt(12.0))

    # 夏普比率
    if annual_vol > 0:
        sharpe = float((annual_return - risk_free_rate) / annual_vol)
    else:
        sharpe = 0.0

    # 最大回撤
    cummax = np.maximum.accumulate(nav_values)
    drawdown = (nav_values - cummax) / cummax
    max_dd = float(np.min(drawdown))

    # Calmar 比率 = 年化收益 / |最大回撤|
    if max_dd != 0:
        calmar = float(annual_return / abs(max_dd))
    else:
        calmar = 0.0

    # 月度胜率
    positive_months = int(np.sum(returns > 0))
    win_rate = float(positive_months / n_periods) if n_periods > 0 else 0.0

    return {
        "total_return": round(total_return, 4),
        "annual_return": round(annual_return, 4),
        "annual_volatility": round(annual_vol, 4),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown": round(max_dd, 4),
        "calmar_ratio": round(calmar, 3),
        "monthly_win_rate": round(win_rate, 3),
    }


def _empty_metrics() -> dict:
    """返回空/零值指标字典"""
    return {
        "total_return": 0.0,
        "annual_return": 0.0,
        "annual_volatility": 0.0,
        "sharpe_ratio": 0.0,
        "max_drawdown": 0.0,
        "calmar_ratio": 0.0,
        "monthly_win_rate": 0.0,
    }
