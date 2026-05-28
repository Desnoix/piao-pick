from pydantic import BaseModel


class StockInfoSchema(BaseModel):
    ts_code: str
    name: str | None = None
    industry: str | None = None
    list_date: str | None = None
    is_st: bool = False
    is_suspended: bool = False


class KlineSchema(BaseModel):
    ts_code: str
    trade_date: str
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None
    close_adj: float | None = None
    pct_chg: float | None = None
