"""
数据状态与同步 API 端点

- GET  /status           数据库状态
- POST /sync             手动触发数据同步
- GET  /trade-calendar   获取交易日历
"""

import logging
import os
from datetime import datetime, timedelta

from fastapi import APIRouter, Query
from pydantic import BaseModel

from app.database import get_db
from app.repositories import StockRepository
from app.services.cache import get_cache_manager

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_stock_repo() -> StockRepository:
    return StockRepository(get_db())


class SyncRequest(BaseModel):
    trade_date: str | None = None
    stock_codes: list[str] | None = None


class SyncResponse(BaseModel):
    success: bool
    message: str
    trade_date: str | None = None
    synced_count: int = 0
    failed_count: int = 0
    errors: list[str] = []


@router.get("/status", summary="数据库状态")
async def get_data_status():
    """获取数据库状态和数据概览 (缓存 5 分钟, 避免重复全表扫描)"""
    cm = get_cache_manager()

    def _loader():
        """加载数据库概览 (在缓存未命中时执行)"""
        db = get_db()
        repo = _get_stock_repo()

        # DB file size
        db_size_mb = None
        if os.path.exists(db.db_path):
            db_size_mb = round(os.path.getsize(db.db_path) / (1024 * 1024), 2)

        # Stock count — use cached method
        from app.repositories import StockRepository as SR
        repo_cached = SR(db)
        df = repo_cached.get_all_stock_info_df()
        stock_count = len(df) if df is not None else len(repo.get_all_stock_codes())

        # Latest kline date — single session, single query
        latest_kline_date = None
        latest_factor_date = None
        with db.get_session() as session:
            from sqlmodel import select
            from app.models import Kline, Factor

            latest_kline_date = session.exec(
                select(Kline.trade_date).order_by(Kline.trade_date.desc()).limit(1)
            ).first()

            latest_factor_date = session.exec(
                select(Factor.trade_date).order_by(Factor.trade_date.desc()).limit(1)
            ).first()

        return {
            "db_path": db.db_path,
            "db_size_mb": db_size_mb,
            "stock_count": stock_count,
            "latest_kline_date": latest_kline_date,
            "latest_factor_date": latest_factor_date,
        }

    return cm.get("data_status", "overview", category="hot", loader_fn=_loader)


@router.post("/sync", summary="手动触发数据同步")
async def sync_data(req: SyncRequest):
    """
    手动触发数据同步。

    使用 ak.stock_zh_a_spot_em() 一次拉取全A股快照，
    写入 stock_info / kline_daily / factor_daily。
    """
    import asyncio

    try:
        from app.services.data_preparation import DataPreparationService

        db = get_db()
        service = DataPreparationService(db)
        # 同步到线程池以免阻塞事件循环
        result = await asyncio.to_thread(service.prepare, trade_date=req.trade_date)
        return SyncResponse(
            success=True,
            message=(
                f"同步完成: {result.get('stock_count', 0)} 只股票, "
                f"{result.get('synced', 0)} 条K线, "
                f"{result.get('factor_count', 0)} 条因子"
            ),
            trade_date=result.get("trade_date"),
            synced_count=result.get("synced", 0),
            failed_count=result.get("failed", 0),
            errors=[],
        )
    except Exception as e:
        logger.error(f"Sync failed: {e}", exc_info=True)
        return SyncResponse(
            success=False,
            message=f"Sync failed: {str(e)}",
            trade_date=req.trade_date,
        )


@router.get("/trade-calendar", summary="获取交易日历")
async def get_trade_calendar(
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """
    获取交易日历。

    尝试使用 exchange_calendars 库，
    回退到简单的工作日计算。
    """
    if start_date is None:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if end_date is None:
        end_date = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")

    cm = get_cache_manager()
    cache_key = f"{start_date}:{end_date}"

    def _loader():
        try:
            import exchange_calendars as xcals

            xshg = xcals.get_calendar("XSHG")
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(end_date, "%Y-%m-%d")
            sessions = xshg.sessions_in_range(start, end)
            trading_days = [s.strftime("%Y-%m-%d") for s in sessions]
        except ImportError:
            trading_days = _get_weekdays(start_date, end_date)
        except Exception as e:
            logger.warning(f"exchange_calendars failed, using weekday fallback: {e}")
            trading_days = _get_weekdays(start_date, end_date)
        return trading_days

    trading_days = cm.get("trade_calendar", cache_key, category="config", loader_fn=_loader)

    return {
        "start_date": start_date,
        "end_date": end_date,
        "trading_days": trading_days,
        "count": len(trading_days),
    }


def _get_weekdays(start_date: str, end_date: str) -> list[str]:
    """简单的工作日计算（不含节假日）"""
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")
    days = []
    current = start
    while current <= end:
        if current.weekday() < 5:  # Mon-Fri
            days.append(current.strftime("%Y-%m-%d"))
        current += timedelta(days=1)
    return days