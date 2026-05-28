from sqlmodel import Field, SQLModel


class Kline(SQLModel, table=True):
    __tablename__ = "kline_daily"

    ts_code: str = Field(primary_key=True)
    trade_date: str = Field(primary_key=True)  # 'YYYY-MM-DD'
    open: float | None = None
    high: float | None = None
    low: float | None = None
    close: float | None = None
    volume: int | None = None
    amount: float | None = None
    close_adj: float | None = None
    adj_factor: float | None = None
    is_limit_up: bool = Field(default=False)
    is_limit_down: bool = Field(default=False)
    ma5: float | None = None
    ma10: float | None = None
    ma20: float | None = None
    volume_ratio: float | None = None
    turnover_rate: float | None = None  # 换手率 (%)
    data_source: str | None = None
