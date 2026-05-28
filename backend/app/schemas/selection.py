from pydantic import BaseModel


class StockScoreSchema(BaseModel):
    rank: int
    ts_code: str
    name: str | None = None
    industry: str | None = None
    composite_score: float
    status: str = "OK"
    close: float | None = None
    pct_change: float | None = None
    pe_ttm: float | None = None
    pb: float | None = None
    roe_ttm: float | None = None
    market_cap: float | None = None
    factor_snapshot: dict[str, float] = {}


class SelectionResultSchema(BaseModel):
    trade_date: str
    strategy_name: str
    universe_count: int
    filtered_count: int
    candidate_count: int
    final_count: int
    results: list[StockScoreSchema] = []
