"""
基本面数据同步任务 — 定期将 AKShare 财务数据写入 factor_daily。
Fundamental data sync task: periodically persist AKShare financial data to factor_daily.

同步的因子 (Synced factors):
- roe_ttm (质量) — from stock_yjbb_em
- rev_growth_yoy (成长) — from stock_yjbb_em
- ear_growth_yoy (成长) — from stock_yjbb_em
- gross_margin (质量) — from stock_financial_analysis_indicator (per-stock, slow)
- fcf_yield (价值) — from stock_cash_flow_sheet_by_report_em (per-stock, slow)
- ps_ttm (价值) — from stock_yjbb_em + total_mv
- inst_holding_chg (规模) — from stock_institute_hold_detail (per-stock, low coverage)

策略:
- 批量接口 (stock_yjbb_em): 全市场一次获取，高效
- 单股接口: 逐股调用+限流，放入独立同步任务可选执行
"""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd

from app.database import DatabaseManager, get_db
from app.models.factor import Factor
from app.services.fundamental_service import FundamentalService

logger = logging.getLogger(__name__)


def _latest_report_date(ref_date: date) -> str:
    """
    计算给定日期之前最近的财报发布日期。
    Calculate the latest financial report date before ref_date.

    财报发布规律:
    - 年报 (Q4): 4月30日前
    - 一季报 (Q1): 4月30日前
    - 半年报 (Q2): 8月31日前
    - 三季报 (Q3): 10月31日前

    为安全起见，假设财报滞后 2 个月发布。

    Returns:
        "YYYYMMDD" 格式的报告期日期
    """
    year = ref_date.year
    month = ref_date.month

    if month >= 11:
        # 11-12月: 三季报可用 (当年Q3 = 9月30日)
        return f"{year}0930"
    elif month >= 9:
        # 9-10月: 半年报可用 (当年Q2 = 6月30日)
        return f"{year}0630"
    elif month >= 5:
        # 5-8月: 一季报可用 (当年Q1 = 3月31日)
        return f"{year}0331"
    else:
        # 1-4月: 去年三季报可用 (去年Q3 = 9月30日)
        return f"{year - 1}0930"


def sync_fundamental_factors(
    trade_date: str | None = None,
    sync_per_stock: bool = False,
) -> dict:
    """
    同步基本面因子到 factor_daily 表。

    默认只执行批量接口 (yjbb_em)，高效获取全市场数据。
    可选启用单股接口 (sync_per_stock=True)，同步毛利率、FCF等。

    Args:
        trade_date: 交易日期 YYYY-MM-DD，默认今天
        sync_per_stock: 是否执行单股接口 (慢，5000只 x 0.5s ≈ 42分钟)

    Returns:
        dict with synced counts: {"batch": int, "per_stock": int, "failed": int}
    """
    if trade_date is None:
        ref_date = date.today()
    else:
        try:
            ref_date = date.fromisoformat(trade_date)
        except ValueError:
            logger.error("Invalid trade_date format: %s (expected YYYY-MM-DD)", trade_date)
            return {"batch": 0, "per_stock": 0, "failed": 1, "error": "invalid date"}

    report_date = _latest_report_date(ref_date)
    logger.info("sync_fundamental: using report_date=%s for trade_date=%s", report_date, ref_date)

    fundamental = FundamentalService()
    db = get_db()

    # === Batch sync: stock_yjbb_em ===
    yjbb = fundamental.fetch_yjbb_batch(report_date)
    batch_count = 0
    if yjbb is not None and not yjbb.empty:
        batch_count = _sync_yjbb_to_factor(db, yjbb, ref_date.isoformat())
        logger.info("sync_fundamental: batch synced %d records", batch_count)
    else:
        logger.warning("sync_fundamental: yjbb_em returned no data")

    # === Per-stock sync (optional, slow) ===
    per_stock_count = 0
    if sync_per_stock:
        per_stock_count = _sync_per_stock_factors(db, fundamental, ref_date, yjbb)
        logger.info("sync_fundamental: per-stock synced %d records", per_stock_count)

    return {
        "trade_date": ref_date.isoformat(),
        "report_date": report_date,
        "batch": batch_count,
        "per_stock": per_stock_count,
        "failed": 0,
    }


def _sync_yjbb_to_factor(
    db: DatabaseManager,
    yjbb_df: pd.DataFrame,
    trade_date: str,
) -> int:
    """
    将 yjbb 批量数据写入 factor_daily。

    更新字段: rev_growth_yoy, ear_growth_yoy, roe_ttm (from_batch API).
    """
    factors_to_upsert: list[Factor] = []

    for _, row in yjbb_df.iterrows():
        ts_code = str(row.get("ts_code", "")).zfill(6)
        if not ts_code or len(ts_code) != 6:
            continue

        rev = row.get("rev_growth_yoy")
        ear = row.get("ear_growth_yoy")
        roe = row.get("roe")

        # Build or get existing factor record
        factor = Factor(ts_code=ts_code, trade_date=trade_date)

        # Set available fields
        if pd.notna(rev):
            factor.rev_growth_yoy = float(rev)
        if pd.notna(ear):
            factor.ear_growth_yoy = float(ear)
        if pd.notna(roe):
            factor.roe_ttm = float(roe)

        # Only add if at least one field was set
        if factor.rev_growth_yoy is not None or factor.ear_growth_yoy is not None or factor.roe_ttm is not None:
            factors_to_upsert.append(factor)

    if not factors_to_upsert:
        return 0

    # Upsert to DB (merge with existing records)
    from app.repositories.factor_repo import FactorRepository

    repo = FactorRepository(db)
    return repo.upsert_factor_batch(factors_to_upsert)


def _sync_per_stock_factors(
    db: DatabaseManager,
    fundamental: FundamentalService,
    ref_date: date,
    yjbb_df: pd.DataFrame | None,
) -> int:
    """
    逐股获取毛利率和自由现金流 (慢接口)。

    仅对 yjbb 中存在的股票执行，避免无效请求。
    """
    if yjbb_df is None or yjbb_df.empty:
        logger.info("per_stock sync skipped: no stock list from yjbb")
        return 0

    stock_codes = yjbb_df["ts_code"].dropna().unique()
    if len(stock_codes) == 0:
        return 0

    logger.info("per_stock sync: starting for %d stocks (slow, ~0.5s each)", len(stock_codes))

    factors_to_upsert: list[Factor] = []

    for ts_code in stock_codes:
        ts_code = str(ts_code).zfill(6)
        factor = Factor(ts_code=ts_code, trade_date=ref_date.isoformat())
        has_data = False

        # Gross margin
        fi = fundamental.fetch_financial_indicators(ts_code)
        if fi is not None and not fi.empty and "gross_margin" in fi.columns:
            gm = fi.iloc[0]["gross_margin"]
            if pd.notna(gm):
                factor.gross_margin = float(gm)
                has_data = True

        # Free cash flow (requires total_mv from elsewhere, skip for now)
        # TODO: implement fcf_yield with total_mv from snapshot

        if has_data:
            factors_to_upsert.append(factor)

    if not factors_to_upsert:
        return 0

    from app.repositories.factor_repo import FactorRepository

    repo = FactorRepository(db)
    return repo.upsert_factor_batch(factors_to_upsert)
