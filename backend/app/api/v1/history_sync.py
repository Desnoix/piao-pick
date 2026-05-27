# -*- coding: utf-8 -*-
"""
历史数据同步 API 接口

- POST /history-sync          启动历史数据同步
- GET  /history-sync/status    查询最新同步任务状态
- GET  /history-sync/{task_id} 查询指定任务状态
- GET  /history-sync/history   列出历史同步任务
"""

import logging
from typing import Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.historical_data_service import HistoricalDataService

logger = logging.getLogger(__name__)

router = APIRouter()


class HistorySyncRequest(BaseModel):
    start_date: str  # YYYY-MM-DD
    end_date: Optional[str] = None  # YYYY-MM-DD, 默认今天
    adjust_type: str = "qfq"  # 复权类型
    stock_codes: Optional[list[str]] = None  # 指定股票代码，None 表示全市场
    use_existing: bool = False  # 如果已有活跃任务是否复用


class HistorySyncResponse(BaseModel):
    task_id: str
    status: str
    start_date: str
    end_date: str
    progress: dict
    created_at: str
    started_at: Optional[str]
    completed_at: Optional[str]
    error_messages: Optional[str]


@router.post("/history-sync", summary="启动历史数据同步")
async def start_history_sync(req: HistorySyncRequest):
    """
    启动历史数据同步任务。
    
    后台异步执行，支持断点续传和限速控制。
    """
    try:
        service = HistoricalDataService()
        
        # 设置结束日期
        end_date = req.end_date or datetime.now().strftime("%Y-%m-%d")
        
        # 启动同步任务
        task = service.start_sync(
            start_date=req.start_date,
            end_date=end_date,
            adjust_type=req.adjust_type,
            stock_codes=req.stock_codes,
            use_existing_task=req.use_existing,
        )
        
        # 获取任务状态
        status = service.get_task_status(task.task_id)
        
        return {
            "success": True,
            "message": f"History sync task started: {task.task_id}",
            "data": status,
        }
        
    except Exception as e:
        logger.error(f"Failed to start history sync: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start history sync: {str(e)}",
        )


@router.get("/history-sync/status", summary="查询最新同步任务状态")
async def get_latest_sync_status():
    """查询最新的历史同步任务状态"""
    try:
        service = HistoricalDataService()
        status = service.get_task_status()
        
        if not status:
            return {
                "success": True,
                "message": "No sync tasks found",
                "data": None,
            }
        
        return {
            "success": True,
            "data": status,
        }
        
    except Exception as e:
        logger.error(f"Failed to get sync status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get sync status: {str(e)}",
        )


@router.get("/history-sync/{task_id}", summary="查询指定任务状态")
async def get_task_status(task_id: str):
    """查询指定 ID 的同步任务状态"""
    try:
        service = HistoricalDataService()
        status = service.get_task_status(task_id)
        
        if not status:
            raise HTTPException(
                status_code=404,
                detail=f"Task not found: {task_id}",
            )
        
        return {
            "success": True,
            "data": status,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get task status: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get task status: {str(e)}",
        )


@router.get("/history-sync/history", summary="列出历史同步任务")
async def list_sync_history(limit: int = 10):
    """列出历史同步任务"""
    try:
        service = HistoricalDataService()
        tasks = service.list_tasks(limit=limit)
        
        return {
            "success": True,
            "data": tasks,
        }
        
    except Exception as e:
        logger.error(f"Failed to list sync history: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list sync history: {str(e)}",
        )


class FactorComputeRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    stock_codes: Optional[list[str]] = None  # 指定股票，None 表示全市场


@router.post("/factor-compute", summary="计算时序因子")
async def compute_factors(req: FactorComputeRequest):
    """
    从历史K线数据计算时序因子 (MA/动量/波动率/换手率)。

    同步执行，耗时较长。
    """
    try:
        from app.services.factor_compute_service import FactorComputeService
        service = FactorComputeService()
        result = service.compute_factors_for_all_stocks(
            start_date=req.start_date,
            end_date=req.end_date,
        )
        return {
            "success": True,
            "message": f"Factor computation completed: {result['computed']} stocks, {result['failed']} failed",
            "data": result,
        }
    except Exception as e:
        logger.error(f"Failed to compute factors: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to compute factors: {str(e)}",
        )
