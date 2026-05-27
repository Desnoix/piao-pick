# -*- coding: utf-8 -*-
from sqlmodel import SQLModel, Field
from typing import Optional


class Factor(SQLModel, table=True):
    __tablename__ = "factor_daily"

    ts_code: str = Field(primary_key=True)
    trade_date: str = Field(primary_key=True)
    # 估值因子
    pe_ttm: Optional[float] = None
    pb: Optional[float] = None
    ps_ttm: Optional[float] = None
    fcf_yield: Optional[float] = None
    # 动量因子
    ret_20d: Optional[float] = None
    ret_60d_vol: Optional[float] = None
    turnover_20d: Optional[float] = None
    # 质量因子
    roe_ttm: Optional[float] = None
    gross_margin: Optional[float] = None
    # 成长因子
    rev_growth_yoy: Optional[float] = None
    ear_growth_yoy: Optional[float] = None
    # 其他
    ln_market_cap: Optional[float] = None
    inst_holding_chg: Optional[float] = None
    extra: Optional[str] = None  # JSON string
