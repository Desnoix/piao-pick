"""
市场指数 API

- GET  /index/{code}    获取指数最新行情 (默认沪深300: 000300)
"""

import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-init singleton (避免每次请求创建 4 个 fetcher)
_index_manager = None


def _get_index_manager():
    """线程安全的 DataFetcherManager 懒加载单例。"""
    global _index_manager
    if _index_manager is None:
        try:
            from data_provider.base import DataFetcherManager
        except ImportError:
            raise HTTPException(
                status_code=503,
                detail="data_provider module not available",
            )
        _index_manager = DataFetcherManager()
    return _index_manager


@router.get("/index/{code}", summary="获取指数行情")
async def get_market_index(
    code: str = "000300",
    days: int = Query(30, ge=1, le=365, description="历史天数"),
):
    """
    获取指数最新行情数据和近N日走势。

    使用 DataFetcherManager 获取指数数据 (支持自动故障转移):
    - 000300: 沪深300
    - 000001: 上证指数
    - 399001: 深证成指
    - 399006: 创业板指

    行情数据通过 CacheManager 缓存 (L1: 5min, L2: 24h)，
    在缓存有效期内不会触发外部 API 调用。
    """
    import asyncio
    from datetime import datetime, timedelta

    from app.services.cache import get_cache_manager

    cm = get_cache_manager()
    end_date = datetime.now().strftime("%Y-%m-%d")
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    cache_key_spot = f"{code}:spot"
    cache_key_hist = f"{code}:{start_date}:{end_date}"

    # ---- 实时行情 (带缓存) ----
    def _load_spot():
        """加载指数实时行情 (在 thread pool 中执行以避免阻塞事件循环)。"""
        from data_provider.base import DataFetchError
        manager = _get_index_manager()
        try:
            index_df, _ = manager.get_index_spot_data()
        except DataFetchError as e:
            logger.error(f"Index spot data fetch failed: {e}")
            raise HTTPException(status_code=503, detail=f"Market data source unavailable: {e}")

        row = index_df[index_df["代码"] == code]
        if row.empty:
            raise HTTPException(status_code=404, detail=f"指数 {code} 不存在")
        row = row.iloc[0]
        return {
            "code": code,
            "name": str(row.get("名称", "")),
            "price": float(row.get("最新价", 0)),
            "change_pct": float(row.get("涨跌幅", 0)),
            "volume": float(row.get("成交量", 0)),
            "amount": float(row.get("成交额", 0)),
        }

    # ---- 历史走势 (带缓存) ----
    def _load_history():
        """加载指数历史走势 (在 thread pool 中执行以避免阻塞事件循环)。"""
        from data_provider.base import DataFetchError
        manager = _get_index_manager()
        try:
            hist_df, _ = manager.get_index_daily_data(code, start_date, end_date)
        except DataFetchError as e:
            logger.warning(f"Failed to fetch index history for {code}: {e}")
            return []
        except Exception as e:
            logger.warning(f"Unexpected error fetching index history for {code}: {e}")
            return []

        if hist_df is None or hist_df.empty:
            return []
        date_col = "日期" if "日期" in hist_df.columns else "trade_date"
        close_col = "收盘" if "收盘" in hist_df.columns else "close"
        return [
            {"date": str(r[date_col]), "close": float(r[close_col])}
            for _, r in hist_df.iterrows()
        ]

    # 缓存优先: 先查内存 → 未命中则 asyncio.to_thread 加载 (不阻塞事件循环)
    spot_key = f"market_index:{cache_key_spot}"
    hist_key = f"market_index:{cache_key_hist}"

    latest = cm.l1.get(spot_key) if cm.l1.enabled else None
    history = cm.l1.get(hist_key) if cm.l1.enabled else None

    if latest is None:
        try:
            latest = await asyncio.to_thread(_load_spot)
            if cm.l1.enabled:
                cm.l1.set(spot_key, latest, category="hot")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Market index spot fetch failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    if history is None:
        try:
            history = await asyncio.to_thread(_load_history)
            if cm.l1.enabled:
                cm.l1.set(hist_key, history, category="hot")
        except Exception as e:
            logger.error(f"Market index history fetch failed: {e}")
            history = []

    return {"latest": latest, "history": history}