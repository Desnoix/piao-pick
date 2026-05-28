"""
===================================
MootdxFetcher - Primary Data Source (Priority 0)
===================================

Data source: Tongdaxin (通达信) via mootdx library
Mechanism: Direct TCP connection to TDX market data servers (port 7709)

Key advantages over HTTP-based fetchers:
- TCP native protocol — immune to HTTP anti-bot blocking
- 3-5x faster than HTTP-based sources (no TLS handshake, no DNS per request)
- Same protocol used by professional trading terminals

Data characteristics:
- Real-time + historical K-line (daily, weekly, monthly, minute)
- Unadjusted (不复权) data from live TCP server
- Pre-adjusted data available via mootdx Reader (offline mode)
- Returns DataFrame columns: datetime, open, high, low, close, volume, amount

Connection lifecycle:
1. Lazy connect on first use (_ensure_connected)
2. Connection stays alive via heartbeat
3. Auto-reconnect on connection loss

Key constraints:
- MAX 800 bars per request — k() auto-paginates internally
- REQUIRES Chinese IP to reach TDX servers
- No pct_chg field — computed from close/prev_close locally
"""

import logging
import os
import time
from datetime import datetime
from threading import RLock

import pandas as pd

from .base import (
    STANDARD_COLUMNS,
    BaseFetcher,
    DataFetchError,
)

logger = logging.getLogger(__name__)


class MootdxFetcher(BaseFetcher):
    """
    Tongdaxin (通达信) data source via mootdx TCP protocol.

    Priority: 0 (highest — preferred over all HTTP-based sources)
    Data source: Tongdaxin market data servers

    Key characteristics:
    - TCP direct connection — immune to HTTP anti-bot blocking
    - Uses StdQuotes.k() for date-range-based fetching with auto-pagination
      (handles the 800-bar-per-request limit transparently)
    - Lazy connection with heartbeat keep-alive + bestip auto-selection
    - Thread-safe client via multithread mode
    - Computes pct_chg from close price deltas
    """

    name = "MootdxFetcher"
    priority = int(os.getenv("MOOTDX_PRIORITY", "0"))

    def __init__(self, timeout: float = 15.0):
        """
        Initialize MootdxFetcher.

        Args:
            timeout: Connection and request timeout in seconds (default 15)
        """
        self.timeout = timeout
        self._client = None
        self._lock = RLock()
        self._connected = False

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    def _ensure_connected(self) -> None:
        """
        Thread-safe lazy connection to TDX server.

        Under _lock:
        1. If already connected, return immediately
        2. Import mootdx, create Quotes client (bestip + multithread + heartbeat)
        3. Health-check via a quick 1-bar fetch (600519)
        4. Retry up to 3 times with exponential backoff
        5. Raise DataFetchError if all attempts fail

        Raises:
            DataFetchError: When connection fails after all retry attempts
        """
        with self._lock:
            if self._connected and self._client is not None:
                return

            from mootdx.quotes import Quotes

            last_error = None
            max_retries = 3

            for attempt in range(1, max_retries + 1):
                try:
                    logger.info(f"[Mootdx] Connection attempt {attempt}/{max_retries}...")
                    self._client = Quotes.factory(
                        market="std",
                        bestip=True,
                        multithread=True,
                        heartbeat=True,
                        timeout=self.timeout,
                    )
                    # Health check — 1 bar for a liquid stock
                    test = self._client.bars(symbol="600519", frequency=9, offset=1)
                    if test is not None and not (isinstance(test, pd.DataFrame) and test.empty):
                        self._connected = True
                        logger.info("[Mootdx] Connection established (verified via 600519)")
                        return
                    else:
                        last_error = "Health check returned empty data"
                        logger.warning(
                            f"[Mootdx] Connection attempt {attempt}/{max_retries}: {last_error}"
                        )

                except Exception as e:
                    last_error = str(e)
                    logger.warning(
                        f"[Mootdx] Connection attempt {attempt}/{max_retries} failed: {e}"
                    )

                if attempt < max_retries:
                    time.sleep(1.5 * attempt)

            raise DataFetchError(
                f"[{self.name}] Connection failed after {max_retries} attempts: {last_error}"
            )

    def __del__(self):
        """Cleanup: close connection on garbage collection. Silently ignore all errors."""
        try:
            if self._client is not None:
                self._client.close()
                self._client = None
                self._connected = False
        except Exception:
            pass

    # ------------------------------------------------------------------
    # BaseFetcher abstract methods
    # ------------------------------------------------------------------

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch raw daily K-line data from TDX server via mootdx.

        Uses StdQuotes.k() which provides date-range-based fetching
        with automatic pagination across the 800-bar-per-request limit.

        k() signature: k(symbol, begin, end, **kwargs)
        - Internally calculates offset/start from date difference
        - Auto-paginates 800 bars at a time
        - Filters result to [begin, end) date range
        - Sorts ascending by date

        Args:
            stock_code: 6-digit stock code, e.g. '600519', '000001'
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format

        Returns:
            Raw DataFrame with mootdx field names (datetime, open, high,
            low, close, volume, amount, year, month, day)

        Raises:
            DataFetchError: When connection fails or no data returned
        """
        self._ensure_connected()

        logger.info(
            f"[API call] mootdx Quotes.k("
            f"symbol={stock_code}, begin={start_date}, end={end_date})"
        )

        api_start = time.time()

        try:
            # k() handles date-range → offset conversion + pagination automatically
            df = self._client.k(symbol=stock_code, begin=start_date, end=end_date)
        except Exception as e:
            error_msg = str(e).lower()
            if any(kw in error_msg for kw in ["timeout", "refused", "reset", "broken pipe"]):
                self._connected = False
                self._client = None
                raise DataFetchError(
                    f"[{self.name}] Connection lost for {stock_code}: {e}. "
                    f"Will reconnect on next request."
                ) from e
            raise DataFetchError(
                f"[{self.name}] TDX query failed for {stock_code}: {e}"
            ) from e

        api_elapsed = time.time() - api_start

        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            logger.warning(
                f"[API response] mootdx k() returned empty for {stock_code}, "
                f"range={start_date}~{end_date}, elapsed={api_elapsed:.2f}s"
            )
            raise DataFetchError(
                f"[{self.name}] No data returned for {stock_code} "
                f"(range: {start_date} ~ {end_date})"
            )

        logger.info(
            f"[API response] mootdx k() success: {len(df)} rows for {stock_code}, "
            f"elapsed={api_elapsed:.2f}s"
        )

        return df.copy()

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        Normalize mootdx data to standard format.

        mootdx k() returns columns:
        - datetime (may be DatetimeIndex after to_data() processing)
        - open, high, low, close, volume, amount
        - Plus timestamp components: year, month, day, hour, minute

        Processing:
        1. Extract date from DatetimeIndex or 'datetime' column
        2. Compute pct_chg from close price deltas
        3. Map to standard columns + stock code

        Args:
            df: Raw DataFrame from mootdx k()
            stock_code: 6-digit stock code

        Returns:
            Standardized DataFrame with STANDARD_COLUMNS
        """
        df = df.copy()

        # Step 1: Extract date
        # k() may set datetime as DatetimeIndex via to_data()
        if isinstance(df.index, pd.DatetimeIndex):
            df["date"] = df.index.strftime("%Y-%m-%d")
            df = df.reset_index(drop=True)
        elif "datetime" in df.columns:
            df["date"] = pd.to_datetime(df["datetime"]).dt.strftime("%Y-%m-%d")
        elif "date" not in df.columns:
            # Fallback: assemble from year/month/day components
            if all(c in df.columns for c in ["year", "month", "day"]):
                df["date"] = pd.to_datetime(
                    df["year"].astype(str) + "-"
                    + df["month"].astype(str).str.zfill(2) + "-"
                    + df["day"].astype(str).str.zfill(2)
                ).dt.strftime("%Y-%m-%d")
            else:
                raise DataFetchError(
                    f"[{self.name}] Cannot determine date column for {stock_code}. "
                    f"Available columns: {list(df.columns)}"
                )

        # Step 2: Sort ascending by date for pct_chg calculation
        df = df.sort_values("date", ascending=True).reset_index(drop=True)

        # Step 3: Compute pct_chg from close price deltas
        # k() data is unadjusted — pct_chg reflects raw price change
        df["pct_chg"] = (df["close"].pct_change() * 100).round(3)
        # First row stays NaN — handled by BaseFetcher._clean_data()

        # Step 4: Add stock code
        df["code"] = stock_code

        # Step 5: Select and order standard columns
        keep_cols = ["code"] + STANDARD_COLUMNS
        existing_cols = [col for col in keep_cols if col in df.columns]
        df = df[existing_cols]

        # Step 6: Ensure numeric types
        numeric_cols = ["open", "high", "low", "close", "volume", "amount", "pct_chg"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    # ------------------------------------------------------------------
    # Index data
    # ------------------------------------------------------------------

    def get_index_daily_data(
        self, index_code: str, start_date: str, end_date: str
    ) -> pd.DataFrame:
        """
        Fetch index daily data via mootdx.

        TDX supports major indices natively:
        - 000001 = 上证指数
        - 399001 = 深证成指
        - 399006 = 创业板指

        Args:
            index_code: Index code
            start_date: Start date (YYYY-MM-DD or YYYYMMDD)
            end_date: End date (YYYY-MM-DD or YYYYMMDD)

        Returns:
            DataFrame with index daily data

        Raises:
            DataFetchError: On query failure or empty result
        """
        self._ensure_connected()

        # Normalize date format
        if len(start_date) == 8:
            start_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:8]}"
        if len(end_date) == 8:
            end_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:8]}"

        code = index_code.strip()

        logger.info(
            f"[API call] mootdx Quotes.index(symbol={code}, frequency=9)"
        )

        api_start = time.time()

        try:
            df = self._client.index(symbol=code, frequency=9)
        except Exception as e:
            raise DataFetchError(
                f"[{self.name}] Index query failed for {index_code}: {e}"
            ) from e

        api_elapsed = time.time() - api_start

        if df is None or (isinstance(df, pd.DataFrame) and df.empty):
            raise DataFetchError(
                f"[{self.name}] No index data returned for {index_code}, "
                f"elapsed={api_elapsed:.2f}s"
            )

        logger.info(
            f"[API response] mootdx index success: {len(df)} rows for {index_code}, "
            f"elapsed={api_elapsed:.2f}s"
        )
        return df

    def get_index_spot_data(self) -> pd.DataFrame:
        """
        Get all index real-time spot data.

        mootdx does not support bulk index spot queries over live TCP.
        Raises DataFetchError so the failover chain falls back to
        AkshareFetcher for real-time spot data.

        Raises:
            DataFetchError: Always
        """
        raise DataFetchError(
            f"[{self.name}] Bulk index spot data not supported over TDX TCP. "
            f"Will fall back to HTTP-based fetcher."
        )