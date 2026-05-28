from sqlmodel import Field, SQLModel


class SelectionResult(SQLModel, table=True):
    __tablename__ = "selection_results"

    strategy_id: str = Field(primary_key=True)
    ts_code: str = Field(primary_key=True)
    trade_date: str = Field(primary_key=True)
    rank: int | None = None
    composite_score: float | None = None
    status: str | None = None  # 'OK', 'LIMIT_UP', 'SUSPENDED'
    factor_snapshot: str | None = None  # JSON string
    created_at: str | None = None
