"""
数据同步服务

负责从数据源获取行情数据并写入数据库。
"""

import logging
from datetime import datetime

import pandas as pd

from app.config import get_config
from app.database import get_db
from app.models.kline import Kline
from app.repositories import StockRepository

logger = logging.getLogger(__name__)


class DataSyncService:
    """数据同步服务"""

    def __init__(self):
        self.db = get_db()
        self.stock_repo = StockRepository(self.db)
        self.config = get_config()

    def sync_daily_data(
        self,
        trade_date: str | None = None,
        stock_codes: list[str] | None = None,
    ) -> dict:
        """
        同步日K线数据。

        Args:
            trade_date: 交易日期（YYYY-MM-DD），默认使用最新交易日
            stock_codes: 指定股票代码列表，默认同步所有股票

        Returns:
            同步结果摘要
        """
        if trade_date is None:
            trade_date = self._get_effective_trading_date()
            logger.info(f"Using effective trading date: {trade_date}")

        if stock_codes is None:
            stock_codes = self.stock_repo.get_all_stock_codes()
            logger.info(f"Syncing {len(stock_codes)} stocks for {trade_date}")

        synced = 0
        failed = 0
        errors: list[str] = []

        # Try importing DataFetcherManager from data_provider
        fetcher_manager = None
        try:
            from data_provider import DataFetcherManager

            fetcher_manager = DataFetcherManager()
        except ImportError:
            logger.warning(
                "data_provider.DataFetcherManager not available. Data sync requires the data_provider module."
            )
            return {
                "synced": 0,
                "failed": len(stock_codes),
                "errors": ["DataFetcherManager not available"],
            }

        for code in stock_codes:
            try:
                result = self._sync_single_stock(fetcher_manager, code, trade_date)
                if result:
                    synced += 1
                else:
                    failed += 1
            except Exception as e:
                failed += 1
                error_msg = f"{code}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"Failed to sync {code}: {e}")

        summary = {
            "trade_date": trade_date,
            "synced": synced,
            "failed": failed,
            "errors": errors[:20],  # Limit error list
        }
        logger.info(f"Sync completed: {synced} synced, {failed} failed for {trade_date}")
        return summary

    def _sync_single_stock(self, fetcher_manager, ts_code: str, trade_date: str) -> bool:
        """同步单只股票数据"""
        try:
            df, source = fetcher_manager.get_daily_data(ts_code)
            if df is None or df.empty:
                return False

            # Filter to target date
            target_row = df[df["trade_date"] == trade_date] if "trade_date" in df.columns else None
            if target_row is None or target_row.empty:
                return False

            row = target_row.iloc[0]
            kline = Kline(
                ts_code=ts_code,
                trade_date=trade_date,
                open=_safe_float(row.get("open")),
                high=_safe_float(row.get("high")),
                low=_safe_float(row.get("low")),
                close=_safe_float(row.get("close")),
                volume=_safe_int(row.get("volume")),
                amount=_safe_float(row.get("amount")),
                close_adj=_safe_float(row.get("close_adj")),
                adj_factor=_safe_float(row.get("adj_factor")),
                data_source=source,
            )

            # Upsert

            with self.db.get_session() as session:
                existing = session.get(Kline, (ts_code, trade_date))
                if existing:
                    session.merge(kline)
                else:
                    session.add(kline)
                session.commit()

            return True
        except Exception as e:
            logger.debug(f"Sync {ts_code} for {trade_date} failed: {e}")
            raise

    def _get_effective_trading_date(self) -> str:
        """
        获取有效交易日期。

        尝试使用 exchange_calendars，回退到当日（工作日）或前一工作日。
        """
        today = datetime.now()
        try:
            import exchange_calendars as xcals

            xshg = xcals.get_calendar("XSHG")
            if xshg.is_session(today):
                return today.strftime("%Y-%m-%d")
            # Find previous trading day
            prev = today
            for _ in range(10):
                from datetime import timedelta

                prev = prev - timedelta(days=1)
                if xshg.is_session(prev):
                    return prev.strftime("%Y-%m-%d")
        except ImportError:
            pass

        # Fallback: if today is weekday, use today; else use last Friday
        if today.weekday() < 5:
            return today.strftime("%Y-%m-%d")
        else:
            days_back = today.weekday() - 4
            last_friday = today - __import__("datetime").timedelta(days=days_back)
            return last_friday.strftime("%Y-%m-%d")


def _safe_float(val) -> float | None:
    """安全转换为 float"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _safe_int(val) -> int | None:
    """安全转换为 int"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None
