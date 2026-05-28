from sqlmodel import Field, SQLModel


class Factor(SQLModel, table=True):
    __tablename__ = "factor_daily"

    ts_code: str = Field(primary_key=True)
    trade_date: str = Field(primary_key=True)
    # 估值因子
    pe_ttm: float | None = None
    pb: float | None = None
    ps_ttm: float | None = None
    fcf_yield: float | None = None
    # 动量因子
    ret_20d: float | None = None
    ret_60d_vol: float | None = None
    turnover_20d: float | None = None
    # 质量因子
    roe_ttm: float | None = None
    gross_margin: float | None = None
    # 成长因子
    rev_growth_yoy: float | None = None
    ear_growth_yoy: float | None = None
    # 其他
    ln_market_cap: float | None = None
    inst_holding_chg: float | None = None
    extra: str | None = None  # JSON string
