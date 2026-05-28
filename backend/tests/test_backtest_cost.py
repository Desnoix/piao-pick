"""
P0-1 回测交易成本模型验证测试

测试 BacktestEngine 在不同成本参数下的扣费行为。
运行: python -m pytest backend/tests/test_backtest_cost.py -v
"""

from datetime import date

import pandas as pd
import pytest

REBALANCE_DATES = [date(2024, 1, 31), date(2024, 2, 29), date(2024, 3, 29)]
STOCKS = ["000001", "000002", "000003"]
ALT_STOCKS = ["999001", "999002", "999003"]
ALL_STOCKS = STOCKS + ALT_STOCKS

# 每期收盘价递增 10%（2024-01-31=10, 2024-02-29=11, 2024-03-29=12.1）
PRICE_BY_DATE = {
    date(2024, 1, 31): 10.0,
    date(2024, 2, 29): 11.0,
    date(2024, 3, 29): 12.1,
}


def make_stubs(stocks=ALL_STOCKS):
    """构造 BacktestEngine 桩函数，所有股票收盘价相同且按期递增 10%"""
    from app.core.backtest.engine import BacktestEngine

    engine = BacktestEngine()

    def get_trade_dates(s, e):
        return REBALANCE_DATES

    def get_factors_snapshot(r):
        return pd.DataFrame({"f1": [0.5] * len(stocks)}, index=stocks)

    def get_kline_snapshot(r):
        p = PRICE_BY_DATE[r]
        return pd.DataFrame(
            {"close": [p] * len(stocks), "close_adj": [p] * len(stocks)},
            index=stocks,
        )

    return engine, get_trade_dates, get_factors_snapshot, get_kline_snapshot


def test_no_cost_baseline():
    """成本参数全为 0 时，结果与旧逻辑一致（裸收益不扣费）"""
    engine, gtd, gfs, gks = make_stubs()

    def run_strategy(name, r, f):
        return STOCKS

    result = engine.run(
        "test",
        "2024-01-01",
        "2024-03-31",
        gtd,
        gfs,
        gks,
        run_strategy,
        commission_rate=0.0,
        stamp_tax=0.0,
        slippage=0.0,
    )

    # 两期各涨 10%，无成本时 raw = net = 0.10
    assert result["portfolio_returns"][0] == pytest.approx(0.10, abs=1e-6)
    assert result["portfolio_returns"][1] == pytest.approx(0.10, abs=1e-6)
    assert result["total_cost"] == 0.0
    assert result["avg_cost_per_period"] == 0.0
    assert "cost_deductions" in result


def test_default_costs_deducted():
    """默认成本下扣费正确: round_trip=0.0031，按换手率比例逐期扣除"""
    engine, gtd, gfs, gks = make_stubs()

    def run_strategy(name, r, f):
        # 第一期: STOCKS（首次建仓，turnover=1.0）
        # 第二期: 留 000002/000003，换掉 000001 → turnover=1/3
        if r == REBALANCE_DATES[0]:
            return STOCKS
        return STOCKS[1:] + [ALT_STOCKS[0]]

    result = engine.run(
        "test",
        "2024-01-01",
        "2024-03-31",
        gtd,
        gfs,
        gks,
        run_strategy,
        commission_rate=0.0003,
        stamp_tax=0.0005,
        slippage=0.001,
    )

    # round_trip = 0.0003*2 + 0.0005 + 0.001*2 = 0.0031
    round_trip = 0.0031

    # 第一期: turnover=1.0, net = 0.10 - 1.0 * 0.0031 = 0.0969
    assert result["portfolio_returns"][0] == pytest.approx(0.10 - 1.0 * round_trip, abs=1e-6)

    # 第二期: overlap={000002,000003}=2, total=3, turnover=1/3
    # net = 0.10 - (1/3) * 0.0031 ≈ 0.098967
    turnover_p1 = 1.0 - 2 / 3
    expected_p1 = 0.10 - turnover_p1 * round_trip
    assert result["portfolio_returns"][1] == pytest.approx(expected_p1, abs=1e-4)

    # 成本统计字段
    assert result["total_cost"] > 0.0
    assert result["avg_cost_per_period"] == pytest.approx(result["total_cost"] / 2, abs=1e-6)
    assert len(result["cost_deductions"]) == 2


def test_high_turnover_amplifies_cost():
    """高换手策略总成本 > 低换手策略，且同期净收益更低"""
    engine, gtd, gfs, gks = make_stubs()

    # 高换手: 第一期 STOCKS，第二期全部换成 ALT_STOCKS（turnover=1.0）
    def rs_high(name, r, f):
        return STOCKS if r == REBALANCE_DATES[0] else ALT_STOCKS

    # 低换手: 始终持有 STOCKS（第二期 turnover=0）
    def rs_low(name, r, f):
        return STOCKS

    res_high = engine.run(
        "test",
        "2024-01-01",
        "2024-03-31",
        gtd,
        gfs,
        gks,
        rs_high,
        commission_rate=0.0003,
        stamp_tax=0.0005,
        slippage=0.001,
    )
    res_low = engine.run(
        "test",
        "2024-01-01",
        "2024-03-31",
        gtd,
        gfs,
        gks,
        rs_low,
        commission_rate=0.0003,
        stamp_tax=0.0005,
        slippage=0.001,
    )

    # 第一期两者换手相同 (1.0)，总成本差异来自第二期
    assert res_high["total_cost"] > res_low["total_cost"]

    # 第二期: 低换手换手率=0 (无成本)，高换手换手率=1.0 (full round-trip)
    # 低换手净收益 0.10 > 高换手净收益 0.10 - 0.0031 = 0.0969
    assert res_low["portfolio_returns"][1] > res_high["portfolio_returns"][1]

    # 低换手第二期应完全无成本扣除
    assert res_low["cost_deductions"][1] == pytest.approx(0.0, abs=1e-9)
