# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional


class StockInfoSchema(BaseModel):
    ts_code: str
    name: Optional[str] = None
    industry: Optional[str] = None
    list_date: Optional[str] = None
    is_st: bool = False
    is_suspended: bool = False


class KlineSchema(BaseModel):
    ts_code: str
    trade_date: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    amount: Optional[float] = None
    close_adj: Optional[float] = None
    pct_chg: Optional[float] = None
