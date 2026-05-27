# -*- coding: utf-8 -*-
from sqlmodel import SQLModel, Field
from typing import Optional


class StockInfo(SQLModel, table=True):
    __tablename__ = "stock_info"

    ts_code: str = Field(primary_key=True)
    name: Optional[str] = None
    industry: Optional[str] = None
    list_date: Optional[str] = None  # 'YYYY-MM-DD'
    is_st: bool = Field(default=False)
    is_suspended: bool = Field(default=False)
    updated_at: Optional[str] = None
