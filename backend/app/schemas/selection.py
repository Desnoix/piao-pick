# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional


class StockScoreSchema(BaseModel):
    rank: int
    ts_code: str
    name: Optional[str] = None
    industry: Optional[str] = None
    composite_score: float
    status: str = "OK"
    close: Optional[float] = None
    pct_change: Optional[float] = None
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    roe_ttm: Optional[float] = None
    market_cap: Optional[float] = None
    factor_snapshot: dict[str, float] = {}


class SelectionResultSchema(BaseModel):
    trade_date: str
    strategy_name: str
    universe_count: int
    filtered_count: int
    candidate_count: int
    final_count: int
    results: list[StockScoreSchema] = []
