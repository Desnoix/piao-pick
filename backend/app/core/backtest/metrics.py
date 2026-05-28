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


def compute_metrics(
    nav: list[tuple[str, float]],
    portfolio_returns: list[float],
    benchmark_nav: list[tuple[str, float]] | None = None,
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

    # --- 基准对比指标 ---
    benchmark_metrics = {}
    if benchmark_nav is not None and len(benchmark_nav) >= 2:
        bm_values = np.array([v for _, v in benchmark_nav], dtype=float)

        # 对齐长度: 取策略和基准中较短的
        min_len = min(len(nav_values), len(bm_values))
        s_nav = nav_values[:min_len]
        b_nav = bm_values[:min_len]

        # 基准净值归一化为从 1.0 开始
        if b_nav[0] > 0:
            b_nav = b_nav / b_nav[0]

        # 基准收益率 (与策略同期的日/期收益率)
        b_returns = np.diff(b_nav) / b_nav[:-1]
        # 策略同期收益率 (截取对齐后)
        s_returns = np.diff(s_nav) / s_nav[:-1]

        # 对齐收益率长度
        min_ret = min(len(s_returns), len(b_returns))
        s_ret = s_returns[:min_ret]
        b_ret = b_returns[:min_ret]

        # 超额收益序列
        excess_returns = s_ret - b_ret

        # 超额收益率 (年化, 按月度 period × 12)
        excess_annual = float(np.mean(excess_returns) * 12.0)

        # 跟踪误差 (年化)
        if len(excess_returns) > 1:
            tracking_error = float(np.std(excess_returns, ddof=1) * np.sqrt(12.0))
        else:
            tracking_error = 0.0

        # 信息比率 IR = 超额收益 / 跟踪误差
        if tracking_error > 0:
            information_ratio = float(excess_annual / tracking_error)
        else:
            information_ratio = 0.0

        # Beta = Cov(Rp, Rm) / Var(Rm)
        if len(s_ret) > 1 and len(b_ret) > 1:
            cov_matrix = np.cov(s_ret, b_ret)
            var_market = cov_matrix[1, 1]
            if var_market > 0:
                beta = float(cov_matrix[0, 1] / var_market)
            else:
                beta = 0.0
        else:
            beta = 0.0

        # Alpha (年化) = Rp - [Rf + Beta * (Rm - Rf)]
        # 其中 Rp 为策略年化收益, Rm 为基准年化收益
        r_annual = float((b_nav[-1] / b_nav[0]) ** (12.0 / len(b_ret)) - 1.0) if len(b_ret) > 0 else 0.0
        alpha = float(annual_return - (risk_free_rate + beta * (r_annual - risk_free_rate)))

        # 基准自身的总收益 (供展示)
        benchmark_total_return = float(b_nav[-1] / b_nav[0] - 1.0)

        benchmark_metrics = {
            "benchmark_total_return": round(benchmark_total_return, 4),
            "excess_return": round(excess_annual, 4),
            "tracking_error": round(tracking_error, 4),
            "information_ratio": round(information_ratio, 3),
            "alpha": round(alpha, 4),
            "beta": round(beta, 3),
        }

    metrics = {
        "total_return": round(total_return, 4),
        "annual_return": round(annual_return, 4),
        "annual_volatility": round(annual_vol, 4),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown": round(max_dd, 4),
        "calmar_ratio": round(calmar, 3),
        "monthly_win_rate": round(win_rate, 3),
    }
    metrics.update(benchmark_metrics)
    return metrics


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
        "benchmark_total_return": 0.0,
        "excess_return": 0.0,
        "tracking_error": 0.0,
        "information_ratio": 0.0,
        "alpha": 0.0,
        "beta": 0.0,
    }
