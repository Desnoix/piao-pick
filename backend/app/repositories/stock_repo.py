from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select

from app.database import DatabaseManager
from app.models import Kline, StockInfo
from app.services.cache import get_cache_manager

if TYPE_CHECKING:
    import pandas as pd


class StockRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_all_stock_codes(self) -> list[str]:
        with self.db.get_session() as session:
            statement = select(StockInfo.ts_code)
            results = session.exec(statement).all()
            return list(results)

    def get_stock_info(self, ts_code: str) -> StockInfo | None:
        with self.db.get_session() as session:
            return session.get(StockInfo, ts_code)

    def get_stock_info_list(self, ts_codes: list[str]) -> list[StockInfo]:
        with self.db.get_session() as session:
            statement = select(StockInfo).where(StockInfo.ts_code.in_(ts_codes))
            return list(session.exec(statement).all())

    def upsert_stock_info(self, stock: StockInfo):
        with self.db.get_session() as session:
            existing = session.get(StockInfo, stock.ts_code)
            if existing:
                session.merge(stock)
            else:
                session.add(stock)
            session.commit()

    def upsert_stock_info_batch(self, stocks: list[StockInfo]) -> int:
        def _do():
            count = 0
            with self.db.get_session() as session:
                for stock in stocks:
                    existing = session.get(StockInfo, stock.ts_code)
                    if existing:
                        session.merge(stock)
                    else:
                        session.add(stock)
                    count += 1
                session.commit()
                return count

        return self.db.execute_with_retry(_do, op_name="upsert_stock_info_batch")

    def get_kline(self, ts_code: str, trade_date: str) -> Kline | None:
        with self.db.get_session() as session:
            statement = select(Kline).where(Kline.ts_code == ts_code, Kline.trade_date == trade_date)
            return session.exec(statement).first()

    def get_klines_by_date(self, trade_date: str) -> list[Kline]:
        """获取某交易日的所有股票K线数据"""
        with self.db.get_session() as session:
            statement = select(Kline).where(Kline.trade_date == trade_date)
            return list(session.exec(statement).all())

    def get_kline_range(self, ts_code: str, start_date: str, end_date: str) -> list[Kline]:
        with self.db.get_session() as session:
            statement = (
                select(Kline)
                .where(Kline.ts_code == ts_code)
                .where(Kline.trade_date >= start_date)
                .where(Kline.trade_date <= end_date)
                .order_by(Kline.trade_date)
            )
            return list(session.exec(statement).all())

    def get_klines_by_code(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Kline] | pd.DataFrame:
        """
        获取某只股票的K线数据 (支持日期范围过滤)。

        Args:
            ts_code: 股票代码
            start_date: 开始日期 (可选)
            end_date: 结束日期 (可选)

        Returns:
            Kline 对象列表, 按 trade_date 升序
            或 DataFrame (当 start_date 和 end_date 都为 None 时)
        """
        import pandas as pd

        cm = get_cache_manager()

        # 无日期范围时，返回全量历史数据 (走 L2 Parquet)
        if start_date is None and end_date is None:
            df = cm.l2.get(f"kline_history:{ts_code}")
            if df is not None:
                # L2 命中, 转回 Kline 对象 (或直接返回 DataFrame 视调用方而定)
                cm.l1.set(f"kline_history:{ts_code}", df, category="hot")
                return df  # 调用方需适配 DataFrame

        # 有日期范围时，走缓存 + DB
        range_key = f"{ts_code}:{start_date or 'min'}:{end_date or 'max'}"

        def _loader():
            with self.db.get_session() as session:
                statement = select(Kline).where(Kline.ts_code == ts_code)
                if start_date:
                    statement = statement.where(Kline.trade_date >= start_date)
                if end_date:
                    statement = statement.where(Kline.trade_date <= end_date)
                statement = statement.order_by(Kline.trade_date)
                return list(session.exec(statement).all())

        return cm.get("kline_history", range_key, category="hot", loader_fn=_loader)

    def has_kline_data(self, ts_code: str, trade_date: str) -> bool:
        return self.get_kline(ts_code, trade_date) is not None

    def upsert_kline_batch(self, klines: list[Kline]) -> int:
        def _do():
            count = 0
            with self.db.get_session() as session:
                for kline in klines:
                    existing = session.get(Kline, (kline.ts_code, kline.trade_date))
                    if existing:
                        session.merge(kline)
                    else:
                        session.add(kline)
                    count += 1
                session.commit()
                return count

        return self.db.execute_with_retry(_do, op_name="upsert_kline_batch")

    def get_all_stock_info_df(self) -> pd.DataFrame:
        """
        获取全市场股票基本信息 DataFrame (带缓存)。

        Returns:
            DataFrame, index=ts_code, columns=name, industry, is_st, is_suspended, ...
        """
        import pandas as pd

        cm = get_cache_manager()

        def _loader() -> pd.DataFrame:
            with self.db.get_session() as session:
                statement = select(StockInfo)
                stocks = session.exec(statement).all()

            if not stocks:
                return pd.DataFrame()

            records = []
            for s in stocks:
                records.append(
                    {
                        "ts_code": s.ts_code,
                        "name": s.name,
                        "industry": s.industry,
                        "list_date": s.list_date,
                        "is_st": s.is_st,
                        "is_suspended": s.is_suspended,
                    }
                )

            df = pd.DataFrame(records)
            df = df.set_index("ts_code")
            return df

        return cm.get("stock_info", "all", category="config", loader_fn=_loader)

    def get_kline_snapshot(self, trade_date: str) -> pd.DataFrame:
        """
        获取某交易日的全市场行情快照 (带缓存)。

        Returns:
            DataFrame, index=ts_code, columns=open, high, low, close, close_adj, volume, amount,
                        is_limit_up, is_limit_down, turnover_rate
        """
        import pandas as pd

        cm = get_cache_manager()

        def _loader() -> pd.DataFrame:
            with self.db.get_session() as session:
                statement = select(Kline).where(Kline.trade_date == trade_date)
                klines = session.exec(statement).all()

            if not klines:
                return pd.DataFrame()

            records = []
            for k in klines:
                records.append(
                    {
                        "ts_code": k.ts_code,
                        "open": k.open,
                        "high": k.high,
                        "low": k.low,
                        "close": k.close,
                        "close_adj": k.close_adj,
                        "volume": k.volume,
                        "amount": k.amount,
                        "is_limit_up": k.is_limit_up,
                        "is_limit_down": k.is_limit_down,
                        "turnover_rate": k.turnover_rate,
                    }
                )

            df = pd.DataFrame(records)
            df = df.set_index("ts_code")
            return df

        return cm.get("kline_snapshot", trade_date, category="hot", loader_fn=_loader)

    def get_index_kline_range(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
    ) -> pd.DataFrame:
        """
        获取指数 K 线数据并返回 DataFrame。

        Args:
            ts_code: 指数代码 (如 "000300")
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            DataFrame with columns: [trade_date, close], sorted by date
        """
        import pandas as pd

        with self.db.get_session() as session:
            statement = (
                select(Kline)
                .where(Kline.ts_code == ts_code)
                .where(Kline.trade_date >= start_date)
                .where(Kline.trade_date <= end_date)
                .order_by(Kline.trade_date)
            )
            klines = list(session.exec(statement).all())

        if not klines:
            return pd.DataFrame(columns=["trade_date", "close"])

        return pd.DataFrame([{"trade_date": k.trade_date, "close": k.close} for k in klines])
