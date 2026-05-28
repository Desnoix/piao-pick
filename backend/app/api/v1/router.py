"""
API v1 路由聚合

将所有 v1 端点路由聚合，统一添加 /api/v1 前缀。
"""

from fastapi import APIRouter

from app.api.v1 import (
    backtest,
    cache_stats,
    data_quality,
    data_status,
    factor_coverage,
    history_sync,
    market,
    selection,
    settings,
    stocks,
    strategies,
)

router = APIRouter(prefix="/api/v1")

router.include_router(stocks.router, prefix="/stocks", tags=["Stocks"])
router.include_router(factor_coverage.router, prefix="/strategies", tags=["Strategies"])
router.include_router(strategies.router, prefix="/strategies", tags=["Strategies"])
router.include_router(selection.router, prefix="/selection", tags=["Selection"])
router.include_router(backtest.router, prefix="/backtest", tags=["Backtest"])
router.include_router(data_status.router, prefix="/data", tags=["Data"])
router.include_router(history_sync.router, prefix="/data", tags=["Data"])
router.include_router(market.router, prefix="/market", tags=["Market"])
router.include_router(data_quality.router, prefix="/data-quality", tags=["DataQuality"])
router.include_router(cache_stats.router, prefix="/data", tags=["缓存"])
router.include_router(settings.router, prefix="/settings", tags=["Settings"])
