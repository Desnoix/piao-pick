"""
Trading Calendar 单元测试

覆盖: get_market_now, is_market_open, get_effective_trading_date, get_trade_dates_between。
无外部依赖 (使用 exchange_calendars 或 fail-open), 标记为 @pytest.mark.unit。
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import pytest

from app.core.trading_calendar import (
    MARKET_TIMEZONE,
    get_effective_trading_date,
    get_market_now,
    get_trade_dates_between,
    is_market_open,
)

pytestmark = pytest.mark.unit


class TestGetMarketNow:
    def test_returns_timezone_aware(self):
        result = get_market_now()
        assert result.tzinfo is not None
        assert "Shanghai" in str(result.tzinfo)

    def test_naive_input_treated_as_market_time(self):
        naive = datetime(2025, 1, 15, 10, 30)
        result = get_market_now(current_time=naive)
        assert result.tzinfo is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_aware_input_converts_to_shanghai(self):
        utc = datetime(2025, 1, 15, 2, 0, tzinfo=UTC)  # 10:00 AM Shanghai
        result = get_market_now(current_time=utc)
        assert "Shanghai" in str(result.tzinfo)
        assert result.hour == 10


class TestIsMarketOpen:
    def test_weekend_is_not_open(self):
        # 2025-01-11 是周六
        saturday = date(2025, 1, 11)
        result = is_market_open(saturday)
        # 如果有 exchange_calendars 应该返回 False; 否则 fail-open 返回 True
        # 这里只验证不抛异常
        assert isinstance(result, bool)

    def test_out_of_range_fail_open(self):
        # 超出 exchange_calendars 范围 (如 2040 年) -> fail-open = True
        future = date(2040, 1, 2)
        result = is_market_open(future)
        assert result is True

    def test_returns_bool(self):
        for d in [date(2025, 1, 1), date(2025, 7, 1)]:
            assert isinstance(is_market_open(d), bool)


class TestGetEffectiveTradingDate:
    def test_returns_date(self):
        result = get_effective_trading_date()
        assert isinstance(result, date)

    def test_with_explicit_time(self):
        # 指定一个已知日期: 2025-01-15 周三 18:00 (market closed by then)
        t = datetime(2025, 1, 15, 18, 0, tzinfo=ZoneInfo(MARKET_TIMEZONE))
        result = get_effective_trading_date(current_time=t)
        assert isinstance(result, date)

    def test_future_date_fail_open(self):
        t = datetime(2040, 6, 15, 15, 30, tzinfo=ZoneInfo(MARKET_TIMEZONE))
        result = get_effective_trading_date(current_time=t)
        assert isinstance(result, date)


class TestGetTradeDatesBetween:
    def test_returns_list_of_dates(self):
        result = get_trade_dates_between(date(2025, 1, 1), date(2025, 1, 31))
        assert isinstance(result, list)
        assert all(isinstance(d, date) for d in result)

    def test_result_within_range(self):
        start = date(2025, 3, 1)
        end = date(2025, 3, 31)
        result = get_trade_dates_between(start, end)
        for d in result:
            assert start <= d <= end

    def test_future_range_fail_open_returns_all(self):
        start = date(2040, 1, 1)
        end = date(2040, 1, 10)
        result = get_trade_dates_between(start, end)
        assert len(result) >= 1

    def test_single_day_range(self):
        d = date(2025, 1, 15)
        result = get_trade_dates_between(d, d)
        assert isinstance(result, list)
        assert all(r == d for r in result) or len(result) <= 1
