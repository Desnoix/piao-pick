"""
===================================
JQDataFetcher - Supplementary Data Source (Priority 3)
===================================

Data source: JoinQuant (JQData) via jqdatasdk
Features: Requires free registration, provides financial/fundamental data
Use case: PE, PB, ROE, gross margin, revenue growth rates for factor computation

NOT for kline data — Baostock/Akshare/Tushare handle kline.
This fetcher provides financial indicators and valuation data.

Authentication:
- JQData supports username+password or token-based auth
- Credentials stored in settings.json (configurable via Settings API)
- Also supports .env fallback: JQDATA_TOKEN, JQDATA_PASSWORD

JQData code format: 000001.XSHE, 600519.XSHG
JQData trial limits: 1 million data points/day, 3 months historical data gap
"""

import logging
import os
from datetime import datetime
from typing import Optional

import pandas as pd

from .base import BaseFetcher, DataFetchError

logger = logging.getLogger(__name__)


class JQDataFetcher(BaseFetcher):
    """
    JQData data source implementation.

    Priority: 3 (supplementary — lowest priority, not in kline failover)
    Data source: JoinQuant jqdatasdk

    This fetcher specializes in financial/fundamental data:
    - Financial indicators: ROE, ROA, gross margin, net margin, growth rates
    - Valuation: PE, PB, PS, market cap, turnover
    - Stock basic info: name, listing date, industry
    - Stock code lists: all A-shares, index constituents

    Key characteristics:
    - NOT for kline data (use Baostock/Akshare/Tushare)
    - jqdatasdk is NOT thread-safe — use single threaded access
    - Trial accounts: 1M data points/day, missing last 3 months data
    - market_cap unit: 亿元 (100M yuan)
    - roe/roa/margins unit: % (percentage points)
    """

    name = "JQDataFetcher"
    priority = int(os.getenv("JQDATA_PRIORITY", "3"))

    def __init__(self):
        self._jq = None
        self._authenticated = False
        self._username = None
        self._password = None
        self._load_credentials()

    def _load_credentials(self):
        """Load JQData credentials from settings store (priority) or .env (fallback)."""
        # Priority: settings.json > .env
        try:
            from app.services.settings_store import get_settings_store

            store = get_settings_store()
            token = store.get("jqdata_token")
            password = store.get("jqdata_password")
            if token and password:
                self._username = token
                self._password = password
                logger.info("[JQData] Using credentials from settings store")
                return
        except ImportError:
            pass

        # Fallback to .env
        from app.config import get_config

        config = get_config()
        token = config.jqdata_token
        password = config.jqdata_password
        if token and password:
            self._username = token
            self._password = password
            logger.info("[JQData] Using credentials from .env")
        else:
            logger.warning("[JQData] No credentials configured. Set via Settings page or .env")

    def is_available(self) -> bool:
        """Check if credentials are configured."""
        return bool(self._username and self._password)

    def _ensure_auth(self):
        """Lazy authenticate with JQData. Not thread-safe (jqdatasdk limitation)."""
        if self._authenticated:
            return
        if not self.is_available():
            raise DataFetchError("[JQData] Not configured. Set JQData credentials in Settings.")

        import jqdatasdk as jq

        self._jq = jq
        try:
            jq.auth(self._username, self._password)
            if not jq.is_auth():
                raise DataFetchError("[JQData] Authentication failed — check credentials")
            self._authenticated = True
            logger.info("[JQData] Authentication successful")
        except Exception as e:
            raise DataFetchError(f"[JQData] Authentication error: {e}") from e

    def _convert_code(self, code: str) -> str:
        """
        Convert 6-digit A-share code to JQData format.

        JQData expects: 000001.XSHE (Shenzhen), 600519.XSHG (Shanghai)

        Args:
            code: 6-digit stock code

        Returns:
            JQData format code with exchange suffix
        """
        code = code.strip()

        # Already has exchange suffix
        if "." in code:
            return code.upper()

        # Shanghai: 600xxx, 601xxx, 603xxx, 688xxx
        if code.startswith(("600", "601", "603", "688")):
            return f"{code}.XSHG"

        # Shenzhen: 000xxx, 002xxx, 300xxx
        if code.startswith(("000", "002", "300")):
            return f"{code}.XSHE"

        raise DataFetchError(f"[JQData] Cannot determine exchange for code '{code}'")

    def get_all_stock_codes(self, date: str | None = None) -> list[str]:
        """
        Get all A-share stock codes.

        Returns JQData format codes (e.g., '000001.XSHE').
        """
        self._ensure_auth()
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        df = self._jq.get_all_securities("stock", date=date)
        return df.index.tolist()

    def get_financial_indicators(
        self,
        stock_codes: list[str],
        stat_date: str,
    ) -> pd.DataFrame:
        """
        Get financial indicators for multiple stocks at a specific report date.

        Args:
            stock_codes: List of JQData format codes (e.g., ['000001.XSHE', '600519.XSHG'])
            stat_date: Report date, e.g., '2025q3' (quarter) or '2025-09-30' (date)

        Returns:
            DataFrame with columns: code, statDate, roe, roa, gross_profit_margin,
            net_profit_margin, inc_total_revenue_year_on_year, inc_net_profit_year_on_year,
            inc_revenue_year_on_year, inc_operation_profit_year_on_year
        """
        self._ensure_auth()

        from jqdatasdk import query
        from jqdatasdk import indicator as fin_indicator

        q = query(
            fin_indicator.code,
            fin_indicator.statDate,
            fin_indicator.roe,
            fin_indicator.roa,
            fin_indicator.gross_profit_margin,
            fin_indicator.net_profit_margin,
            fin_indicator.inc_total_revenue_year_on_year,
            fin_indicator.inc_net_profit_year_on_year,
            fin_indicator.inc_revenue_year_on_year,
            fin_indicator.inc_operation_profit_year_on_year,
        ).filter(fin_indicator.code.in_(stock_codes))

        logger.info(f"[API call] JQData get_fundamentals (indicators): {len(stock_codes)} stocks, statDate={stat_date}")
        df = self._jq.get_fundamentals(q, statDate=stat_date)
        logger.info(f"[API response] JQData get_fundamentals: {len(df)} rows")
        return df

    def get_valuation_snapshot(
        self,
        stock_codes: list[str],
        date: str,
    ) -> pd.DataFrame:
        """
        Get valuation data for multiple stocks at a specific trading date.

        Args:
            stock_codes: List of JQData format codes
            date: Trading date, e.g., '2025-09-30'

        Returns:
            DataFrame with columns: code, pe_ratio, pe_ratio_lyr, pb_ratio, ps_ratio,
            market_cap, circulating_market_cap, turnover_ratio
        """
        self._ensure_auth()

        from jqdatasdk import query
        from jqdatasdk import valuation

        q = query(
            valuation.code,
            valuation.pe_ratio,
            valuation.pe_ratio_lyr,
            valuation.pb_ratio,
            valuation.ps_ratio,
            valuation.market_cap,
            valuation.circulating_market_cap,
            valuation.turnover_ratio,
        ).filter(valuation.code.in_(stock_codes))

        logger.info(f"[API call] JQData get_fundamentals (valuation): {len(stock_codes)} stocks, date={date}")
        df = self._jq.get_fundamentals(q, date=date)
        logger.info(f"[API response] JQData get_fundamentals: {len(df)} rows")
        return df

    def get_remaining_quota(self) -> int:
        """Get remaining daily data point quota."""
        self._ensure_auth()
        return self._jq.get_query_count("spare")

    def convert_code_to_standard(self, jq_code: str) -> str:
        """
        Convert JQData code format back to 6-digit.

        Args:
            jq_code: JQData format, e.g., '000001.XSHE'

        Returns:
            6-digit code, e.g., '000001'
        """
        return jq_code.split(".")[0]

    def batch_convert_to_standard(self, jq_codes: list[str]) -> list[str]:
        """Batch convert JQData codes to 6-digit format."""
        return [self.convert_code_to_standard(c) for c in jq_codes]

    # === BaseFetcher abstract methods (stub — not for kline) ===

    def _fetch_raw_data(self, stock_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """
        NOT IMPLEMENTED — JQDataFetcher does not provide kline data.
        Use BaostockFetcher, AkshareFetcher, or TushareFetcher for kline.
        """
        raise DataFetchError(
            f"[JQData] Kline data not supported. JQDataFetcher provides financial/valuation data only. "
            f"Use BaostockFetcher for kline."
        )

    def _normalize_data(self, df: pd.DataFrame, stock_code: str) -> pd.DataFrame:
        """
        NOT IMPLEMENTED — JQDataFetcher returns domain-specific DataFrames directly.
        Use the specialized methods: get_financial_indicators(), get_valuation_snapshot().
        """
        raise DataFetchError(
            f"[JQData] Normalize not supported. Use get_financial_indicators() or get_valuation_snapshot()."
        )

    def get_index_daily_data(self, index_code: str, start_date: str, end_date: str) -> pd.DataFrame:
        """NOT IMPLEMENTED — use Baostock/Akshare for index data."""
        raise DataFetchError(f"[JQData] Index data not supported. Use BaostockFetcher.")

    def get_index_spot_data(self) -> pd.DataFrame:
        """NOT IMPLEMENTED — use Akshare for real-time index data."""
        raise DataFetchError(f"[JQData] Real-time spot data not supported.")