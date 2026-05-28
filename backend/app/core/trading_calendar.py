"""
===================================
Trading Calendar Module (A-share only)
===================================

Responsibilities:
1. Determine if a date is a trading day for A-share market (XSHG)
2. Get "today" in market timezone to avoid server UTC date errors
3. Get effective trading date for checkpoint/resume logic
4. Get trade dates between a date range

Dependencies: exchange-calendars (optional, fail-open when unavailable)
"""

import logging
from datetime import date, datetime
from zoneinfo import ZoneInfo

logger = logging.getLogger(__name__)

# exchange-calendars availability
_XCALS_AVAILABLE = False
try:
    import exchange_calendars as xcals

    _XCALS_AVAILABLE = True
except ImportError:
    logger.warning(
        "exchange-calendars not installed; trading day check disabled. Install with: pip install exchange-calendars"
    )

# A-share market: Shanghai Stock Exchange
MARKET_EXCHANGE = "XSHG"
MARKET_TIMEZONE = "Asia/Shanghai"


def get_market_now(current_time: datetime | None = None) -> datetime:
    """
    Return current time in A-share market timezone (Asia/Shanghai).

    If current_time is naive, treat it as already expressed in the market timezone.
    If current_time is None, use system time converted to market timezone.

    Args:
        current_time: Optional datetime to convert. If None, use datetime.now().

    Returns:
        Datetime in Asia/Shanghai timezone
    """
    tz = ZoneInfo(MARKET_TIMEZONE)

    if current_time is None:
        return datetime.now(tz)

    if current_time.tzinfo is None:
        return current_time.replace(tzinfo=tz)

    return current_time.astimezone(tz)


def is_market_open(check_date: date) -> bool:
    """
    Check if A-share market is open on the given date.

    Fail-open: returns True if exchange-calendars unavailable or date out of range.

    Args:
        check_date: Date to check

    Returns:
        True if trading day (or fail-open), False otherwise
    """
    if not _XCALS_AVAILABLE:
        return True

    try:
        cal = xcals.get_calendar(MARKET_EXCHANGE)
        session = datetime(check_date.year, check_date.month, check_date.day)
        return cal.is_session(session)
    except ValueError as e:
        # exchange_calendars 日历数据范围有限 (如 XSHG 只到 2025-12-31)
        # 超出范围时 fail-open，仅输出 debug 日志
        logger.debug("trading_calendar.is_market_open fail-open (date out of range): %s", e)
        return True
    except Exception as e:
        logger.warning("trading_calendar.is_market_open fail-open: %s", e)
        return True


def get_effective_trading_date(
    current_time: datetime | None = None,
) -> date:
    """
    Resolve the latest reusable daily-bar date for checkpoint/resume logic.

    Rules:
    - Non-trading day / holiday: previous trading session
    - Trading day before market close: previous completed trading session
    - Trading day after market close: current trading session
    - Calendar lookup failure: fail-open to market-local natural date

    Args:
        current_time: Optional datetime to use. If None, use current time.

    Returns:
        The effective trading date
    """
    market_now = get_market_now(current_time)
    fallback_date = market_now.date()

    if not _XCALS_AVAILABLE:
        return fallback_date

    try:
        cal = xcals.get_calendar(MARKET_EXCHANGE)
        local_date = market_now.date()
        tz = ZoneInfo(MARKET_TIMEZONE)

        if not cal.is_session(local_date):
            # Not a trading day: return most recent previous session
            return cal.date_to_session(local_date, direction="previous").date()

        # It is a trading day: check if market has closed
        session = cal.date_to_session(local_date, direction="previous")
        session_close = cal.session_close(session)

        if hasattr(session_close, "tz_convert"):
            close_local = session_close.tz_convert(MARKET_TIMEZONE).to_pydatetime()
        elif session_close.tzinfo is not None:
            close_local = session_close.astimezone(tz)
        else:
            close_local = session_close.replace(tzinfo=tz)

        if market_now >= close_local:
            # Market has closed: return today's session
            return session.date()

        # Market still open: return previous completed session
        return cal.previous_session(session).date()

    except ValueError as e:
        # exchange_calendars 日历数据范围有限 (如 XSHG 只到 2025-12-31)
        logger.debug("trading_calendar.get_effective_trading_date fail-open (date out of range): %s", e)
        return fallback_date
    except Exception as e:
        logger.warning("trading_calendar.get_effective_trading_date fail-open: %s", e)
        return fallback_date


def get_trade_dates_between(
    start_date: date,
    end_date: date,
) -> list[date]:
    """
    Get list of trading dates between start_date and end_date (inclusive).

    Fail-open: returns all dates in range if exchange-calendars unavailable.

    Args:
        start_date: Start date (inclusive)
        end_date: End date (inclusive)

    Returns:
        List of trading dates
    """
    if not _XCALS_AVAILABLE:
        # Fail-open: return all dates in range
        result = []
        current = start_date
        while current <= end_date:
            result.append(current)
            current = date.fromordinal(current.toordinal() + 1)
        return result

    try:
        cal = xcals.get_calendar(MARKET_EXCHANGE)
        sessions = cal.sessions_in_range(start_date, end_date)
        return [s.date() for s in sessions]
    except Exception as e:
        logger.warning("trading_calendar.get_trade_dates_between fail-open: %s", e)
        # Fail-open: return all dates
        result = []
        current = start_date
        while current <= end_date:
            result.append(current)
            current = date.fromordinal(current.toordinal() + 1)
        return result
