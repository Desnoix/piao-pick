# -*- coding: utf-8 -*-
from sqlmodel import SQLModel, Field
from typing import Optional


class Kline(SQLModel, table=True):
    __tablename__ = "kline_daily"

    ts_code: str = Field(primary_key=True)
    trade_date: str = Field(primary_key=True)  # 'YYYY-MM-DD'
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[int] = None
    amount: Optional[float] = None
    close_adj: Optional[float] = None
    adj_factor: Optional[float] = None
    is_limit_up: bool = Field(default=False)
    is_limit_down: bool = Field(default=False)
    ma5: Optional[float] = None
    ma10: Optional[float] = None
    ma20: Optional[float] = None
    volume_ratio: Optional[float] = None
    turnover_rate: Optional[float] = None  # 换手率 (%)
    data_source: Optional[str] = None
