# -*- coding: utf-8 -*-
"""
API v1 路由聚合

将所有 v1 端点路由聚合，统一添加 /api/v1 前缀。
"""

from fastapi import APIRouter

from app.api.v1 import stocks, strategies, selection, backtest, data_status, history_sync

router = APIRouter(prefix="/api/v1")

router.include_router(stocks.router, prefix="/stocks", tags=["Stocks"])
router.include_router(strategies.router, prefix="/strategies", tags=["Strategies"])
router.include_router(selection.router, prefix="/selection", tags=["Selection"])
router.include_router(backtest.router, prefix="/backtest", tags=["Backtest"])
router.include_router(data_status.router, prefix="/data", tags=["Data"])
router.include_router(history_sync.router, prefix="/data", tags=["Data"])
