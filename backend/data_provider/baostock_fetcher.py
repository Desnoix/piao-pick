"""
===================================
BaostockFetcher - Primary Data Source (Priority 0)
===================================

Data source: Baostock (http://baostock.com)
Features: Free, no Token required, most stable free A-stock data source
Mechanism: Stateful TCP connection via baostock SDK

Baostock returns ALL fields as strings — numeric type conversion is critical.

Connection lifecycle:
1. Lazy login on first use (_ensure_login)
2. Query data via bs.query_history_k_data_plus()
3. Logout on garbage collection (__del__)

Key differences from HTTP-based fetchers:
- TCP-based, stateful connection — no per-request retry needed
- Connection-level retry only (3 attempts in _ensure_login)
- No tenacity (different failure model)
"""

import logging
import os
import time
from threading import RLock

import pandas as pd

from .base import (
    STANDARD_COLUMNS,
    BaseFetcher,
    DataFetchError,
    RateLimitError,
    _is_etf_code,
)

logger = logging.getLogger(__name__)

# ETF code prefixes by exchange (for Baostock code conversion)
# Shanghai: 51xxxx, 52xxxx, 56xxxx, 58xxxx
# Shenzhen: 15xxxx, 16xxxx, 18xxxx
_ETF_SH_PREFIXES = ("51", "52", "56", "58")
_ETF_SZ_PREFIXES = ("15", "16", "18")


class BaostockFetcher(BaseFetcher):
    """
    Baostock data source implementation.

    Priority: 0 (highest, alongside AkshareFetcher)
    Data source: Baostock TCP API

    Key characteristics:
    - Stateful TCP connection (login/logout required)
    - ALL response fields are strings — must convert to numeric
    - T+1 data only (no real-time)
    - Pre-adjusted (qfq) data via adjustflag=2

    Connection notes:
    - Lazy login: connection established on first use, not at __init__
    - Thread-safe login state via RLock
    - Connection-level retry only (3 attempts, 1s sleep)
    """

    name = "BaostockFetcher"
    priority = int(os.getenv("BAOSTOCK_PRIORITY", "0"))

    def __init__(self, retry_count: int = 3, retry_sleep: float = 1.0):
        """
        Initialize BaostockFetcher.

        Args:
            retry_count: Number of login retry attempts (default 3)
            retry_sleep: Sleep seconds between login retries (default 1.0)
        """
        self.retry_count = retry_count
        self.retry_sleep = retry_sleep
        self._logged_in = False
        self._lock = RLock()
        self._bs = None

    def _ensure_login(self) -> None:
        """
        Thread-safe lazy login to Baostock.

        Under _lock:
        1. If already logged in, return immediately
        2. Import baostock, call bs.login()
        3. Retry up to retry_count times on failure
        4. Raise DataFetchError if all attempts fail

        Raises:
            DataFetchError: When login fails after all retry attempts
        """
        with self._lock:
            if self._logged_in:
                return

            import baostock as bs

            self._bs = bs

            last_error = None
            for attempt in range(1, self.retry_count + 1):
                try:
                    logger.info(f"[Baostock] Login attempt {attempt}/{self.retry_count}...")
                    lg = bs.login()
                    if lg.error_code != "0":
                        last_error = lg.error_msg
                        logger.warning(
                            f"[Baostock] Login attempt {attempt}/{self.retry_count} failed: "
                            f"error_code={lg.error_code}, error_msg={lg.error_msg}"
                        )
                        if attempt < self.retry_count:
                            time.sleep(self.retry_sleep)
                        continue

                    self._logged_in = True
                    logger.info("[Baostock] Login successful")
                    return

                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        f"[Baostock] Login attempt {attempt}/{self.retry_count} exception: {e}"
                    )
                    if attempt < self.retry_count:
                        time.sleep(self.retry_sleep)

            # All attempts exhausted
            raise DataFetchError(
                f"[{self.name}] Login failed after {self.retry_count} attempts: {last_error}"
            )

    def __del__(self):
        """Cleanup: attempt to logout on garbage collection. Silently ignore all errors."""
        try:
            if self._logged_in and self._bs is not None:
                self._bs.logout()
                self._logged_in = False
        except Exception:
            pass

    def _convert_code(self, code: str) -> str:
        """
        Convert 6-digit A-share code to Baostock format.

        Baostock expects format:
        - Shanghai stocks: sh.600519
        - Shenzhen stocks: sz.000001
        - Shanghai ETFs: sh.510050
        - Shenzhen ETFs: sz.159919

        Args:
            code: 6-digit stock code, e.g. '600519', '000001'

        Returns:
            Baostock format code, e.g. 'sh.600519', 'sz.000001'

        Raises:
            DataFetchError: When code cannot be mapped to a known exchange
        """
        code = code.strip()

        # ETF codes: determine exchange by prefix
        if code.startswith(_ETF_SH_PREFIXES) and len(code) == 6:
            return f"sh.{code}"
        if code.startswith(_ETF_SZ_PREFIXES) and len(code) == 6:
            return f"sz.{code}"

        # Regular A-share stocks
        # Shanghai: 600xxx, 601xxx, 603xxx, 688xxx (STAR Market)
        if code.startswith(("600", "601", "603", "688")):
            return f"sh.{code}"

        # Shenzhen: 000xxx, 002xxx, 300xxx (ChiNext)
        if code.startswith(("000", "002", "300")):
            return f"sz.{code}"

        raise DataFetchError(
            f"[{self.name}] Cannot determine exchange for code '{code}'. "
            f"Expected 6-digit A-share or ETF code."
        )

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch raw daily K-line data from Baostock.

        Uses bs.query_history_k_data_plus() which returns ALL fields as strings.
        Column names are lower-case English: date, code, open, high, low, close,
        preclose, volume, amount, adjustflag, turn, tradestatus, pctChg, isST.

        Args:
            stock_code: 6-digit stock code, e.g. '600519'
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format

        Returns:
            Raw DataFrame with Baostock field names (all string-typed)

        Raises:
            DataFetchError: When login fails, query fails, or no data returned
        """
        # Step 1: Ensure logged in
        self._ensure_login()

        # Step 2: Convert code to Baostock format
        baostock_code = self._convert_code(stock_code)

        # Step 3: Baostock uses YYYY-MM-DD format (keep hyphens)
        # Determine frequency: daily for all types
        frequency = "d"

        # Step 4: Build field list
        # adjustflag: 1=post, 2=pre (qfq equivalent), 3=unadjusted
        fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"

        # Step 5: Log and execute query
        logger.info(
            f"[API call] bs.query_history_k_data_plus("
            f"code={baostock_code}, frequency={frequency}, "
            f"start_date={start_date}, end_date={end_date}, "
            f"adjustflag=2, fields=...)"
        )

        api_start = time.time()

        rs = self._bs.query_history_k_data_plus(
            code=baostock_code,
            fields=fields,
            start_date=start_date,
            end_date=end_date,
            frequency=frequency,
            adjustflag="2",
        )

        # Step 6: Check query result status
        if rs.error_code != "0":
            raise DataFetchError(
                f"[{self.name}] Query failed for {stock_code}: "
                f"error_code={rs.error_code}, error_msg={rs.error_msg}"
            )

        # Step 7: Iterate through result set and build DataFrame
        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())

        # Step 8: Build DataFrame
        if not rows:
            api_elapsed = time.time() - api_start
            logger.warning(
                f"[API response] bs.query_history_k_data_plus returned empty data "
                f"for {stock_code}, elapsed={api_elapsed:.2f}s"
            )
            raise DataFetchError(
                f"[{self.name}] No data returned for {stock_code} "
                f"(range: {start_date} ~ {end_date})"
            )

        # Get column names from result set fields
        column_names = rs.fields
        df = pd.DataFrame(rows, columns=column_names)

        api_elapsed = time.time() - api_start
        logger.info(
            f"[API response] bs.query_history_k_data_plus success: "
            f"{len(df)} rows for {stock_code}, elapsed={api_elapsed:.2f}s"
        )

        return df

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        Normalize Baostock data to standard format.

        CRITICAL: Baostock returns ALL fields as strings — must convert to numeric.
        Uses pd.to_numeric() with errors='coerce' to handle non-numeric values.

        Baostock columns -> Standard columns mapping:
        - date, open, high, low, close, volume, amount: keep as-is
        - pctChg -> pct_chg

        Args:
            df: Raw DataFrame from Baostock (all string columns)
            stock_code: 6-digit stock code

        Returns:
            Standardized DataFrame with columns: code, date, open, high, low,
            close, volume, amount, pct_chg
        """
        df = df.copy()

        # Convert numeric columns from strings to float
        numeric_cols = ["open", "high", "low", "close", "preclose", "volume", "amount", "turn", "pctChg"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Map Baostock column names to standard names
        # pctChg -> pct_chg (only renaming needed; others keep same name)
        column_mapping = {
            "pctChg": "pct_chg",
        }
        df = df.rename(columns=column_mapping)

        # Add stock code column
        df["code"] = stock_code

        # Keep only required columns: code + STANDARD_COLUMNS
        keep_cols = ["code"] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        return df

    def get_index_daily_data(
        self, index_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """
        Fetch index daily historical data from Baostock.

        Args:
            index_code: Index code, e.g. '000300' (沪深300), '399001' (深证成指)
            start_date: Start date in 'YYYY-MM-DD' or 'YYYYMMDD' format
            end_date: End date in 'YYYY-MM-DD' or 'YYYYMMDD' format

        Returns:
            DataFrame with index daily data (Baostock column names)

        Raises:
            DataFetchError: When login fails, query fails, or no data returned
        """
        # Step 1: Ensure logged in
        self._ensure_login()

        # Step 2: Convert index code to Baostock format
        code = index_code.strip()

        # Already has prefix (e.g. sh.000300)
        if "." in code:
            baostock_code = code.lower()
        else:
            # Follow same convention as TushareFetcher._convert_index_code:
            # 399xxx -> sz.{code}, everything else -> sh.{code}
            if code.startswith("399"):
                baostock_code = f"sz.{code}"
            else:
                baostock_code = f"sh.{code}"

        # Step 3: Strip hyphens only if present (Baostock accepts both formats)
        if "-" in start_date and "-" in end_date:
            pass  # Baostock accepts YYYY-MM-DD format
        else:
            # Ensure YYYY-MM-DD format if received as YYYYMMDD
            if len(start_date) == 8:
                start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
            if len(end_date) == 8:
                end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

        # Step 4: Build field list and query
        fields = "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST"

        logger.info(
            f"[API call] bs.query_history_k_data_plus("
            f"code={baostock_code}, frequency=d, "
            f"start_date={start_date}, end_date={end_date})"
        )

        api_start = time.time()

        rs = self._bs.query_history_k_data_plus(
            code=baostock_code,
            fields=fields,
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2",
        )

        if rs.error_code != "0":
            raise DataFetchError(
                f"[{self.name}] Index query failed for {index_code}: "
                f"error_code={rs.error_code}, error_msg={rs.error_msg}"
            )

        rows = []
        while rs.error_code == "0" and rs.next():
            rows.append(rs.get_row_data())

        if not rows:
            api_elapsed = time.time() - api_start
            logger.warning(
                f"[API response] bs.query_history_k_data_plus returned empty data "
                f"for index {index_code}, elapsed={api_elapsed:.2f}s"
            )
            raise DataFetchError(
                f"[{self.name}] No index data returned for {index_code} "
                f"(range: {start_date} ~ {end_date})"
            )

        column_names = rs.fields
        df = pd.DataFrame(rows, columns=column_names)

        api_elapsed = time.time() - api_start
        logger.info(
            f"[API response] bs.query_history_k_data_plus success: "
            f"{len(df)} rows for index {index_code}, elapsed={api_elapsed:.2f}s"
        )

        return df

    def get_index_spot_data(self) -> pd.DataFrame:
        """
        Get all index real-time spot data.

        Baostock is a T+1 data source and does not support real-time
        spot data. This method always raises DataFetchError.

        Raises:
            DataFetchError: Always, with explanatory message
        """
        raise DataFetchError(
            f"[{self.name}] Baostock does not support real-time spot data. "
            f"Baostock is a T+1 historical data source only."
        )