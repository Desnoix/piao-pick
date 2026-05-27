# -*- coding: utf-8 -*-
"""
回测 API 端点

- POST /run              运行回测
- GET  /available-dates  获取可用日期范围
- GET  /{strategy_name}  获取策略最近回测结果 (stub)
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()


# -- Request / Response schemas --


class BacktestRunRequest(BaseModel):
    strategy_id: str
    start_date: str
    end_date: str
    initial_capital: float = 1000000.0
    commission_rate: float = 0.0003
    slippage: float = 0.001


class BacktestRunResponse(BaseModel):
    strategy_name: str
    start_date: str
    end_date: str
    period: dict
    metrics: dict
    nav_series: list
    returns: list
    turnover_history: list


class AvailableDatesResponse(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    trade_date_count: int = 0


# -- Endpoints --


@router.post("/run", summary="运行回测", response_model=BacktestRunResponse)
async def run_backtest(req: BacktestRunRequest):
    """
    运行月度调仓回测。

    使用 BacktestService 执行完整的回测流程：
    1. 获取交易日历
    2. 按月调仓选股
    3. 计算等权持仓收益
    4. 计算风险指标 (Sharpe, MaxDD, Calmar, etc.)
    """
    from app.services.backtest_service import BacktestService

    try:
        service = BacktestService()
        result = service.run_backtest(
            strategy_name=req.strategy_id,
            start_date=req.start_date,
            end_date=req.end_date,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception(f"Backtest failed: {e}")
        raise HTTPException(status_code=500, detail=f"Backtest execution error: {e}")


@router.get("/available-dates", summary="获取可用回测日期范围", response_model=AvailableDatesResponse)
async def get_available_dates():
    """
    返回行情数据中可用的日期范围。

    用于前端回测表单的日期选择器限制。
    """
    from app.services.backtest_service import BacktestService

    try:
        service = BacktestService()
        return service.get_available_dates()
    except Exception as e:
        logger.exception(f"Failed to get available dates: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{strategy_name}", summary="获取策略最近回测结果")
async def get_last_backtest(strategy_name: str):
    """
    获取某策略最近一次回测结果 (stub)。

    当前返回空结果，未来可从 BacktestRepository 查询持久化的回测记录。
    """
    from app.repositories import BacktestRepository
    from app.database import get_db

    repo = BacktestRepository(get_db())
    results = repo.list_backtests(strategy_id=strategy_name)

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No backtest results found for strategy: {strategy_name}",
        )

    return results[-1]


@router.get("/results", summary="获取回测结果列表")
async def list_backtest_results(
    strategy_id: Optional[str] = Query(None, description="策略 ID"),
):
    """获取历史回测结果列表"""
    from app.repositories import BacktestRepository
    from app.database import get_db

    repo = BacktestRepository(get_db())
    results = repo.list_backtests(strategy_id=strategy_id)
    return results
