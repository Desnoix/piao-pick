# -*- coding: utf-8 -*-
from sqlmodel import select
from app.models import StockInfo, Kline
from typing import List, Optional
from app.database import DatabaseManager


class StockRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_all_stock_codes(self) -> List[str]:
        with self.db.get_session() as session:
            statement = select(StockInfo.ts_code)
            results = session.exec(statement).all()
            return list(results)

    def get_stock_info(self, ts_code: str) -> Optional[StockInfo]:
        with self.db.get_session() as session:
            return session.get(StockInfo, ts_code)

    def get_stock_info_list(self, ts_codes: List[str]) -> List[StockInfo]:
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

    def upsert_stock_info_batch(self, stocks: List[StockInfo]) -> int:
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

    def get_kline(self, ts_code: str, trade_date: str) -> Optional[Kline]:
        with self.db.get_session() as session:
            statement = select(Kline).where(
                Kline.ts_code == ts_code, Kline.trade_date == trade_date
            )
            return session.exec(statement).first()

    def get_klines_by_date(self, trade_date: str) -> List[Kline]:
        """获取某交易日的所有股票K线数据"""
        with self.db.get_session() as session:
            statement = (
                select(Kline)
                .where(Kline.trade_date == trade_date)
            )
            return list(session.exec(statement).all())

    def get_kline_range(self, ts_code: str, start_date: str, end_date: str) -> List[Kline]:
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
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
    ) -> List[Kline]:
        """
        获取某只股票的K线数据 (支持日期范围过滤)。

        Args:
            ts_code: 股票代码
            start_date: 开始日期 (可选)
            end_date: 结束日期 (可选)

        Returns:
            Kline 对象列表, 按 trade_date 升序
        """
        with self.db.get_session() as session:
            statement = select(Kline).where(Kline.ts_code == ts_code)
            if start_date:
                statement = statement.where(Kline.trade_date >= start_date)
            if end_date:
                statement = statement.where(Kline.trade_date <= end_date)
            statement = statement.order_by(Kline.trade_date)
            return list(session.exec(statement).all())

    def has_kline_data(self, ts_code: str, trade_date: str) -> bool:
        return self.get_kline(ts_code, trade_date) is not None

    def upsert_kline_batch(self, klines: List[Kline]) -> int:
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

    def get_all_stock_info_df(self) -> "pd.DataFrame":
        """
        获取全市场股票基本信息 DataFrame。

        Returns:
            DataFrame, index=ts_code, columns=name, industry, is_st, is_suspended, ...
        """
        import pandas as pd

        with self.db.get_session() as session:
            statement = select(StockInfo)
            stocks = session.exec(statement).all()

        if not stocks:
            return pd.DataFrame()

        records = []
        for s in stocks:
            records.append({
                "ts_code": s.ts_code,
                "name": s.name,
                "industry": s.industry,
                "list_date": s.list_date,
                "is_st": s.is_st,
                "is_suspended": s.is_suspended,
            })

        df = pd.DataFrame(records)
        df = df.set_index("ts_code")
        return df

    def get_kline_snapshot(self, trade_date: str) -> "pd.DataFrame":
        """
        获取某交易日的全市场行情快照。

        Returns:
            DataFrame, index=ts_code, columns=open, high, low, close, close_adj, volume, amount
        """
        import pandas as pd

        with self.db.get_session() as session:
            statement = select(Kline).where(Kline.trade_date == trade_date)
            klines = session.exec(statement).all()

        if not klines:
            return pd.DataFrame()

        records = []
        for k in klines:
            records.append({
                "ts_code": k.ts_code,
                "open": k.open,
                "high": k.high,
                "low": k.low,
                "close": k.close,
                "close_adj": k.close_adj,
                "volume": k.volume,
                "amount": k.amount,
            })

        df = pd.DataFrame(records)
        df = df.set_index("ts_code")
        return df
