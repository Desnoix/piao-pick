from __future__ import annotations

from typing import TYPE_CHECKING

from sqlmodel import select

from app.database import DatabaseManager
from app.models import Factor
from app.services.cache import get_cache_manager

if TYPE_CHECKING:
    import pandas as pd


class FactorRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_factor(self, ts_code: str, trade_date: str) -> Factor | None:
        with self.db.get_session() as session:
            return session.get(Factor, (ts_code, trade_date))

    def get_factors_by_date(self, trade_date: str) -> list[Factor]:
        with self.db.get_session() as session:
            statement = select(Factor).where(Factor.trade_date == trade_date)
            return list(session.exec(statement).all())

    def get_factors_by_code(self, ts_code: str, start_date: str, end_date: str) -> list[Factor]:
        with self.db.get_session() as session:
            statement = (
                select(Factor)
                .where(Factor.ts_code == ts_code)
                .where(Factor.trade_date >= start_date)
                .where(Factor.trade_date <= end_date)
                .order_by(Factor.trade_date)
            )
            return list(session.exec(statement).all())

    def upsert_factor(self, factor: Factor):
        with self.db.get_session() as session:
            existing = session.get(Factor, (factor.ts_code, factor.trade_date))
            if existing:
                session.merge(factor)
            else:
                session.add(factor)
            session.commit()

    def upsert_factor_batch(self, factors: list[Factor]) -> int:
        def _do():
            count = 0
            with self.db.get_session() as session:
                for factor in factors:
                    existing = session.get(Factor, (factor.ts_code, factor.trade_date))
                    if existing:
                        session.merge(factor)
                    else:
                        session.add(factor)
                    count += 1
                session.commit()
                return count

        return self.db.execute_with_retry(_do, op_name="upsert_factor_batch")

    def get_latest_trade_date(self, ts_code: str) -> str | None:
        with self.db.get_session() as session:
            statement = select(Factor.trade_date).where(Factor.ts_code == ts_code).order_by(Factor.trade_date.desc())
            return session.exec(statement).first()

    def get_factors_snapshot(self, trade_date: str) -> pd.DataFrame:
        """
        获取某交易日的全市场因子快照 (带缓存)。

        Returns:
            DataFrame, index=ts_code, columns=因子字段
        """
        import pandas as pd

        cm = get_cache_manager()

        def _loader() -> pd.DataFrame:
            factors = self.get_factors_by_date(trade_date)
            if not factors:
                return pd.DataFrame()

            records = []
            for f in factors:
                records.append(
                    {
                        "ts_code": f.ts_code,
                        "pe_ttm": f.pe_ttm,
                        "pb": f.pb,
                        "ps_ttm": f.ps_ttm,
                        "fcf_yield": f.fcf_yield,
                        "ret_20d": f.ret_20d,
                        "ret_60d_vol": f.ret_60d_vol,
                        "turnover_20d": f.turnover_20d,
                        "roe_ttm": f.roe_ttm,
                        "gross_margin": f.gross_margin,
                        "rev_growth_yoy": f.rev_growth_yoy,
                        "ear_growth_yoy": f.ear_growth_yoy,
                        "ln_market_cap": f.ln_market_cap,
                        "inst_holding_chg": f.inst_holding_chg,
                    }
                )

            df = pd.DataFrame(records)
            df = df.set_index("ts_code")
            return df

        return cm.get("factors_snapshot", trade_date, category="hot", loader_fn=_loader)

    def get_factors_range(self, start_date: str, end_date: str) -> pd.DataFrame:
        """
        批量获取日期区间内的全市场因子数据。

        Args:
            start_date: 起始日期 YYYY-MM-DD (含)
            end_date: 结束日期 YYYY-MM-DD (含)

        Returns:
            DataFrame, columns=[trade_date, ts_code, pe_ttm, pb, ...]
        """
        import pandas as pd

        with self.db.get_session() as session:
            statement = (
                select(Factor)
                .where(Factor.trade_date >= start_date)
                .where(Factor.trade_date <= end_date)
                .order_by(Factor.trade_date)
            )
            factors = session.exec(statement).all()

        if not factors:
            return pd.DataFrame()

        records = []
        for f in factors:
            records.append(
                {
                    "trade_date": f.trade_date,
                    "ts_code": f.ts_code,
                    "pe_ttm": f.pe_ttm,
                    "pb": f.pb,
                    "ps_ttm": f.ps_ttm,
                    "fcf_yield": f.fcf_yield,
                    "ret_20d": f.ret_20d,
                    "ret_60d_vol": f.ret_60d_vol,
                    "turnover_20d": f.turnover_20d,
                    "roe_ttm": f.roe_ttm,
                    "gross_margin": f.gross_margin,
                    "rev_growth_yoy": f.rev_growth_yoy,
                    "ear_growth_yoy": f.ear_growth_yoy,
                    "ln_market_cap": f.ln_market_cap,
                    "inst_holding_chg": f.inst_holding_chg,
                }
            )

        return pd.DataFrame(records)
