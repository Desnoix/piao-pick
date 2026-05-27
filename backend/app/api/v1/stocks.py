# -*- coding: utf-8 -*-
"""
股票相关 API 端点

- GET  /          列出股票（分页）
- GET  /{ts_code} 获取单只股票信息
- GET  /{ts_code}/kline   获取K线数据
- GET  /{ts_code}/factors 获取因子数据
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from app.database import get_db
from app.repositories import StockRepository, FactorRepository
from app.schemas.stock import StockInfoSchema, KlineSchema

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_stock_repo() -> StockRepository:
    return StockRepository(get_db())


def _get_factor_repo() -> FactorRepository:
    return FactorRepository(get_db())


@router.get("/", summary="列出股票")
async def list_stocks(
    offset: int = Query(0, ge=0, description="偏移量"),
    limit: int = Query(50, ge=1, le=500, description="每页数量"),
    keyword: Optional[str] = Query(None, description="关键词（代码或名称）"),
):
    """分页获取股票列表"""
    repo = _get_stock_repo()
    with repo.db.get_session() as session:
        from sqlmodel import select
        from app.models import StockInfo

        statement = select(StockInfo)
        if keyword:
            statement = statement.where(
                StockInfo.name.contains(keyword) | StockInfo.ts_code.contains(keyword)
            )
        # count
        from sqlmodel import func as sqlfunc

        count_stmt = select(sqlfunc.count()).select_from(StockInfo)
        if keyword:
            count_stmt = count_stmt.where(
                StockInfo.name.contains(keyword) | StockInfo.ts_code.contains(keyword)
            )
        total = session.exec(count_stmt).one()

        statement = statement.offset(offset).limit(limit)
        stocks = list(session.exec(statement).all())

    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "items": [StockInfoSchema.model_validate(s, from_attributes=True).model_dump() for s in stocks],
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
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
    limit: int = Query(500, ge=1, le=2000, description="最大返回条数"),
):
    """获取日K线数据"""
    repo = _get_stock_repo()
    if start_date and end_date:
        klines = repo.get_kline_range(ts_code, start_date, end_date)
    else:
        # Use a wide range and limit via Kline query
        from sqlmodel import select
        from app.models import Kline

        with repo.db.get_session() as session:
            statement = (
                select(Kline)
                .where(Kline.ts_code == ts_code)
                .order_by(Kline.trade_date.desc())
                .limit(limit)
            )
            klines = list(session.exec(statement).all())
        klines.reverse()

    return [KlineSchema.model_validate(k, from_attributes=True).model_dump() for k in klines]


@router.get("/{ts_code}/factors", summary="获取因子数据")
async def get_factors(
    ts_code: str,
    start_date: Optional[str] = Query(None, description="开始日期 YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="结束日期 YYYY-MM-DD"),
):
    """获取因子数据"""
    repo = _get_factor_repo()
    if start_date and end_date:
        factors = repo.get_factors_by_code(ts_code, start_date, end_date)
    else:
        # Get latest 100 records
        with repo.db.get_session() as session:
            from sqlmodel import select
            from app.models import Factor

            statement = (
                select(Factor)
                .where(Factor.ts_code == ts_code)
                .order_by(Factor.trade_date.desc())
                .limit(100)
            )
            factors = list(session.exec(statement).all())
        factors.reverse()

    return [
        {
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
        for f in factors
    ]
