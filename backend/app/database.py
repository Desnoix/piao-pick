# -*- coding: utf-8 -*-
from sqlmodel import SQLModel, create_engine, Session
from typing import Optional
import os
import logging

logger = logging.getLogger(__name__)


class DatabaseManager:
    _instance: Optional["DatabaseManager"] = None

    def __init__(self, db_path: str = "data/piao_pick.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        self.engine = create_engine(f"sqlite:///{db_path}", echo=False)
        self._init_tables()

    def _init_tables(self):
        from app.models import StockInfo, Kline, Factor, Strategy, SelectionResult  # noqa: F401
        SQLModel.metadata.create_all(self.engine)
        logger.info(f"Database initialized: {self.db_path}")

    def get_session(self) -> Session:
        return Session(self.engine)

    def init_db(self):
        from app.models import StockInfo, Kline, Factor, Strategy, SelectionResult  # noqa: F401
        SQLModel.metadata.create_all(self.engine)
        logger.info(f"Database tables created: {self.db_path}")

    @classmethod
    def get_instance(cls, db_path: str = None) -> "DatabaseManager":
        if cls._instance is None:
            if db_path is None:
                try:
                    from app.config import get_config
                    db_path = get_config().db_path
                except (ImportError, AttributeError):
                    db_path = "data/piao_pick.db"
            cls._instance = cls(db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None


def get_db() -> DatabaseManager:
    return DatabaseManager.get_instance()
