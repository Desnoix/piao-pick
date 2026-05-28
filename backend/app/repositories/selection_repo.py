from sqlmodel import select

from app.database import DatabaseManager
from app.models import SelectionResult


class SelectionRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_by_strategy_date(self, strategy_id: str, trade_date: str) -> list[SelectionResult]:
        with self.db.get_session() as session:
            statement = (
                select(SelectionResult)
                .where(SelectionResult.strategy_id == strategy_id)
                .where(SelectionResult.trade_date == trade_date)
                .order_by(SelectionResult.rank)
            )
            return list(session.exec(statement).all())

    def get_by_code_date(self, ts_code: str, trade_date: str) -> list[SelectionResult]:
        with self.db.get_session() as session:
            statement = (
                select(SelectionResult)
                .where(SelectionResult.ts_code == ts_code)
                .where(SelectionResult.trade_date == trade_date)
            )
            return list(session.exec(statement).all())

    def get_latest_date(self, strategy_id: str) -> str | None:
        with self.db.get_session() as session:
            statement = (
                select(SelectionResult.trade_date)
                .where(SelectionResult.strategy_id == strategy_id)
                .order_by(SelectionResult.trade_date.desc())
            )
            return session.exec(statement).first()

    def upsert_batch(self, results: list[SelectionResult]) -> int:
        def _do():
            count = 0
            with self.db.get_session() as session:
                for result in results:
                    existing = session.get(
                        SelectionResult,
                        (result.strategy_id, result.ts_code, result.trade_date),
                    )
                    if existing:
                        session.merge(result)
                    else:
                        session.add(result)
                    count += 1
                session.commit()
                return count

        return self.db.execute_with_retry(_do, op_name="upsert_selection_batch")

    def delete_by_strategy_date(self, strategy_id: str, trade_date: str) -> int:
        def _do():
            with self.db.get_session() as session:
                statement = select(SelectionResult).where(
                    SelectionResult.strategy_id == strategy_id,
                    SelectionResult.trade_date == trade_date,
                )
                results = session.exec(statement).all()
                count = len(results)
                for result in results:
                    session.delete(result)
                session.commit()
                return count

        return self.db.execute_with_retry(_do, op_name="delete_selection_by_date")

    def get_history(self, strategy_id: str, ts_code: str) -> list[SelectionResult]:
        with self.db.get_session() as session:
            statement = (
                select(SelectionResult)
                .where(SelectionResult.strategy_id == strategy_id)
                .where(SelectionResult.ts_code == ts_code)
                .order_by(SelectionResult.trade_date.desc())
            )
            return list(session.exec(statement).all())
