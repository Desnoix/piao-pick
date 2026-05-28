"""
选股 API 端点

- POST /run                    运行选股
- GET  /prepare/status/{date}  查询数据准备状态
- GET  /results                获取选股结果列表
- GET  /results/{date}         获取某日选股结果
"""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.database import get_db
from app.repositories import SelectionRepository, StrategyRepository
from app.repositories.factor_repo import FactorRepository

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_selection_repo() -> SelectionRepository:
    return SelectionRepository(get_db())


def _get_strategy_repo() -> StrategyRepository:
    return StrategyRepository(get_db())


# -- Request models --


class SelectionRunRequest(BaseModel):
    strategy_name: str | None = None
    strategy_id: str | None = None  # deprecated, kept for backward compat
    trade_date: str | None = None


# -- Endpoints --


@router.post("/run", summary="运行选股")
async def run_selection(req: SelectionRunRequest):
    """
    触发选股流程。

    如果数据库中没有因子数据，自动触发全市场数据同步。
    通过 SelectionService 调用 SelectionPipeline 执行选股。
    """
    from app.repositories import FactorRepository
    from app.services.selection_service import SelectionService

    strategy_name = req.strategy_name
    strategy_id = req.strategy_id

    # Resolve strategy_name from strategy_id if needed (backward compat)
    if strategy_name is None and strategy_id is not None:
        strategy_repo = _get_strategy_repo()
        db_strategy = strategy_repo.get_by_id(strategy_id)
        if db_strategy is not None:
            strategy_name = db_strategy.name
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Strategy not found by id: {strategy_id}",
            )

    if strategy_name is None:
        raise HTTPException(
            status_code=400,
            detail="strategy_name is required",
        )

    logger.info(f"Selection requested: strategy={strategy_name}, date={req.trade_date}")

    # Auto-prepare data if factor table is empty
    trade_date = req.trade_date
    if trade_date is None:
        from app.core.trading_calendar import get_effective_trading_date

        trade_date = get_effective_trading_date().isoformat()

    db = get_db()
    factor_repo = FactorRepository(db)
    existing_factors = factor_repo.get_factors_by_date(trade_date)
    if not existing_factors:
        from app.services._prepare_state import (
            cleanup_old,
            is_preparing,
            set_done,
            set_failed,
            set_preparing,
        )

        # 如果已有同日期任务在跑, 返回 202 让前端轮询
        if is_preparing(trade_date):
            return JSONResponse(
                status_code=202,
                content={
                    "status": "preparing",
                    "trade_date": trade_date,
                    "message": "数据准备进行中, 请稍后重试",
                },
            )

        logger.info(f"因子表为空 (日期 {trade_date}), 异步触发全市场数据准备...")
        set_preparing(trade_date)
        cleanup_old()

        async def _run_prepare():
            from app.services.data_preparation import DataPreparationService

            try:
                prep_db = get_db()
                prep_service = DataPreparationService(prep_db)
                prep_result = await asyncio.to_thread(prep_service.prepare, trade_date=trade_date)
                if prep_result.get("error"):
                    set_failed(trade_date, prep_result["error"])
                    logger.error(f"数据准备失败: {prep_result['error']}")
                else:
                    set_done(trade_date, prep_result)
                    logger.info(f"数据准备完成: {prep_result}")
            except Exception as e:
                set_failed(trade_date, str(e))
                logger.error(f"数据准备异常: {e}", exc_info=True)

        asyncio.create_task(_run_prepare())

        return JSONResponse(
            status_code=202,
            content={
                "status": "preparing",
                "trade_date": trade_date,
                "message": "数据准备已启动, 预计 10-60 秒完成, 请轮询状态",
            },
        )

    try:
        service = SelectionService()
        result = service.run_selection(
            strategy_name=strategy_name,
            trade_date=trade_date,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Selection failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Selection failed: {str(e)}",
        )


@router.get("/prepare/status/{trade_date}", summary="查询数据准备状态")
async def get_prepare_status(trade_date: str):
    """
    查询某日期数据准备任务的当前状态。

    返回值:
        status: "preparing" | "done" | "failed" | "unknown"
    """
    from app.services._prepare_state import get_status

    task = get_status(trade_date)
    if task is None:
        # 检查数据库中是否已有该日因子数据
        factor_repo = FactorRepository(get_db())
        existing = factor_repo.get_factors_by_date(trade_date)
        if existing:
            return {
                "status": "done",
                "trade_date": trade_date,
                "factor_count": len(existing),
            }
        return {
            "status": "unknown",
            "trade_date": trade_date,
        }

    result = {
        "status": task["status"],
        "trade_date": trade_date,
    }

    if task.get("result"):
        result["result"] = task["result"]
    if task.get("error"):
        result["error"] = task["error"]

    return result


@router.get("/results", summary="获取选股结果列表")
async def list_selection_results(
    strategy_id: str | None = Query(None, description="策略ID"),
    trade_date: str | None = Query(None, description="交易日期 YYYY-MM-DD"),
    limit: int = Query(100, ge=1, le=1000, description="最大返回条数"),
):
    """获取选股结果"""
    repo = _get_selection_repo()

    if trade_date:
        results = (
            repo.get_by_strategy_date(strategy_id=strategy_id or "", trade_date=trade_date)
            if strategy_id
            else _get_all_results_by_date(repo, trade_date)
        )
    elif strategy_id:
        latest_date = repo.get_latest_date(strategy_id)
        if not latest_date:
            return []
        results = repo.get_by_strategy_date(strategy_id, latest_date)
    else:
        results = []

    return [_serialize_result(r) for r in results]


@router.get("/results/{trade_date}", summary="获取某日选股结果")
async def get_selection_results_by_date(
    trade_date: str,
    strategy_id: str | None = Query(None, description="策略ID"),
):
    """获取某个交易日的选股结果"""
    repo = _get_selection_repo()

    if strategy_id:
        results = repo.get_by_strategy_date(strategy_id, trade_date)
    else:
        results = _get_all_results_by_date(repo, trade_date)

    if not results:
        raise HTTPException(
            status_code=404,
            detail=f"No selection results for date {trade_date}",
        )

    return [_serialize_result(r) for r in results]


def _get_all_results_by_date(repo: SelectionRepository, trade_date: str):
    """获取某日所有策略的选股结果"""
    strategy_repo = _get_strategy_repo()
    strategies = strategy_repo.get_all()
    results = []
    for s in strategies:
        results.extend(repo.get_by_strategy_date(s.id, trade_date))
    return results


def _serialize_result(r):
    """序列化选股结果"""
    import json

    factor_snapshot = {}
    if r.factor_snapshot:
        try:
            factor_snapshot = json.loads(r.factor_snapshot)
        except (json.JSONDecodeError, TypeError):
            factor_snapshot = {}

    return {
        "strategy_id": r.strategy_id,
        "ts_code": r.ts_code,
        "trade_date": r.trade_date,
        "rank": r.rank,
        "composite_score": r.composite_score,
        "status": r.status,
        "factor_snapshot": factor_snapshot,
        "created_at": r.created_at,
    }
