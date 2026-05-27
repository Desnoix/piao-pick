# -*- coding: utf-8 -*-
"""
Backtest repository stub.
Full implementation deferred to Phase 4 (backtesting).
"""
from typing import List, Optional, Dict, Any
from app.database import DatabaseManager


class BacktestRepository:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_backtest_result(self, strategy_id: str, start_date: str, end_date: str) -> Optional[Dict[str, Any]]:
        # Stub: will be implemented when backtest tables are created
        return None

    def save_backtest_result(self, result: Dict[str, Any]) -> None:
        # Stub: will be implemented when backtest tables are created
        pass

    def list_backtests(self, strategy_id: Optional[str] = None) -> List[Dict[str, Any]]:
        # Stub: will be implemented when backtest tables are created
        return []
