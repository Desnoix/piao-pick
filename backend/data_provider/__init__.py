# -*- coding: utf-8 -*-
"""
Data Provider package for piao-pick stock screening system.

Exports:
- BaseFetcher: Abstract base class for data sources
- DataFetcherManager: Strategy manager with auto-failover
- normalize_stock_code: Normalize A-share stock codes
- canonical_stock_code: Canonical uppercase stock code form
- AkshareFetcher: Primary data source (East Money via akshare)
- TushareFetcher: Backup data source (Tushare Pro API)
"""

from .base import (
    BaseFetcher,
    DataFetcherManager,
    DataFetchError,
    RateLimitError,
    STANDARD_COLUMNS,
    normalize_stock_code,
    canonical_stock_code,
    is_bse_code,
    is_st_stock,
    is_kc_cy_stock,
)
from .akshare_fetcher import AkshareFetcher
from .tushare_fetcher import TushareFetcher

__all__ = [
    "BaseFetcher",
    "DataFetcherManager",
    "DataFetchError",
    "RateLimitError",
    "STANDARD_COLUMNS",
    "normalize_stock_code",
    "canonical_stock_code",
    "is_bse_code",
    "is_st_stock",
    "is_kc_cy_stock",
    "AkshareFetcher",
    "TushareFetcher",
]
