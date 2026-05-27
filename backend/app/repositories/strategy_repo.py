# -*- coding: utf-8 -*-
from sqlmodel import select
from app.models import Strategy
from typing import List, Optional
from app.database import DatabaseManager


class StrategyRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_all(self) -> List[Strategy]:
        with self.db.get_session() as session:
            statement = select(Strategy).order_by(Strategy.priority)
            return list(session.exec(statement).all())

    def get_active(self) -> List[Strategy]:
        with self.db.get_session() as session:
            statement = (
                select(Strategy)
                .where(Strategy.is_active == True)  # noqa: E712
                .order_by(Strategy.priority)
            )
            return list(session.exec(statement).all())

    def get_by_id(self, strategy_id: str) -> Optional[Strategy]:
        with self.db.get_session() as session:
            return session.get(Strategy, strategy_id)

    def get_by_name(self, name: str) -> Optional[Strategy]:
        with self.db.get_session() as session:
            statement = select(Strategy).where(Strategy.name == name)
            return session.exec(statement).first()

    def create(self, strategy: Strategy):
        with self.db.get_session() as session:
            session.add(strategy)
            session.commit()
            session.refresh(strategy)

    def update(self, strategy: Strategy):
        with self.db.get_session() as session:
            session.merge(strategy)
            session.commit()

    def delete(self, strategy_id: str) -> bool:
        with self.db.get_session() as session:
            strategy = session.get(Strategy, strategy_id)
            if strategy:
                session.delete(strategy)
                session.commit()
                return True
            return False

    def set_active(self, strategy_id: str, is_active: bool) -> bool:
        with self.db.get_session() as session:
            strategy = session.get(Strategy, strategy_id)
            if strategy:
                strategy.is_active = is_active
                session.add(strategy)
                session.commit()
                return True
            return False
