# -*- coding: utf-8 -*-
"""
全市场数据准备服务

一键拉取全A股实时快照 (ak.stock_zh_a_spot_em)，
写入 stock_info / kline_daily / factor_daily 三张表。
用于选股前自动准备数据，或手动触发数据同步。
"""

import logging
import json
import numpy as np
import pandas as pd
from datetime import datetime
from typing import Optional

from app.database import get_db, DatabaseManager
from app.models.stock_info import StockInfo
from app.models.kline import Kline
from app.models.factor import Factor

logger = logging.getLogger(__name__)


# AKShare 列名映射
_COLUMN_MAP = {
    '代码': 'ts_code',
    '名称': 'name',
    '最新价': 'close',
    '涨跌幅': 'pct_chg',
    '涨跌额': 'price_change',
    '成交量': 'volume',
    '成交额': 'amount',
    '振幅': 'amplitude',
    '最高': 'high',
    '最低': 'low',
    '今开': 'open',
    '昨收': 'pre_close',
    '量比': 'volume_ratio',
    '换手率': 'turnover_rate',
    '市盈率-动态': 'pe_ttm',
    '市净率': 'pb',
    '总市值': 'total_market_cap',
    '流通市值': 'circ_market_cap',
    '60日涨跌幅': 'ret_60d',
    '年初至今涨跌幅': 'ret_ytd',
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

    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or get_db()

    def prepare(self, trade_date: Optional[str] = None) -> dict:
        """
        全量数据准备: 拉取快照 → 写入DB → 计算因子。

        Args:
            trade_date: 交易日期 YYYY-MM-DD，默认今天

        Returns:
            dict with synced/failed counts
        """
        if trade_date is None:
            trade_date = datetime.now().strftime('%Y-%m-%d')

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
        source = df['_source'].iloc[0] if '_source' in df.columns else 'unknown'
        df = df.drop(columns=['_source'], errors='ignore')
        logger.info(f"[数据准备] 数据源: {source}, 股票数: {len(df)}")

        # For Sina source: filter out ETF codes (they are mixed in)
        if source == 'sina':
            from data_provider.base import _is_etf_code
            before = len(df)
            code_col = '代码' if '代码' in df.columns else 'ts_code'
            df = df[~df[code_col].apply(lambda x: _is_etf_code(str(x)))]
            logger.info(f"[数据准备] Sina 模式: 过滤 ETF, {before} -> {len(df)} 只")

        # Step 2: 列名映射
        df = df.rename(columns={k: v for k, v in _COLUMN_MAP.items() if k in df.columns})

        # Step 3: 数值列转换
        numeric_cols = [
            'close', 'pct_chg', 'volume', 'amount', 'high', 'low',
            'open', 'pre_close', 'volume_ratio', 'turnover_rate',
            'pe_ttm', 'pb', 'total_market_cap', 'circ_market_cap',
            'ret_60d',
        ]
        for col in numeric_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')

        logger.info(f"[数据准备] 快照解析完成: {len(df)} 只股票")

        # Step 4: 写入 stock_info
        stock_count = self._save_stock_info(df)
        logger.info(f"[数据准备] 写入 stock_info: {stock_count} 条")

        # Step 5: 写入 kline_daily
        kline_count = self._save_kline_daily(df, trade_date)
        logger.info(f"[数据准备] 写入 kline_daily: {kline_count} 条")

        # Step 6: 计算因子并写入 factor_daily
        factor_count = self._compute_and_save_factors(df, trade_date)
        logger.info(f"[数据准备] 写入 factor_daily: {factor_count} 条")

        return {
            "trade_date": trade_date,
            "source": source,
            "synced": kline_count,
            "factor_count": factor_count,
            "stock_count": stock_count,
        }

    def _save_stock_info(self, df: pd.DataFrame) -> int:
        """写入股票基本信息"""
        now = datetime.now().isoformat()
        stocks = []
        for _, row in df.iterrows():
            ts_code = row.get('ts_code')
            if not ts_code or pd.isna(ts_code):
                continue
            stock = StockInfo(
                ts_code=str(ts_code),
                name=str(row.get('name', '')) if pd.notna(row.get('name')) else None,
                is_st=int('ST' in str(row.get('name', '')).upper()),
                updated_at=now,
            )
            stocks.append(stock)

        if not stocks:
            return 0

        count = 0
        with self.db.get_session() as session:
            for stock in stocks:
                existing = session.get(StockInfo, stock.ts_code)
                if existing:
                    if stock.name:
                        existing.name = stock.name
                    existing.is_st = stock.is_st
                    existing.updated_at = stock.updated_at
                else:
                    session.add(stock)
                count += 1
            session.commit()
        return count

    def _save_kline_daily(self, df: pd.DataFrame, trade_date: str) -> int:
        """写入当日K线数据"""
        klines = []
        for _, row in df.iterrows():
            ts_code = row.get('ts_code')
            if not ts_code or pd.isna(ts_code):
                continue

            close_val = _safe_float(row.get('close'))
            if close_val is None or close_val <= 0:
                continue

            kline = Kline(
                ts_code=str(ts_code),
                trade_date=trade_date,
                open=_safe_float(row.get('open')),
                high=_safe_float(row.get('high')),
                low=_safe_float(row.get('low')),
                close=close_val,
                volume=_safe_float(row.get('volume')),
                amount=_safe_float(row.get('amount')),
                close_adj=close_val,  # 快照数据是当日价，复权价 = 收盘价 for now
                volume_ratio=_safe_float(row.get('volume_ratio')),
                turnover_rate=_safe_float(row.get('turnover_rate')),
                is_limit_up=1 if _safe_float(row.get('pct_chg')) and abs(_safe_float(row.get('pct_chg')) - 10.0) < 0.1 else 0,
                is_limit_down=1 if _safe_float(row.get('pct_chg')) and abs(_safe_float(row.get('pct_chg')) + 10.0) < 0.1 else 0,
                data_source='ak_spot',
            )
            klines.append(kline)

        if not klines:
            return 0

        count = 0
        with self.db.get_session() as session:
            for kline in klines:
                existing = session.get(Kline, (kline.ts_code, kline.trade_date))
                if existing:
                    session.merge(kline)
                else:
                    session.add(kline)
                count += 1
            session.commit()
        return count

    def _compute_and_save_factors(self, df: pd.DataFrame, trade_date: str) -> int:
        """
        从快照数据计算可用因子并写入 factor_daily。

        可从快照直接计算的因子:
        - pe_ttm: 市盈率-动态
        - pb: 市净率
        - turnover_20d: 换手率 (快照只提供当日换手率，作为代理值)
        - ret_20d: 用 60日涨跌幅的 1/3 近似
        - ret_60d_vol: 暂用振幅近似 (高-低/昨收)
        - ln_market_cap: ln(流通市值)

        需要基本面数据的因子 (暂缺):
        - ps_ttm, fcf_yield, roe_ttm, gross_margin,
          rev_growth_yoy, ear_growth_yoy, inst_holding_chg
        """
        now = datetime.now().isoformat()
        factors = []

        for _, row in df.iterrows():
            ts_code = row.get('ts_code')
            if not ts_code or pd.isna(ts_code):
                continue

            close_val = _safe_float(row.get('close'))
            if close_val is None or close_val <= 0:
                continue

            # 因子计算
            pe = _safe_float(row.get('pe_ttm'))
            pb = _safe_float(row.get('pb'))
            turnover = _safe_float(row.get('turnover_rate'))
            ret_60d = _safe_float(row.get('ret_60d'))
            circ_mv = _safe_float(row.get('circ_market_cap'))
            high = _safe_float(row.get('high'))
            low = _safe_float(row.get('low'))
            pre_close = _safe_float(row.get('pre_close'))

            # 波动率: 振幅近似 (高-低)/昨收
            ret_60d_vol = None
            if high and low and pre_close and pre_close > 0:
                ret_60d_vol = (high - low) / pre_close

            # 动量: 60日涨跌幅作为代理
            ret_20d = ret_60d / 3.0 if ret_60d is not None else None

            # 对数市值
            ln_market_cap = np.log(circ_mv) if circ_mv and circ_mv > 0 else None

            # PE 过滤: 排除 PE < 0 (亏损) 和 PE > 500 (异常)
            if pe is not None and (pe < 0 or pe > 500):
                pe = None

            factor = Factor(
                ts_code=str(ts_code),
                trade_date=trade_date,
                pe_ttm=pe,
                pb=pb,
                turnover_20d=turnover,
                ret_20d=ret_20d,
                ret_60d_vol=ret_60d_vol,
                ln_market_cap=ln_market_cap,
            )
            factors.append(factor)

        if not factors:
            return 0

        # 删除当日旧数据
        from sqlmodel import select
        with self.db.get_session() as session:
            # Delete existing factors for this date
            existing = session.exec(
                select(Factor).where(Factor.trade_date == trade_date)
            ).all()
            for f in existing:
                session.delete(f)
            session.commit()

        # 写入新数据
        count = 0
        with self.db.get_session() as session:
            for factor in factors:
                session.add(factor)
                count += 1
            session.commit()

        return count


def _safe_float(val) -> Optional[float]:
    """安全转换为 float"""
    if val is None:
        return None
    if isinstance(val, float) and pd.isna(val):
        return None
    if isinstance(val, str) and val.strip() == '-':
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None
