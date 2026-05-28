"""
前视偏差修复验证测试

验证 trade_date 参数在 exclude_new_listing_days 过滤中正确替代 date.today()。
"""

import sys

sys.path.insert(0, ".")

import pandas as pd

from app.core.strategy.executor import StrategyExecutor
from app.core.strategy.filters import filter_universe


def _make_data():
    """
    构造测试数据。3 只股票:
    - 600519.SH: 2001-08-27 上市 (老股票)
    - 002940.SZ: 2019-12-26 上市 (2019 年底次新)
    - 688396.SH: 2020-06-15 上市 (2020 年中次新)
    """
    stock_info = pd.DataFrame(
        {
            "ts_code": ["600519.SH", "002940.SZ", "688396.SH"],
            "name": ["贵州茅台", "测试A", "测试B"],
            "industry": ["白酒", "测试", "测试"],
            "is_st": [False, False, False],
            "is_suspended": [False, False, False],
            "list_date": ["2001-08-27", "2019-12-26", "2020-06-15"],
        }
    ).set_index("ts_code")

    factors = pd.DataFrame(
        {
            "ts_code": ["600519.SH", "002940.SZ", "688396.SH"],
            "pe_ttm": [30.5, 25.0, 40.0],
        }
    ).set_index("ts_code")

    return stock_info, factors


def test_2020_jan_excludes_new_stocks():
    """
    回测 2020-01-15, exclude_new_listing_days=60。
    截止日 = 2020-01-15 减 60天 = 2019-11-16。
    - 600519 (2001-08-27): 通过
    - 002940 (2019-12-26): 排除 (晚于 2019-11-16)
    - 688396 (2020-06-15): 排除 (晚于 2019-11-16)
    """
    executor = StrategyExecutor()
    stock_info, factors = _make_data()
    universe = {"exclude_new_listing_days": 60}

    result = executor._filter_universe(factors, stock_info, universe, trade_date="2020-01-15")
    codes = list(result.index)

    assert "600519.SH" in codes, "600519 应保留 (2001年上市)"
    assert "002940.SZ" not in codes, "002940 应排除 (2019-12-26 晚于截止日 2019-11-16)"
    assert "688396.SH" not in codes, "688396 应排除 (尚未上市)"
    print("  PASS: test_2020_jan_excludes_new_stocks")


def test_2020_jul_keeps_2019_listing():
    """
    回测 2020-07-15, exclude_new_listing_days=60。
    截止日 = 2020-07-15 减 60天 = 2020-05-16。
    - 600519 (2001-08-27): 通过
    - 002940 (2019-12-26): 通过 (早于 2020-05-16)
    - 688396 (2020-06-15): 排除 (晚于 2020-05-16)
    """
    executor = StrategyExecutor()
    stock_info, factors = _make_data()
    universe = {"exclude_new_listing_days": 60}

    result = executor._filter_universe(factors, stock_info, universe, trade_date="2020-07-15")
    codes = list(result.index)

    assert "600519.SH" in codes, "600519 应保留"
    assert "002940.SZ" in codes, "002940 应保留 (上市超60天)"
    assert "688396.SH" not in codes, "688396 应排除 (上市不足60天)"
    print("  PASS: test_2020_jul_keeps_2019_listing")


def test_none_fallback_to_today():
    """trade_date=None 时回退到 date.today()，行为与原代码一致"""
    executor = StrategyExecutor()
    stock_info, factors = _make_data()
    universe = {"exclude_new_listing_days": 60}

    result = executor._filter_universe(factors, stock_info, universe, trade_date=None)
    codes = list(result.index)

    # 2026年所有股都上市超60天，应全部保留
    assert "600519.SH" in codes
    assert "002940.SZ" in codes
    assert "688396.SH" in codes
    print("  PASS: test_none_fallback_to_today")


def test_filter_universe_standalone():
    """filters.py 独立的 filter_universe() 也正确使用 trade_date"""
    stock_df = pd.DataFrame(
        {
            "list_date": ["2001-08-27", "2019-12-26"],
            "is_st": [False, False],
        },
        index=["600519.SH", "002940.SZ"],
    )

    config = {"exclude_new_listing_days": 60}

    # 2020-01-15: 002940 应排除
    r1 = filter_universe(stock_df, config, trade_date="2020-01-15")
    assert "002940.SZ" not in r1.index, "002940 在 2020-01 应为次新股"

    # 2020-07-15: 002940 应保留
    r2 = filter_universe(stock_df, config, trade_date="2020-07-15")
    assert "002940.SZ" in r2.index, "002940 在 2020-07 已上市超60天"
    print("  PASS: test_filter_universe_standalone")


def test_backward_compatible():
    """execute() 不传 trade_date 不报错"""
    import inspect

    sig = inspect.signature(StrategyExecutor.execute)
    assert "trade_date" in sig.parameters
    assert sig.parameters["trade_date"].default is None
    print("  PASS: test_backward_compatible")


def main():
    print("=" * 60)
    print("P0-3 前视偏差修复验证")
    print("=" * 60)

    tests = [
        test_2020_jan_excludes_new_stocks,
        test_2020_jul_keeps_2019_listing,
        test_none_fallback_to_today,
        test_filter_universe_standalone,
        test_backward_compatible,
    ]

    passed = failed = 0
    for fn in tests:
        try:
            fn()
            passed += 1
        except Exception as e:
            print(f"  FAIL: {fn.__name__} -> {e}")
            import traceback

            traceback.print_exc()
            failed += 1

    print(f"\n结果: {passed} 通过, {failed} 失败")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
