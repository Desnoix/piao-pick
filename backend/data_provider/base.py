"""
===================================
Data Provider Base & Manager
===================================

Strategy Pattern:
- BaseFetcher: abstract base class defining unified interface
- DataFetcherManager: strategy manager with automatic failover

Anti-ban strategies:
1. Built-in rate limiting per fetcher
2. Automatic failover to next data source
3. Exponential backoff retry
"""

import logging
import random
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from threading import RLock

import pandas as pd

logger = logging.getLogger(__name__)


# === Standard column definitions ===
STANDARD_COLUMNS = ["date", "open", "high", "low", "close", "volume", "amount", "pct_chg"]


class DataFetchError(Exception):
    """Data fetch base exception."""

    pass


class RateLimitError(DataFetchError):
    """API rate limit exception."""

    pass


def unwrap_exception(exc: Exception) -> Exception:
    """Follow chained exceptions and return the deepest non-cyclic cause."""
    current = exc
    visited = set()

    while current is not None and id(current) not in visited:
        visited.add(id(current))
        next_exc = current.__cause__ or current.__context__
        if next_exc is None:
            break
        current = next_exc

    return current


def summarize_exception(exc: Exception) -> tuple[str, str]:
    """Build a stable summary for logs while preserving the application-layer message."""
    root = unwrap_exception(exc)
    error_type = type(root).__name__
    message = str(exc).strip() or str(root).strip() or error_type
    return error_type, " ".join(message.split())


def normalize_stock_code(stock_code: str) -> str:
    """
    Normalize A-share stock code by stripping exchange prefixes/suffixes.

    Accepted formats and their normalized results:
    - '600519'      -> '600519'   (already clean)
    - 'SH600519'    -> '600519'   (strip SH prefix)
    - 'SZ000001'    -> '000001'   (strip SZ prefix)
    - 'BJ920748'    -> '920748'   (strip BJ prefix, BSE)
    - 'sh600519'    -> '600519'   (case-insensitive)
    - '600519.SH'   -> '600519'   (strip .SH suffix)
    - '000001.SZ'   -> '000001'   (strip .SZ suffix)
    - '920748.BJ'   -> '920748'   (strip .BJ suffix, BSE)

    This function is applied at the DataFetcherManager layer so that
    all individual fetchers receive a clean 6-digit code.
    """
    code = stock_code.strip()
    upper = code.upper()

    # Strip SH/SZ prefix (e.g. SH600519 -> 600519)
    if upper.startswith(("SH", "SZ")) and not upper.startswith("SH.") and not upper.startswith("SZ."):
        candidate = code[2:]
        if candidate.isdigit() and len(candidate) in (5, 6):
            return candidate

    # Strip BJ prefix (e.g. BJ920748 -> 920748)
    if upper.startswith("BJ") and not upper.startswith("BJ."):
        candidate = code[2:]
        if candidate.isdigit() and len(candidate) == 6:
            return candidate

    # Strip .SH/.SZ/.BJ suffix (e.g. 600519.SH -> 600519, 920748.BJ -> 920748)
    if "." in code:
        base, suffix = code.rsplit(".", 1)
        if suffix.upper() in ("SH", "SZ", "SS", "BJ") and base.isdigit():
            return base

    return code


def canonical_stock_code(code: str) -> str:
    """
    Return the canonical (uppercase) form of a stock code.

    This is a display/storage layer concern, distinct from normalize_stock_code
    which strips exchange prefixes. Apply at system input boundaries to ensure
    consistent case across all input paths.

    Examples:
        '600519'  -> '600519'  (digits are unchanged)
        'sh600519' -> 'SH600519'
    """
    return (code or "").strip().upper()


ETF_PREFIXES = ("51", "52", "56", "58", "15", "16", "18")


def _is_etf_code(code: str) -> bool:
    """Check if the code is an A-share ETF fund code."""
    normalized = normalize_stock_code(code)
    return normalized.isdigit() and len(normalized) == 6 and normalized.startswith(ETF_PREFIXES)


def is_bse_code(code: str) -> bool:
    """
    Check if the code is a Beijing Stock Exchange (BSE) A-share code.

    BSE rules (2026):
    - New format (2024+): 92xxxx main trading codes
    - Historical ranges: 43xxxx, 83xxxx, 87xxxx, 88xxxx
    - Special instruments: 81xxxx convertible bonds, 82xxxx preferred shares
    - Subscription codes: 889xxx
    Note: 900xxx are Shanghai B-shares and must return False.
    """
    c = (code or "").strip().split(".")[0]
    if len(c) != 6 or not c.isdigit():
        return False

    if c.startswith("900"):
        return False

    return c.startswith(("92", "43", "81", "82", "83", "87", "88"))


def is_st_stock(name: str) -> bool:
    """
    Check if the stock is an ST or *ST stock based on its name.

    ST stocks have special trading rules and typically +/-5% limit.
    """
    n = (name or "").upper()
    return "ST" in n


def is_kc_cy_stock(code: str) -> bool:
    """
    Check if the stock is a STAR Market (科创板) or ChiNext (创业板) stock.

    - STAR Market: Codes starting with 688
    - ChiNext: Codes starting with 300
    Both have +/-20% limit.
    """
    c = (code or "").strip().split(".")[0]
    return c.startswith("688") or c.startswith("30")


class BaseFetcher(ABC):
    """
    Data source abstract base class.

    Responsibilities:
    1. Define unified data fetching interface
    2. Provide data normalization methods
    3. Implement common technical indicator calculations

    Subclasses implement:
    - _fetch_raw_data(): Fetch raw data from specific data source
    - _normalize_data(): Normalize raw data to standard format
    """

    name: str = "BaseFetcher"
    priority: int = 99  # Lower number = higher priority

    @abstractmethod
    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Fetch raw data from data source (subclass must implement).

        Args:
            stock_code: Stock code, e.g. '600519', '000001'
            start_date: Start date in 'YYYY-MM-DD' format
            end_date: End date in 'YYYY-MM-DD' format

        Returns:
            Raw DataFrame (column names vary by source)
        """
        pass

    @abstractmethod
    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        Normalize data columns (subclass must implement).

        Standardizes different source column names to:
        ['date', 'open', 'high', 'low', 'close', 'volume', 'amount', 'pct_chg']
        """
        pass

    def get_index_daily_data(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        Get index daily historical data (subclass should override).

        Default implementation raises DataFetchError — only fetchers that
        support index data need to implement this.

        Args:
            index_code: Index code, e.g. '000300' (沪深300)
            start_date: Start date in 'YYYY-MM-DD' or 'YYYYMMDD' format
            end_date: End date in 'YYYY-MM-DD' or 'YYYYMMDD' format

        Returns:
            DataFrame with columns: 日期, 开盘, 收盘, 最高, 最低, 成交量, 成交额, ...
        """
        raise DataFetchError(f"[{self.name}] Index daily data not supported")

    def get_index_spot_data(self) -> pd.DataFrame:
        """
        Get all index real-time spot data (subclass should override).

        Default implementation raises DataFetchError — only fetchers that
        support index spot data need to implement this.

        Returns:
            DataFrame with columns: 代码, 名称, 最新价, 涨跌幅, 成交量, 成交额, ...
        """
        raise DataFetchError(f"[{self.name}] Index spot data not supported")

    def get_daily_data(
        self,
        stock_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        days: int = 30,
    ) -> pd.DataFrame:
        """
        Get daily data (unified entry point).

        Flow:
        1. Calculate date range
        2. Call subclass to fetch raw data
        3. Normalize columns
        4. Calculate technical indicators

        Args:
            stock_code: Stock code
            start_date: Start date (optional)
            end_date: End date (optional, default today)
            days: Number of days to fetch (used when start_date is not specified)

        Returns:
            Normalized DataFrame with technical indicators
        """
        # Calculate date range
        if end_date is None:
            end_date = datetime.now().strftime("%Y-%m-%d")

        if start_date is None:
            # Default: get recent trading days (estimate by calendar days, fetch extra)
            start_dt = datetime.strptime(end_date, "%Y-%m-%d") - timedelta(days=days * 2)
            start_date = start_dt.strftime("%Y-%m-%d")

        request_start = time.time()
        logger.info(f"[{self.name}] Fetching {stock_code} daily data: range={start_date} ~ {end_date}")

        try:
            # Step 1: Fetch raw data
            raw_df = self._fetch_raw_data(stock_code, start_date, end_date)

            if raw_df is None or raw_df.empty:
                raise DataFetchError(f"[{self.name}] No data returned for {stock_code}")

            # Step 2: Normalize columns
            df = self._normalize_data(raw_df, stock_code)

            # Step 3: Clean data
            df = self._clean_data(df)

            # Step 4: Calculate technical indicators
            df = self._calculate_indicators(df)

            elapsed = time.time() - request_start
            logger.info(
                f"[{self.name}] {stock_code} fetch success: range={start_date} ~ {end_date}, "
                f"rows={len(df)}, elapsed={elapsed:.2f}s"
            )
            return df

        except Exception as e:
            elapsed = time.time() - request_start
            error_type, error_reason = summarize_exception(e)
            logger.error(
                f"[{self.name}] {stock_code} fetch failed: range={start_date} ~ {end_date}, "
                f"error_type={error_type}, elapsed={elapsed:.2f}s, reason={error_reason}"
            )
            raise DataFetchError(f"[{self.name}] {stock_code}: {error_reason}") from e

    def _clean_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Data cleaning:
        1. Ensure date column format is correct
        2. Numeric type conversion
        3. Remove rows with null values
        4. Sort by date
        """
        df = df.copy()

        # Ensure date column is datetime type
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])

        # Numeric column type conversion
        numeric_cols = ["open", "high", "low", "close", "volume", "amount", "pct_chg"]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        # Remove rows with missing key columns
        df = df.dropna(subset=["close", "volume"])

        # Sort by date ascending
        df = df.sort_values("date", ascending=True).reset_index(drop=True)

        return df

    def _calculate_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate technical indicators:
        - MA5, MA10, MA20: Moving averages
        - Volume_Ratio: Volume ratio (today's volume / 5-day average volume)
        """
        df = df.copy()

        # Moving averages
        df["ma5"] = df["close"].rolling(window=5, min_periods=1).mean()
        df["ma10"] = df["close"].rolling(window=10, min_periods=1).mean()
        df["ma20"] = df["close"].rolling(window=20, min_periods=1).mean()

        # Volume ratio: daily volume / 5-day average volume
        avg_volume_5 = df["volume"].rolling(window=5, min_periods=1).mean()
        df["volume_ratio"] = df["volume"] / avg_volume_5.shift(1)
        df["volume_ratio"] = df["volume_ratio"].fillna(1.0)

        # Round to 2 decimal places
        for col in ["ma5", "ma10", "ma20", "volume_ratio"]:
            if col in df.columns:
                df[col] = df[col].round(2)

        return df

    @staticmethod
    def random_sleep(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
        """
        Random jitter sleep for anti-ban purposes.
        Simulates human behavior with random delays between requests.
        """
        sleep_time = random.uniform(min_seconds, max_seconds)
        logger.debug(f"Random sleep {sleep_time:.2f} seconds...")
        time.sleep(sleep_time)


class DataFetcherManager:
    """
    Data source strategy manager.

    Responsibilities:
    1. Manage multiple data sources (sorted by priority)
    2. Automatic failover on failure
    3. Provide unified data fetching interface

    Failover strategy:
    - Use highest priority data source first
    - Automatically switch to next on failure
    - Raise exception when all sources fail
    """

    def __init__(self, fetchers: list[BaseFetcher] | None = None):
        """
        Initialize manager.

        Args:
            fetchers: List of data sources (optional, auto-creates defaults by priority)
        """
        self._fetchers: list[BaseFetcher] = []
        self._fetchers_lock = RLock()
        self._fetcher_call_locks: dict[int, RLock] = {}
        self._fetcher_call_locks_lock = RLock()
        self._stock_name_cache: dict[str, str] = {}
        self._stock_name_cache_lock = RLock()

        if fetchers:
            # Sort by priority
            self._fetchers = sorted(fetchers, key=lambda f: f.priority)
        else:
            # Default data sources will be lazily loaded on first use
            self._init_default_fetchers()

    def _ensure_concurrency_guards(self) -> None:
        """Lazily initialize thread-safety primitives."""
        if not hasattr(self, "_fetchers_lock") or self._fetchers_lock is None:
            self._fetchers_lock = RLock()
        if not hasattr(self, "_fetcher_call_locks") or self._fetcher_call_locks is None:
            self._fetcher_call_locks = {}
        if not hasattr(self, "_fetcher_call_locks_lock") or self._fetcher_call_locks_lock is None:
            self._fetcher_call_locks_lock = RLock()
        if not hasattr(self, "_stock_name_cache") or self._stock_name_cache is None:
            self._stock_name_cache = {}
        if not hasattr(self, "_stock_name_cache_lock") or self._stock_name_cache_lock is None:
            self._stock_name_cache_lock = RLock()

    def _get_fetchers_snapshot(self) -> list[BaseFetcher]:
        self._ensure_concurrency_guards()
        with self._fetchers_lock:
            return list(getattr(self, "_fetchers", []))

    def _get_fetcher_call_lock(self, fetcher: BaseFetcher) -> RLock:
        self._ensure_concurrency_guards()
        fetcher_id = id(fetcher)
        with self._fetcher_call_locks_lock:
            lock = self._fetcher_call_locks.get(fetcher_id)
            if lock is None:
                lock = RLock()
                self._fetcher_call_locks[fetcher_id] = lock
            return lock

    def _call_fetcher_method(self, fetcher: BaseFetcher, method_name: str, *args, **kwargs):
        """Serialize shared fetcher state access through manager-owned per-instance locks."""
        method = getattr(fetcher, method_name)
        with self._get_fetcher_call_lock(fetcher):
            return method(*args, **kwargs)

    def _get_cached_stock_name(self, stock_code: str) -> str | None:
        self._ensure_concurrency_guards()
        with self._stock_name_cache_lock:
            return self._stock_name_cache.get(stock_code)

    def _cache_stock_name(self, stock_code: str, name: str | None) -> str | None:
        if name is None:
            return None
        self._ensure_concurrency_guards()
        with self._stock_name_cache_lock:
            self._stock_name_cache[stock_code] = name
        return name

    def _init_default_fetchers(self) -> None:
        """
        Initialize default data source list.

        Priority:
          0. AkshareFetcher (Priority 0) - highest priority
          1. TushareFetcher (Priority 1)
        """
        from .akshare_fetcher import AkshareFetcher
        from .tushare_fetcher import TushareFetcher

        akshare = AkshareFetcher()
        tushare = TushareFetcher()

        self._ensure_concurrency_guards()
        with self._fetchers_lock:
            self._fetchers = [akshare, tushare]
            self._fetchers.sort(key=lambda f: f.priority)

        priority_info = ", ".join([f"{f.name}(P{f.priority})" for f in self._get_fetchers_snapshot()])
        logger.info(f"Initialized {len(self._fetchers)} data sources (by priority): {priority_info}")

    def add_fetcher(self, fetcher: BaseFetcher) -> None:
        """Add a data source and re-sort."""
        self._ensure_concurrency_guards()
        with self._fetchers_lock:
            self._fetchers.append(fetcher)
            self._fetchers.sort(key=lambda f: f.priority)

    def get_daily_data(
        self,
        stock_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
        days: int = 30,
    ) -> tuple[pd.DataFrame, str]:
        """
        Get daily data with automatic failover.

        Failover strategy:
        1. Start from highest priority data source
        2. On exception, automatically switch to next
        3. Log failure reasons for each source
        4. Raise detailed exception when all fail

        Args:
            stock_code: Stock code
            start_date: Start date
            end_date: End date
            days: Number of days

        Returns:
            Tuple[DataFrame, str]: (data, successful source name)

        Raises:
            DataFetchError: When all sources fail
        """
        # Normalize code (strip SH/SZ prefix etc.)
        stock_code = normalize_stock_code(stock_code)

        fetchers = self._get_fetchers_snapshot()
        errors = []
        total_fetchers = len(fetchers)
        request_start = time.time()

        for attempt, fetcher in enumerate(fetchers, start=1):
            try:
                logger.info(
                    f"[Data source attempt {attempt}/{total_fetchers}] [{fetcher.name}] fetching {stock_code}..."
                )
                df = self._call_fetcher_method(
                    fetcher,
                    "get_daily_data",
                    stock_code=stock_code,
                    start_date=start_date,
                    end_date=end_date,
                    days=days,
                )

                if df is not None and not df.empty:
                    elapsed = time.time() - request_start
                    logger.info(
                        f"[Data source complete] {stock_code} using [{fetcher.name}] success: "
                        f"rows={len(df)}, elapsed={elapsed:.2f}s"
                    )
                    return df, fetcher.name

            except Exception as e:
                error_type, error_reason = summarize_exception(e)
                error_msg = f"[{fetcher.name}] ({error_type}) {error_reason}"
                logger.warning(
                    f"[Data source failed {attempt}/{total_fetchers}] [{fetcher.name}] {stock_code}: "
                    f"error_type={error_type}, reason={error_reason}"
                )
                errors.append(error_msg)
                if attempt < total_fetchers:
                    next_fetcher = fetchers[attempt]
                    logger.info(f"[Data source switch] {stock_code}: [{fetcher.name}] -> [{next_fetcher.name}]")
                continue

        # All sources failed
        error_summary = f"All data sources failed for {stock_code}:\n" + "\n".join(errors)
        elapsed = time.time() - request_start
        logger.error(f"[Data source terminated] {stock_code} failed: elapsed={elapsed:.2f}s\n{error_summary}")
        raise DataFetchError(error_summary)

    def get_index_daily_data(
        self,
        index_code: str,
        start_date: str,
        end_date: str,
    ) -> tuple[pd.DataFrame, str]:
        """
        Get index daily data with automatic failover.

        Failover strategy:
        1. Start from highest priority data source
        2. On exception, automatically switch to next
        3. Raise DataFetchError when all sources fail

        Args:
            index_code: Index code, e.g. '000300'
            start_date: Start date
            end_date: End date

        Returns:
            Tuple[DataFrame, str]: (data, successful source name)

        Raises:
            DataFetchError: When all sources fail
        """
        fetchers = self._get_fetchers_snapshot()
        errors = []
        total_fetchers = len(fetchers)
        request_start = time.time()

        for attempt, fetcher in enumerate(fetchers, start=1):
            try:
                logger.info(
                    f"[Index data attempt {attempt}/{total_fetchers}] [{fetcher.name}] fetching {index_code}..."
                )
                df = self._call_fetcher_method(
                    fetcher,
                    "get_index_daily_data",
                    index_code=index_code,
                    start_date=start_date,
                    end_date=end_date,
                )

                if df is not None and not df.empty:
                    elapsed = time.time() - request_start
                    logger.info(
                        f"[Index data complete] {index_code} using [{fetcher.name}] success: "
                        f"rows={len(df)}, elapsed={elapsed:.2f}s"
                    )
                    return df, fetcher.name

            except Exception as e:
                error_type, error_reason = summarize_exception(e)
                error_msg = f"[{fetcher.name}] ({error_type}) {error_reason}"
                logger.warning(
                    f"[Index data failed {attempt}/{total_fetchers}] [{fetcher.name}] {index_code}: "
                    f"error_type={error_type}, reason={error_reason}"
                )
                errors.append(error_msg)
                if attempt < total_fetchers:
                    next_fetcher = fetchers[attempt]
                    logger.info(f"[Index data switch] {index_code}: [{fetcher.name}] -> [{next_fetcher.name}]")
                continue

        error_summary = f"All data sources failed for index {index_code}:\n" + "\n".join(errors)
        elapsed = time.time() - request_start
        logger.error(f"[Index data terminated] {index_code} failed: elapsed={elapsed:.2f}s\n{error_summary}")
        raise DataFetchError(error_summary)

    def get_index_spot_data(self) -> tuple[pd.DataFrame, str]:
        """
        Get all index real-time spot data with automatic failover.

        Returns:
            Tuple[DataFrame, str]: (data, successful source name)

        Raises:
            DataFetchError: When all sources fail
        """
        fetchers = self._get_fetchers_snapshot()
        errors = []
        total_fetchers = len(fetchers)
        request_start = time.time()

        for attempt, fetcher in enumerate(fetchers, start=1):
            try:
                logger.info(
                    f"[Index spot attempt {attempt}/{total_fetchers}] [{fetcher.name}]..."
                )
                df = self._call_fetcher_method(fetcher, "get_index_spot_data")

                if df is not None and not df.empty:
                    elapsed = time.time() - request_start
                    logger.info(
                        f"[Index spot complete] [{fetcher.name}] success: "
                        f"rows={len(df)}, elapsed={elapsed:.2f}s"
                    )
                    return df, fetcher.name

            except Exception as e:
                error_type, error_reason = summarize_exception(e)
                error_msg = f"[{fetcher.name}] ({error_type}) {error_reason}"
                logger.warning(
                    f"[Index spot failed {attempt}/{total_fetchers}] [{fetcher.name}]: "
                    f"error_type={error_type}, reason={error_reason}"
                )
                errors.append(error_msg)
                continue

        error_summary = "All data sources failed for index spot data:\n" + "\n".join(errors)
        elapsed = time.time() - request_start
        logger.error(f"[Index spot terminated] failed: elapsed={elapsed:.2f}s\n{error_summary}")
        raise DataFetchError(error_summary)

    @property
    def available_fetchers(self) -> list[str]:
        """Return list of available data source names."""
        return [f.name for f in self._get_fetchers_snapshot()]
