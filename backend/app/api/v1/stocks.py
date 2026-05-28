"""
股票相关 API 端点

- GET  /          列出股票（分页）
- GET  /{ts_code} 获取单只股票信息
- GET  /{ts_code}/kline   获取K线数据
- GET  /{ts_code}/factors 获取因子数据
"""

import logging

from fastapi import APIRouter, HTTPException, Query

from app.database import get_db
from app.repositories import FactorRepository, StockRepository
from app.schemas.stock import KlineSchema, StockInfoSchema
from app.services.cache import get_cache_manager

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_stock_repo() -> StockRepository:
    return StockRepository(get_db())


def _get_factor_repo() -> FactorRepository:
    return FactorRepository(get_db())


def _factor_to_dict(f) -> dict:
    """将 Factor ORM 对象序列化为字典 (复用逻辑)。"""
    return {
        "ts_code": f.ts_code,
        "trade_date": f.trade_date,
        "pe_ttm": f.pe_ttm,
        "pb": f.pb,
        "ps_ttm": f.ps_ttm,
        "fcf_yield": f.fcf_yield,
        "ret_20d": f.ret_20d,
        "ret_60d_vol": f.ret_60d_vol,
        "turnover_20d": f.turnover_20d,
        "roe_ttm": f.roe_ttm,
        "gross_margin": f.gross_margin,
        "rev_growth_yoy": f.rev_growth_yoy,
        "ear_growth_yoy": f.ear_growth_yoy,
        "ln_market_cap": f.ln_market_cap,
        "inst_holding_chg": f.inst_holding_chg,
    }


@router.get("/", summary="列出股票")
async def list_stocks(
    offset: int = Query(0, ge=0, description="偏移量"),
    limit: int = Query(50, ge=1, le=500, description="每页数量"),
    keyword: str | None = Query(None, description="关键词（代码或名称）"),
):
    """分页获取股票列表 (利用缓存的 stock_info 全量 DataFrame)"""
    import pandas as pd

    repo = _get_stock_repo()
    df = repo.get_all_stock_info_df()  # 缓存命中 → 无 DB 查询

    if df.empty:
        return {"total": 0, "offset": offset, "limit": limit, "items": []}

    # 内存筛选
    if keyword:
        kw = keyword.lower()
        mask = df.index.str.lower().str.contains(kw) | df["name"].fillna("").str.lower().str.contains(kw)
        df = df[mask]

    total = len(df)

    # 分页
    df = df.iloc[offset : offset + limit]

    # DataFrame → dict 列表
    items = []
    for ts_code, row in df.iterrows():
        items.append({
            "ts_code": ts_code,
            "name": row.get("name"),
            "industry": row.get("industry"),
            "list_date": row.get("list_date"),
            "is_st": bool(row.get("is_st", False)),
            "is_suspended": bool(row.get("is_suspended", False)),
        })

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": items,
    }


@router.get("/{ts_code}", summary="获取股票信息")
async def get_stock(ts_code: str):
    """获取单只股票详细信息"""
    repo = _get_stock_repo()
    stock = repo.get_stock_info(ts_code)
    if not stock:
        raise HTTPException(status_code=404, detail=f"Stock {ts_code} not found")
    return StockInfoSchema.model_validate(stock, from_attributes=True).model_dump()


@router.get("/{ts_code}/kline", summary="获取K线数据")
async def get_kline(
    ts_code: str,
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=2000, description="最大返回条数"),
):
    """获取日K线数据 (利用缓存加速)"""
    import pandas as pd

    repo = _get_stock_repo()

    if start_date and end_date:
        klines = repo.get_kline_range(ts_code, start_date, end_date)
        return [KlineSchema.model_validate(k, from_attributes=True).model_dump() for k in klines]

    # 无日期范围 → 走缓存的 get_klines_by_code
    result = repo.get_klines_by_code(ts_code)

    if isinstance(result, pd.DataFrame):
        # L2 缓存命中返回 DataFrame
        if result.empty:
            return []
        df = result.sort_index().tail(limit)
        items = []
        for _, row in df.iterrows():
            items.append({
                "ts_code": ts_code,
                "trade_date": str(row.name) if row.name else "",
                "open": row.get("open"),
                "high": row.get("high"),
                "low": row.get("low"),
                "close": row.get("close"),
                "volume": row.get("volume"),
                "amount": row.get("amount"),
                "close_adj": row.get("close_adj", row.get("close")),
                "volume_ratio": row.get("volume_ratio"),
                "turnover_rate": row.get("turnover_rate"),
                "is_limit_up": bool(row.get("is_limit_up", False)),
                "is_limit_down": bool(row.get("is_limit_down", False)),
            })
        return items

    # 列表类型
    if len(result) > limit:
        result = result[-limit:]
    return [KlineSchema.model_validate(k, from_attributes=True).model_dump() for k in result]


@router.get("/{ts_code}/factors", summary="获取因子数据")
async def get_factors(
    ts_code: str,
    start_date: str | None = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: str | None = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """获取因子数据 (利用缓存加速)"""
    cm = get_cache_manager()
    repo = _get_factor_repo()

    if start_date and end_date:
        # 范围查询: 按日期段缓存
        cache_key = f"{ts_code}:{start_date}:{end_date}"

        def _loader():
            return repo.get_factors_by_code(ts_code, start_date, end_date)

        factors = cm.get("factors_by_code", cache_key, category="hot", loader_fn=_loader)
    else:
        # 最新 100 条: 按股票缓存 (数据变化频率低)
        cache_key = ts_code

        def _loader():
            with repo.db.get_session() as session:
                from sqlmodel import select
                from app.models import Factor

                statement = (
                    select(Factor)
                    .where(Factor.ts_code == ts_code)
                    .order_by(Factor.trade_date.desc())
                    .limit(100)
                )
                result = list(session.exec(statement).all())
                result.reverse()
                return result

        factors = cm.get("factors_by_code_latest", cache_key, category="hot", loader_fn=_loader)

    return [_factor_to_dict(f) for f in factors]