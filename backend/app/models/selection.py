# -*- coding: utf-8 -*-
from sqlmodel import SQLModel, Field
from typing import Optional


class SelectionResult(SQLModel, table=True):
    __tablename__ = "selection_results"

    strategy_id: str = Field(primary_key=True)
    ts_code: str = Field(primary_key=True)
    trade_date: str = Field(primary_key=True)
    rank: Optional[int] = None
    composite_score: Optional[float] = None
    status: Optional[str] = None  # 'OK', 'LIMIT_UP', 'SUSPENDED'
    factor_snapshot: Optional[str] = None  # JSON string
    created_at: Optional[str] = None
