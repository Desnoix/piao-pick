"""
===================================
TushareFetcher - Backup Data Source (Priority 1)
===================================

Data source: Tushare Pro API (https://tushare.pro)
Features: Requires Token, has request quota limits
Advantages: High data quality, stable API

Rate limiting strategy:
1. Per-minute call counter
2. Forced sleep when exceeding free quota (80 calls/min)
3. Exponential backoff retry via tenacity
"""

import json as _json
import logging
import os
import time

import pandas as pd
import requests
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .base import (
    STANDARD_COLUMNS,
    BaseFetcher,
    DataFetchError,
    RateLimitError,
    _is_etf_code,
    is_bse_code,
    normalize_stock_code,
)

logger = logging.getLogger(__name__)


# ETF code prefixes by exchange
# Shanghai: 51xxxx, 52xxxx, 56xxxx, 58xxxx
# Shenzhen: 15xxxx, 16xxxx, 18xxxx
_ETF_SH_PREFIXES = ("51", "52", "56", "58")
_ETF_SZ_PREFIXES = ("15", "16", "18")
_ETF_ALL_PREFIXES = _ETF_SH_PREFIXES + _ETF_SZ_PREFIXES


class _TushareHttpClient:
    """Lightweight Tushare Pro client that does not require the tushare SDK."""

    def __init__(self, token: str, timeout: int = 30, api_url: str = "http://api.tushare.pro") -> None:
        self._token = token
        self._timeout = timeout
        self._api_url = api_url

    def query(self, api_name: str, fields: str = "", **kwargs) -> pd.DataFrame:
        req_params = {
            "api_name": api_name,
            "token": self._token,
            "params": kwargs,
            "fields": fields,
        }
        res = requests.post(self._api_url, json=req_params, timeout=self._timeout)
        if res.status_code != 200:
            raise Exception(f"Tushare API HTTP {res.status_code}")

        result = _json.loads(res.text)
        if result.get("code") != 0:
            raise Exception(result.get("msg") or f"Tushare API error code {result.get('code')}")

        data = result.get("data") or {}
        columns = data.get("fields") or []
        items = data.get("items") or []
        return pd.DataFrame(items, columns=columns)

    def __getattr__(self, api_name: str):
        if api_name.startswith("_"):
            raise AttributeError(api_name)

        def caller(**kwargs) -> pd.DataFrame:
            return self.query(api_name, **kwargs)

        return caller


class TushareFetcher(BaseFetcher):
    """
    Tushare Pro data source implementation.

    Priority: 1
    Data source: Tushare Pro API

    Key strategies:
    - Per-minute call counter to prevent quota exhaustion
    - Forced wait when exceeding 80 calls/minute
    - Exponential backoff retry on failure

    Quota notes (Tushare free tier):
    - Max 80 requests per minute
    - Max 500 requests per day
    """

    name = "TushareFetcher"
    priority = int(os.getenv("TUSHARE_PRIORITY", "1"))

    def __init__(self, rate_limit_per_minute: int = 80):
        """
        Initialize TushareFetcher.

        Args:
            rate_limit_per_minute: Max requests per minute (default 80, Tushare free quota)
        """
        self.rate_limit_per_minute = rate_limit_per_minute
        self._call_count = 0  # Current minute call count
        self._minute_start: float | None = None  # Current counting period start time
        self._api: object | None = None  # Tushare API instance

        # Attempt to initialize API
        self._init_api()

        # Dynamically adjust priority based on API initialization state
        self.priority = self._determine_priority()

    def _init_api(self) -> None:
        """
        Initialize Tushare API.

        If Token is not configured, this data source will be unavailable.
        Uses built-in HTTP client to avoid runtime dependency on tushare SDK.
        """
        # Import config lazily to avoid circular imports
        from app.config import get_config

        config = get_config()

        if not config.tushare_token:
            logger.warning("TUSHARE_TOKEN not configured, TushareFetcher unavailable")
            return

        try:
            self._api = _TushareHttpClient(token=config.tushare_token)
            logger.info("Tushare API initialized successfully")
        except Exception as e:
            logger.error(f"Tushare API initialization failed: {e}")
            self._api = None

    def _determine_priority(self) -> int:
        """
        Determine priority based on Token configuration and API initialization state.

        Strategy:
        - Token configured and API initialized: priority 1
        - Otherwise: priority 99 (effectively disabled)

        Returns:
            Priority number (lower = higher priority)
        """
        from app.config import get_config

        config = get_config()

        if config.tushare_token and self._api is not None:
            logger.info("TUSHARE_TOKEN configured and API initialized, TushareFetcher priority=1")
            return 1

        # Token not configured or API initialization failed
        logger.info("TushareFetcher disabled (no token or API init failed), priority=99")
        return 99

    def is_available(self) -> bool:
        """Check if this data source is available."""
        return self._api is not None

    def _check_rate_limit(self) -> None:
        """
        Check and enforce rate limiting.

        Strategy:
        1. Check if a new minute has started
        2. If so, reset counter
        3. If current minute calls exceed limit, force sleep
        """
        current_time = time.time()

        # Check if counter needs reset (new minute)
        if self._minute_start is None:
            self._minute_start = current_time
            self._call_count = 0
        elif current_time - self._minute_start >= 60:
            # A minute has passed, reset counter
            self._minute_start = current_time
            self._call_count = 0
            logger.debug("Rate limit counter reset")

        # Check if over quota
        if self._call_count >= self.rate_limit_per_minute:
            # Calculate wait time (until next minute)
            elapsed = current_time - self._minute_start
            sleep_time = max(0, 60 - elapsed) + 1  # +1 second buffer

            logger.warning(
                f"Tushare rate limit reached ({self._call_count}/{self.rate_limit_per_minute} calls/min), "
                f"waiting {sleep_time:.1f} seconds..."
            )

            time.sleep(sleep_time)

            # Reset counter
            self._minute_start = time.time()
            self._call_count = 0

        # Increment call count
        self._call_count += 1
        logger.debug(f"Tushare current minute calls: {self._call_count}/{self.rate_limit_per_minute}")

    def _convert_stock_code(self, stock_code: str) -> str:
        """
        Convert A-share code to Tushare ts_code format.

        Tushare requires format:
        - Shanghai stocks: 600519.SH
        - Shenzhen stocks: 000001.SZ
        - Shanghai ETFs: 510050.SH
        - Shenzhen ETFs: 159919.SZ
        - BSE: 920748.BJ

        Args:
            stock_code: Raw code, e.g. '600519', '000001', '563230'

        Returns:
            Tushare format code, e.g. '600519.SH', '000001.SZ'
        """
        code = normalize_stock_code(stock_code).strip()

        # Already has .SH/.SZ/.BJ suffix
        if "." in code:
            ts_code = code.upper()
            if ts_code.endswith(".SS"):
                return f"{ts_code[:-3]}.SH"
            return ts_code

        # ETF: determine exchange by prefix
        if code.startswith(_ETF_SH_PREFIXES) and len(code) == 6:
            return f"{code}.SH"
        if code.startswith(_ETF_SZ_PREFIXES) and len(code) == 6:
            return f"{code}.SZ"

        # BSE (Beijing Stock Exchange)
        if is_bse_code(code):
            return f"{code}.BJ"

        # Regular stocks:
        # Shanghai: 600xxx, 601xxx, 603xxx, 688xxx (STAR Market)
        # Shenzhen: 000xxx, 002xxx, 300xxx (ChiNext)
        if code.startswith(("600", "601", "603", "688")):
            return f"{code}.SH"
        elif code.startswith(("000", "002", "300")):
            return f"{code}.SZ"
        else:
            logger.warning(f"Cannot determine market for stock {code}, defaulting to SZ")
            return f"{code}.SZ"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch raw data from Tushare.

        Routes based on code type:
        - ETF: fund_daily()
        - Regular stock: daily()

        Flow:
        1. Check API availability
        2. Execute rate limit check
        3. Convert stock code format
        4. Call appropriate API
        """
        if self._api is None:
            raise DataFetchError("Tushare API not initialized, check TUSHARE_TOKEN configuration")

        # Rate-limit check
        self._check_rate_limit()

        ts_code = self._convert_stock_code(stock_code)

        # Determine API name based on code type
        is_etf = _is_etf_code(stock_code)
        api_name = "fund_daily" if is_etf else "daily"

        # Convert date format (Tushare requires YYYYMMDD)
        ts_start = start_date.replace("-", "")
        ts_end = end_date.replace("-", "")

        logger.debug(f"Calling Tushare {api_name}({ts_code}, {ts_start}, {ts_end})")

        try:
            if is_etf:
                df = self._api.fund_daily(
                    ts_code=ts_code,
                    start_date=ts_start,
                    end_date=ts_end,
                )
            else:
                df = self._api.daily(
                    ts_code=ts_code,
                    start_date=ts_start,
                    end_date=ts_end,
                )

            return df

        except Exception as e:
            error_msg = str(e).lower()

            # Detect quota exceeded
            if any(keyword in error_msg for keyword in ["quota", "limit", "permission"]):
                logger.warning(f"Tushare quota possibly exceeded: {e}")
                raise RateLimitError(f"Tushare quota exceeded: {e}") from e

            raise DataFetchError(f"Tushare data fetch failed: {e}") from e

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        Normalize Tushare data.

        Tushare daily/fund_daily returns columns:
        ts_code, trade_date, open, high, low, close, pre_close, change, pct_chg, vol, amount

        Maps to standard columns:
        date, open, high, low, close, volume, amount, pct_chg

        Unit conversion:
        - vol is in "lots" (手), multiply by 100 to convert to "shares" (股)
        - amount is in "thousands of yuan" (千元), multiply by 1000 to convert to "yuan" (元)
        """
        df = df.copy()

        # Column name mapping
        column_mapping = {
            "trade_date": "date",
            "vol": "volume",
        }

        df = df.rename(columns=column_mapping)

        # Convert date format (YYYYMMDD -> datetime)
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"], format="%Y%m%d")

        # Volume: lots -> shares
        if "volume" in df.columns:
            df["volume"] = df["volume"] * 100

        # Amount: thousands of yuan -> yuan
        if "amount" in df.columns:
            df["amount"] = df["amount"] * 1000

        # Add stock code column
        df["code"] = stock_code

        # Keep only required columns
        keep_cols = ["code"] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def _convert_index_code(self, index_code: str) -> str:
        """
        Convert index code to Tushare ts_code format.

        Tushare index codes:
        - 000300 (沪深300) -> 000300.SH
        - 000001 (上证指数) -> 000001.SH
        - 399001 (深证成指) -> 399001.SZ
        - 399006 (创业板指) -> 399006.SZ

        Args:
            index_code: Raw index code, e.g. '000300'

        Returns:
            Tushare format code, e.g. '000300.SH', '399001.SZ'
        """
        code = index_code.strip()

        # Already has suffix
        if "." in code:
            return code.upper()

        # Determine exchange by prefix:
        # 000xxx, 001xxx, 002xxx, 003xxx -> SH (上证指数)
        # 399xxx -> SZ (深证指数)
        if code.startswith("399"):
            return f"{code}.SZ"
        else:
            return f"{code}.SH"

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type((ConnectionError, TimeoutError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
    )
    def get_index_daily_data(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch index historical data from Tushare index_daily API.

        Args:
            index_code: Index code, e.g. '000300'
            start_date: Start date (format flexible)
            end_date: End date (format flexible)

        Returns:
            DataFrame with index daily data
        """
        if self._api is None:
            raise DataFetchError("Tushare API not initialized, check TUSHARE_TOKEN configuration")

        self._check_rate_limit()
        ts_code = self._convert_index_code(index_code)
        ts_start = start_date.replace("-", "")
        ts_end = end_date.replace("-", "")

        logger.info(f"[API call] Tushare index_daily({ts_code}, {ts_start}, {ts_end})")

        try:
            df = self._api.index_daily(
                ts_code=ts_code,
                start_date=ts_start,
                end_date=ts_end,
            )
            if df is not None and not df.empty:
                logger.info(f"[API response] Tushare index_daily success: {len(df)} rows")
                return df
            raise DataFetchError(f"[{self.name}] No index data returned for {index_code}")

        except Exception as e:
            error_msg = str(e).lower()
            if any(keyword in error_msg for keyword in ["quota", "limit", "permission"]):
                raise RateLimitError(f"Tushare quota exceeded: {e}") from e
            raise DataFetchError(f"Tushare index data fetch failed: {e}") from e

