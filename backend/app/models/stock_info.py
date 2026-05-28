from sqlmodel import Field, SQLModel


class StockInfo(SQLModel, table=True):
    __tablename__ = "stock_info"

    ts_code: str = Field(primary_key=True)
    name: str | None = None
    industry: str | None = None
    list_date: str | None = None  # 'YYYY-MM-DD'
    is_st: bool = Field(default=False)
    is_suspended: bool = Field(default=False)
    updated_at: str | None = None
