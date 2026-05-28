"""
P1-4 回测涨跌停处理验证测试

测试 BacktestEngine 对涨停 (不可买入) 和跌停 (延迟卖出) 的正确处理。
运行: python -m pytest backend/tests/test_backtest_limit.py -v
"""

from datetime import date

import pandas as pd
import pytest

from app.core.backtest.engine import BacktestEngine

# ---------- 公共交易日序列 (跨3个月, 保证至少2个rebalance点) ----------
TRADE_DATES_3M = [
    date(2020, 1, 23),
    date(2020, 1, 31),
    date(2020, 2, 3),
    date(2020, 2, 28),
    date(2020, 3, 2),
    date(2020, 3, 31),
]


def _make_engine():
    return BacktestEngine()


# ============================================================
# 测试1: 涨停股不纳入买入
# ============================================================
def test_limit_up_skip_buy():
    """涨停股应被跳过, 仅非涨停股参与收益计算"""
    engine = _make_engine()

    # 1月31日 (买入日): 000001 涨停, 000002 正常
    kline_buy = pd.DataFrame(
        {
            "close": [11.0, 22.0],
            "close_adj": [11.0, 22.0],
            "is_limit_up": [1, 0],
            "is_limit_down": [0, 0],
        },
        index=["000001", "000002"],
    )
    # 2月28日 (卖出日): 两只均正常, 000002 涨到 24.0
    kline_sell = pd.DataFrame(
        {
            "close": [12.0, 24.0],
            "close_adj": [12.0, 24.0],
            "is_limit_up": [0, 0],
            "is_limit_down": [0, 0],
        },
        index=["000001", "000002"],
    )

    def get_trade_dates(s, e):
        return TRADE_DATES_3M

    def get_factors_snapshot(rdate):
        return pd.DataFrame({"f1": [0.9, 0.8]}, index=["000001", "000002"])

    def get_kline_snapshot(rdate):
        # 买入阶段 (1月) 用涨停行情, 其余用卖出行情
        if rdate == date(2020, 1, 23) or rdate == date(2020, 1, 31):
            return kline_buy
        return kline_sell

    def run_strategy(name, rdate, factors):
        return ["000001", "000002"]

    result = engine.run(
        strategy_name="test",
        start_date="2020-01-01",
        end_date="2020-03-31",
        get_trade_dates=get_trade_dates,
        get_factors_snapshot=get_factors_snapshot,
        get_kline_snapshot=get_kline_snapshot,
        run_strategy_fn=run_strategy,
        commission_rate=0.0,
        stamp_tax=0.0,
        slippage=0.0,  # 关闭成本干扰
    )

    # 1. 涨停股被跳过
    assert result["tradeability_stats"]["limit_up_skipped_total"] == 1

    # 2. 仅 000002 参与第一期收益: ret = 24.0/22.0 - 1 = 0.0909...
    assert len(result["portfolio_returns"]) >= 1
    # 第一期 raw return ≈ 0.0909 (无成本)
    assert result["portfolio_returns"][0] == pytest.approx(24.0 / 22.0 - 1.0, abs=1e-4)

    # 3. portfolio_returns 非空
    assert len(result["portfolio_returns"]) > 0


# ============================================================
# 测试2: 跌停股延迟卖出
# ============================================================
def test_limit_down_deferred_sell():
    """卖出日跌停的股票应延迟到下一个非跌停日卖出"""
    engine = _make_engine()

    # 1月31日 (买入日): 正常
    kline_buy = pd.DataFrame(
        {
            "close": [10.0, 20.0],
            "close_adj": [10.0, 20.0],
            "is_limit_up": [0, 0],
            "is_limit_down": [0, 0],
        },
        index=["000001", "000002"],
    )
    # 2月28日 (卖出日): 000001 跌停, 000002 正常
    kline_sell = pd.DataFrame(
        {
            "close": [7.29, 18.0],
            "close_adj": [7.29, 18.0],
            "is_limit_up": [0, 0],
            "is_limit_down": [1, 0],
        },
        index=["000001", "000002"],
    )
    # 3月2日 (延迟卖出日): 000001 开板, 价格 7.50
    kline_defer = pd.DataFrame(
        {
            "close": [7.50, 19.0],
            "close_adj": [7.50, 19.0],
            "is_limit_up": [0, 0],
            "is_limit_down": [0, 0],
        },
        index=["000001", "000002"],
    )

    def get_trade_dates(s, e):
        return TRADE_DATES_3M

    def get_factors_snapshot(rdate):
        return pd.DataFrame({"f1": [0.8, 0.9]}, index=["000001", "000002"])

    def get_kline_snapshot(rdate):
        if rdate == date(2020, 1, 23) or rdate == date(2020, 1, 31):
            return kline_buy
        if rdate == date(2020, 2, 3) or rdate == date(2020, 2, 28):
            return kline_sell
        # 3月2日及之后开板
        return kline_defer

    def run_strategy(name, rdate, factors):
        return ["000001", "000002"]

    result = engine.run(
        strategy_name="test",
        start_date="2020-01-01",
        end_date="2020-03-31",
        get_trade_dates=get_trade_dates,
        get_factors_snapshot=get_factors_snapshot,
        get_kline_snapshot=get_kline_snapshot,
        run_strategy_fn=run_strategy,
        commission_rate=0.0,
        stamp_tax=0.0,
        slippage=0.0,
    )

    # 1. 跌停延迟记录
    assert result["tradeability_stats"]["limit_down_deferred_total"] >= 1

    # 2. 第一期: 000001 延迟至 3月2日 以 7.50 卖出, ret = 7.5/10 - 1 = -0.25
    #    000002 正常以 18.0 卖出, ret = 18/20 - 1 = -0.10
    #    raw period_return = (-0.25 + -0.10) / 2 = -0.175
    assert result["portfolio_returns"][0] == pytest.approx(-0.175, abs=1e-4)

    # 3. 收益为负 (确认非 0)
    assert result["portfolio_returns"][0] < 0


# ============================================================
# 测试3: 向后兼容 - 无涨跌停标记时行为不变
# ============================================================
def test_no_limit_flags_backward_compat():
    """DataFrame 不含 is_limit_up/is_limit_down 时, 行为与旧版一致"""
    engine = _make_engine()

    # 旧版 DataFrame, 无涨跌停列
    kline_old = pd.DataFrame(
        {"close": [10.0, 20.0], "close_adj": [10.0, 20.0]},
        index=["000001", "000002"],
    )

    def get_trade_dates(s, e):
        return TRADE_DATES_3M

    def get_factors_snapshot(rdate):
        return pd.DataFrame({"f1": [0.8, 0.9]}, index=["000001", "000002"])

    def get_kline_snapshot(rdate):
        return kline_old

    def run_strategy(name, rdate, factors):
        return ["000001", "000002"]

    result = engine.run(
        strategy_name="test",
        start_date="2020-01-01",
        end_date="2020-03-31",
        get_trade_dates=get_trade_dates,
        get_factors_snapshot=get_factors_snapshot,
        get_kline_snapshot=get_kline_snapshot,
        run_strategy_fn=run_strategy,
        commission_rate=0.0,
        stamp_tax=0.0,
        slippage=0.0,
    )

    # 无过滤: 两只股票均参与, 卖出价=买入价 → 收益为 0
    assert result["tradeability_stats"]["limit_up_skipped_total"] == 0
    assert result["tradeability_stats"]["limit_down_deferred_total"] == 0
    assert len(result["portfolio_returns"]) >= 1
    # 同一行情快照, 买卖价相同 → 0 收益
    assert result["portfolio_returns"][0] == pytest.approx(0.0, abs=1e-6)


# ============================================================
# 测试4: 全部涨停导致空持仓 → 本期收益 0
# ============================================================
def test_all_limit_up_empty_portfolio():
    """所有股票均涨停时, 本期无可交易股票, 收益为 0"""
    engine = _make_engine()

    kline_all_limit = pd.DataFrame(
        {
            "close": [11.0, 22.0],
            "close_adj": [11.0, 22.0],
            "is_limit_up": [1, 1],  # 全部涨停
            "is_limit_down": [0, 0],
        },
        index=["000001", "000002"],
    )
    kline_normal = pd.DataFrame(
        {
            "close": [12.0, 24.0],
            "close_adj": [12.0, 24.0],
            "is_limit_up": [0, 0],
            "is_limit_down": [0, 0],
        },
        index=["000001", "000002"],
    )

    def get_trade_dates(s, e):
        return TRADE_DATES_3M

    def get_factors_snapshot(rdate):
        return pd.DataFrame({"f1": [0.9, 0.8]}, index=["000001", "000002"])

    def get_kline_snapshot(rdate):
        # 1月买入日全涨停, 2月之后正常
        if rdate == date(2020, 1, 23) or rdate == date(2020, 1, 31):
            return kline_all_limit
        return kline_normal

    def run_strategy(name, rdate, factors):
        return ["000001", "000002"]

    result = engine.run(
        strategy_name="test",
        start_date="2020-01-01",
        end_date="2020-03-31",
        get_trade_dates=get_trade_dates,
        get_factors_snapshot=get_factors_snapshot,
        get_kline_snapshot=get_kline_snapshot,
        run_strategy_fn=run_strategy,
        commission_rate=0.0,
        stamp_tax=0.0,
        slippage=0.0,
    )

    # 第一期全部跳过, 收益为 0
    assert result["tradeability_stats"]["limit_up_skipped_total"] >= 2
    assert result["portfolio_returns"][0] == pytest.approx(0.0, abs=1e-6)


if __name__ == "__main__":
    test_limit_up_skip_buy()
    print("[PASS] test_limit_up_skip_buy")
    test_limit_down_deferred_sell()
    print("[PASS] test_limit_down_deferred_sell")
    test_no_limit_flags_backward_compat()
    print("[PASS] test_no_limit_flags_backward_compat")
    test_all_limit_up_empty_portfolio()
    print("[PASS] test_all_limit_up_empty_portfolio")
    print("All tests passed.")
