"""
市场指数 API

- GET  /index/{code}    获取指数最新行情 (默认沪深300: 000300)
"""

import logging

from fastapi import APIRouter, HTTPException, Query

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_index_manager():
    """Lazy-init DataFetcherManager singleton for index queries."""
    try:
        from data_provider.base import DataFetcherManager
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="data_provider module not available",
        )
    return DataFetcherManager()


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
    """
    try:
        from datetime import datetime, timedelta

        from data_provider.base import DataFetchError

        manager = _get_index_manager()

        # 获取指数实时行情 (通过 DataFetcherManager, 支持故障转移)
        try:
            index_df, spot_source = manager.get_index_spot_data()
        except DataFetchError as e:
            logger.error(f"Index spot data fetch failed: {e}")
            raise HTTPException(status_code=503, detail=f"Market data source unavailable: {e}")

        row = index_df[index_df["代码"] == code]

        if row.empty:
            raise HTTPException(status_code=404, detail=f"指数 {code} 不存在")

        row = row.iloc[0]
        latest = {
            "code": code,
            "name": str(row.get("名称", "")),
            "price": float(row.get("最新价", 0)),
            "change_pct": float(row.get("涨跌幅", 0)),
            "volume": float(row.get("成交量", 0)),
            "amount": float(row.get("成交额", 0)),
        }

        # 获取近N日历史走势 (用于迷你折线图)
        end_date = datetime.now().strftime("%Y-%m-%d")
        start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

        history = []
        try:
            hist_df, hist_source = manager.get_index_daily_data(code, start_date, end_date)
            if hist_df is not None and not hist_df.empty:
                # Determine date/close column names (akshare uses Chinese, tushare uses English)
                date_col = "日期" if "日期" in hist_df.columns else "trade_date"
                close_col = "收盘" if "收盘" in hist_df.columns else "close"
                for _, r in hist_df.iterrows():
                    history.append(
                        {
                            "date": str(r[date_col]),
                            "close": float(r[close_col]),
                        }
                    )
        except DataFetchError as e:
            logger.warning(f"Failed to fetch index history for {code}: {e}")
        except Exception as e:
            logger.warning(f"Unexpected error fetching index history for {code}: {e}")

        return {
            "latest": latest,
            "history": history,
        }

    except HTTPException:
        raise
    except ImportError:
        raise HTTPException(
            status_code=503,
            detail="data_provider module not available",
        )
    except Exception as e:
        logger.error(f"Market index fetch failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
