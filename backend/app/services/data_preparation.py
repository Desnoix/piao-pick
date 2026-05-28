"""
全市场数据准备服务

一键拉取全A股实时快照 (ak.stock_zh_a_spot_em)，
写入 stock_info / kline_daily / factor_daily 三张表。
用于选股前自动准备数据，或手动触发数据同步。
"""

import logging
from datetime import datetime

import numpy as np
import pandas as pd
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from app.database import DatabaseManager, get_db
from app.models.factor import Factor
from app.models.kline import Kline
from app.models.stock_info import StockInfo

logger = logging.getLogger(__name__)


# AKShare 列名映射
_COLUMN_MAP = {
    "代码": "ts_code",
    "名称": "name",
    "最新价": "close",
    "涨跌幅": "pct_chg",
    "涨跌额": "price_change",
    "成交量": "volume",
    "成交额": "amount",
    "振幅": "amplitude",
    "最高": "high",
    "最低": "low",
    "今开": "open",
    "昨收": "pre_close",
    "量比": "volume_ratio",
    "换手率": "turnover_rate",
    "市盈率-动态": "pe_ttm",
    "市净率": "pb",
    "总市值": "total_market_cap",
    "流通市值": "circ_market_cap",
    "年初至今涨跌幅": "ret_ytd",
}


class DataPreparationService:
    """
    全市场数据准备服务。

    主要流程:
    1. 调用 ak.stock_zh_a_spot_em() 一次拉取全A股快照
    2. 写入 stock_info (代码+名称)
    3. 写入 kline_daily (当日行情)
    4. 计算因子并写入 factor_daily
    """

    def __init__(self, db: DatabaseManager | None = None):
        self.db = db or get_db()

    def prepare(self, trade_date: str | None = None) -> dict:
        """
        全量数据准备: 拉取快照 → 写入DB → 计算因子。

        Args:
            trade_date: 交易日期 YYYY-MM-DD，默认今天

        Returns:
            dict with synced/failed counts
        """
        if trade_date is None:
            trade_date = datetime.now().strftime("%Y-%m-%d")

        logger.info(f"[数据准备] 开始全市场数据准备, 目标日期: {trade_date}")

        # Step 1: 拉取全A股快照
        try:
            from data_provider.akshare_fetcher import fetch_all_a_share_snapshot

            df = fetch_all_a_share_snapshot()
        except Exception as e:
            logger.error(f"[数据准备] 全A股快照拉取失败 (已重试5次): {e}")
            return {
                "synced": 0,
                "failed": 0,
                "error": (
                    "无法获取全A股快照数据 (东方财富和新浪接口均不可用)。"
                    "可能原因: (1) 网络连接超时或被防火墙拦截; "
                    "(2) 数据源接口临时不可用; "
                    "(3) 代理设置问题。"
                    f" 原始错误: {e}"
                ),
            }

        if df.empty:
            return {"synced": 0, "failed": 0, "error": "快照数据为空"}

        # Detect data source
        source = df["_source"].iloc[0] if "_source" in df.columns else "unknown"
        df = df.drop(columns=["_source"], errors="ignore")
        logger.info(f"[数据准备] 数据源: {source}, 股票数: {len(df)}")

        # For Sina source: filter out ETF codes (they are mixed in)
        if source == "sina":
            from data_provider.base import _is_etf_code

            before = len(df)
            code_col = "代码" if "代码" in df.columns else "ts_code"
            df = df[~df[code_col].apply(lambda x: _is_etf_code(str(x)))]
            logger.info(f"[数据准备] Sina 模式: 过滤 ETF, {before} -> {len(df)} 只")

        # Step 2: 列名映射
        df = df.rename(columns={k: v for k, v in _COLUMN_MAP.items() if k in df.columns})

        # Step 3: 数值列转换
        numeric_cols = [
            "close",
            "pct_chg",
            "volume",
            "amount",
            "high",
            "low",
            "open",
            "pre_close",
            "volume_ratio",
            "turnover_rate",
            "pe_ttm",
            "pb",
            "total_market_cap",
            "circ_market_cap",
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        logger.info(f"[数据准备] 快照解析完成: {len(df)} 只股票")

        # Step 4: 写入 stock_info
        stock_count = self._save_stock_info(df)
        logger.info(f"[数据准备] 写入 stock_info: {stock_count} 条")

        # Step 5: 写入 kline_daily
        kline_count = self._save_kline_daily(df, trade_date)
        logger.info(f"[数据准备] 写入 kline_daily: {kline_count} 条")

        # Step 6: 计算截面因子并写入 factor_daily
        factor_count = self._compute_and_save_factors(df, trade_date)
        logger.info(f"[数据准备] 写入截面因子: {factor_count} 条")

        # Step 6.5: 同步基本面因子 (批量接口, stock_yjbb_em)
        fundamental_count = 0
        try:
            from app.services.fundamental_sync_task import sync_fundamental_factors

            fund_result = sync_fundamental_factors(trade_date=trade_date, sync_per_stock=False)
            fundamental_count = fund_result.get("batch", 0)
            logger.info(
                f"[数据准备] 同步基本面因子: {fundamental_count} 条 (报告期: {fund_result.get('report_date', 'N/A')})"
            )
        except Exception as e:
            logger.warning(f"[数据准备] 基本面因子同步跳过: {e}")

        # Step 7: 从 K 线历史数据计算时序因子 (ret_20d, ret_60d_vol, turnover_20d)
        ts_factor_count = 0
        ts_factor_failed = 0
        try:
            from app.services.factor_compute_service import FactorComputeService

            factor_service = FactorComputeService()
            ts_result = factor_service.compute_factors_for_date(trade_date)
            ts_factor_count = ts_result.get("computed", 0)
            ts_factor_failed = ts_result.get("failed", 0)
            logger.info(f"[数据准备] 写入时序因子: {ts_factor_count} 条, 失败 {ts_factor_failed} 条 (需历史 K 线数据)")
        except Exception as e:
            logger.warning(f"[数据准备] 时序因子计算跳过 (历史 K 线不足): {e}")

        return {
            "trade_date": trade_date,
            "source": source,
            "synced": kline_count,
            "factor_count": factor_count,
            "fundamental_count": fundamental_count,
            "ts_factor_count": ts_factor_count,
            "stock_count": stock_count,
        }

    def _save_stock_info(self, df: pd.DataFrame) -> int:
        """写入股票基本信息 (批量 Upsert)"""
        now = datetime.now().isoformat()
        rows = []
        for _, row in df.iterrows():
            ts_code = row.get("ts_code")
            if not ts_code or pd.isna(ts_code):
                continue
            rows.append(
                {
                    "ts_code": str(ts_code),
                    "name": str(row.get("name", "")) if pd.notna(row.get("name")) else None,
                    "is_st": int("ST" in str(row.get("name", "")).upper()),
                    "updated_at": now,
                }
            )

        if not rows:
            return 0

        batch_size = 1000
        total = 0

        with self.db.get_session() as session:
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                stmt = sqlite_insert(StockInfo).values(batch)
                # ON CONFLICT DO UPDATE: 主键冲突时更新非主键字段
                stmt = stmt.on_conflict_do_update(
                    index_elements=["ts_code"],
                    set_={
                        "name": stmt.excluded.name,
                        "is_st": stmt.excluded.is_st,
                        "updated_at": stmt.excluded.updated_at,
                    },
                )
                session.exec(stmt)
                total += len(batch)
            session.commit()

        return total

    def _save_kline_daily(self, df: pd.DataFrame, trade_date: str) -> int:
        """写入当日K线数据 (批量 Upsert)"""
        rows = []
        for _, row in df.iterrows():
            ts_code = row.get("ts_code")
            if not ts_code or pd.isna(ts_code):
                continue

            close_val = _safe_float(row.get("close"))
            if close_val is None or close_val <= 0:
                continue

            pct_val = _safe_float(row.get("pct_chg"))
            rows.append(
                {
                    "ts_code": str(ts_code),
                    "trade_date": trade_date,
                    "open": _safe_float(row.get("open")),
                    "high": _safe_float(row.get("high")),
                    "low": _safe_float(row.get("low")),
                    "close": close_val,
                    "volume": _safe_float(row.get("volume")),
                    "amount": _safe_float(row.get("amount")),
                    "close_adj": close_val,
                    "volume_ratio": _safe_float(row.get("volume_ratio")),
                    "turnover_rate": _safe_float(row.get("turnover_rate")),
                    "is_limit_up": 1 if pct_val and abs(pct_val - 10.0) < 0.1 else 0,
                    "is_limit_down": 1 if pct_val and abs(pct_val + 10.0) < 0.1 else 0,
                    "data_source": "ak_spot",
                }
            )

        if not rows:
            return 0

        batch_size = 1000
        total = 0

        with self.db.get_session() as session:
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                stmt = sqlite_insert(Kline).values(batch)
                # 复合主键冲突: (ts_code, trade_date)
                stmt = stmt.on_conflict_do_update(
                    index_elements=["ts_code", "trade_date"],
                    set_={
                        "open": stmt.excluded.open,
                        "high": stmt.excluded.high,
                        "low": stmt.excluded.low,
                        "close": stmt.excluded.close,
                        "volume": stmt.excluded.volume,
                        "amount": stmt.excluded.amount,
                        "close_adj": stmt.excluded.close_adj,
                        "volume_ratio": stmt.excluded.volume_ratio,
                        "turnover_rate": stmt.excluded.turnover_rate,
                        "is_limit_up": stmt.excluded.is_limit_up,
                        "is_limit_down": stmt.excluded.is_limit_down,
                        "data_source": stmt.excluded.data_source,
                    },
                )
                session.exec(stmt)
                total += len(batch)
            session.commit()

        return total

    def _compute_and_save_factors(self, df: pd.DataFrame, trade_date: str) -> int:
        """
        Compute cross-sectional factors from snapshot data (批量 Upsert).

        Cross-sectional factors (computed here):
        - pe_ttm: 市盈率-动态
        - pb: 市净率
        - ln_market_cap: ln(流通市值)

        Time-series factors (computed by FactorComputeService):
        - ret_20d, ret_60d_vol, turnover_20d require historical K-line data
          and are computed separately to avoid incorrect approximations.

        基本面因子 (由 FundamentalSyncTask 从 AKShare 批量同步):
        ps_ttm, fcf_yield, roe_ttm, gross_margin,
        rev_growth_yoy, ear_growth_yoy, inst_holding_chg

        改造要点:
        - 批量 INSERT ON CONFLICT DO UPDATE, 仅更新截面字段
        - 保留时序因子字段 (ret_20d, ret_60d_vol, turnover_20d) 不被覆盖
        """
        rows = []

        for _, row in df.iterrows():
            ts_code = row.get("ts_code")
            if not ts_code or pd.isna(ts_code):
                continue

            close_val = _safe_float(row.get("close"))
            if close_val is None or close_val <= 0:
                continue

            # 截面因子计算 (仅依赖当日快照)
            pe = _safe_float(row.get("pe_ttm"))
            pb = _safe_float(row.get("pb"))
            circ_mv = _safe_float(row.get("circ_market_cap"))

            # 对数市值
            ln_market_cap = np.log(circ_mv) if circ_mv and circ_mv > 0 else None

            # PE 过滤: 排除 PE < 0 (亏损) 和 PE > 500 (异常)
            if pe is not None and (pe < 0 or pe > 500):
                pe = None

            rows.append(
                {
                    "ts_code": str(ts_code),
                    "trade_date": trade_date,
                    "pe_ttm": pe,
                    "pb": pb,
                    "ln_market_cap": ln_market_cap,
                }
            )

        if not rows:
            return 0

        batch_size = 1000
        total = 0

        # 单会话, 单事务: 批量 upsert 截面因子, 保留时序字段
        with self.db.get_session() as session:
            for i in range(0, len(rows), batch_size):
                batch = rows[i : i + batch_size]
                stmt = sqlite_insert(Factor).values(batch)
                # 复合主键冲突: (ts_code, trade_date)
                # 仅更新截面字段, 保留时序因子和基本面因子数据
                stmt = stmt.on_conflict_do_update(
                    index_elements=["ts_code", "trade_date"],
                    set_={
                        "pe_ttm": stmt.excluded.pe_ttm,
                        "pb": stmt.excluded.pb,
                        "ln_market_cap": stmt.excluded.ln_market_cap,
                    },
                )
                session.exec(stmt)
                total += len(batch)
            session.commit()

        return total


def _safe_float(val) -> float | None:
    """安全转换为 float"""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, str) and val.strip() == "-":
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
