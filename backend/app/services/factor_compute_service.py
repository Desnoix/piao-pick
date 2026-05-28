"""
因子计算服务

从历史K线数据计算时序因子，写入 factor_daily 表。
支持:
- 移动平均线 (MA5, MA10, MA20, MA60)
- 动量因子 (20日收益率, 60日波动率)
- 换手率因子 (20日均换手率)
"""

import logging

import numpy as np
import pandas as pd

from app.core.factor.momentum import compute_ret_20d, compute_ret_60d_vol, compute_turnover_20d
from app.database import get_db
from app.models.factor import Factor
from app.repositories import FactorRepository, StockRepository
from app.services.cache import get_cache_manager

logger = logging.getLogger(__name__)


class FactorComputeService:
    """因子计算服务"""

    def __init__(self):
        self.db = get_db()
        self.stock_repo = StockRepository(self.db)
        self.factor_repo = FactorRepository(self.db)

    def compute_factors_for_stock(
        self,
        ts_code: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> int:
        """
        为单只股票计算时序因子。

        Args:
            ts_code: 股票代码
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            写入的因子记录数
        """
        # 加载K线数据
        klines = self.stock_repo.get_klines_by_code(ts_code, start_date=start_date, end_date=end_date)
        if not klines:
            logger.warning(f"No kline data for {ts_code}")
            return 0

        # 转为 DataFrame
        df = pd.DataFrame(
            [
                {
                    "ts_code": k.ts_code,
                    "trade_date": k.trade_date,
                    "open": k.open,
                    "high": k.high,
                    "low": k.low,
                    "close": k.close,
                    "close_adj": k.close_adj,
                    "volume": k.volume,
                    "turnover_rate": k.turnover_rate,
                }
                for k in klines
            ]
        )
        df = df.sort_values("trade_date").reset_index(drop=True)

        if len(df) < 20:
            logger.warning(f"Not enough data for {ts_code}: {len(df)} rows (need >= 20)")
            return 0

        # 计算时序因子
        df["ma5"] = df["close"].rolling(window=5, min_periods=1).mean()
        df["ma10"] = df["close"].rolling(window=10, min_periods=1).mean()
        df["ma20"] = df["close"].rolling(window=20, min_periods=1).mean()
        df["ma60"] = df["close"].rolling(window=60, min_periods=1).mean()

        df["ret_20d"] = compute_ret_20d(df)
        df["ret_60d_vol"] = compute_ret_60d_vol(df)
        df["turnover_20d"] = compute_turnover_20d(df)

        # 构建 Factor 对象列表
        factors: list[Factor] = []
        for _, row in df.iterrows():
            factor = Factor(
                ts_code=row["ts_code"],
                trade_date=row["trade_date"],
                # 时序因子
                ret_20d=self._safe_float(row.get("ret_20d")),
                ret_60d_vol=self._safe_float(row.get("ret_60d_vol")),
                turnover_20d=self._safe_float(row.get("turnover_20d")),
            )
            factors.append(factor)

        # 批量写入
        if factors:
            self.factor_repo.upsert_factor_batch(factors)
            cm = get_cache_manager()
            cm.invalidate_stock_cache(ts_code)
            logger.info(f"Computed {len(factors)} factor records for {ts_code}")

        return len(factors)

    def compute_factors_for_all_stocks(
        self,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """
        为所有股票计算时序因子。

        Args:
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)

        Returns:
            统计结果 dict
        """
        all_codes = self.stock_repo.get_all_stock_codes()
        if not all_codes:
            logger.warning("No stocks found")
            return {"computed": 0, "failed": 0, "total": 0}

        logger.info(f"Start computing factors for {len(all_codes)} stocks")

        computed = 0
        failed = 0
        errors = []

        for idx, ts_code in enumerate(all_codes, 1):
            try:
                n = self.compute_factors_for_stock(ts_code, start_date, end_date)
                if n > 0:
                    computed += 1

                # 进度日志
                if idx % 100 == 0:
                    logger.info(
                        f"Progress: {idx}/{len(all_codes)} "
                        f"({idx / len(all_codes) * 100:.1f}%), "
                        f"computed={computed}, failed={failed}"
                    )
            except Exception as e:
                failed += 1
                errors.append(f"{ts_code}: {e}")
                logger.error(f"Failed to compute factors for {ts_code}: {e}")

        logger.info(f"Factor computation completed: {computed} stocks computed, {failed} failed")

        return {
            "computed": computed,
            "failed": failed,
            "total": len(all_codes),
            "errors": errors[:20],
        }

    def compute_factors_for_date(
        self,
        trade_date: str,
    ) -> dict:
        """
        为指定日期计算所有股票的截面因子。

        与 compute_factors_for_all_stocks 的区别:
        - 本函数只计算单个日期的因子值 (横向截面)
        - compute_factors_for_all_stocks 计算时间序列 (纵向)

        适用于:
        - 每日数据更新后，增量计算当日因子
        - 选时策略需要最新截面

        Args:
            trade_date: 交易日期 (YYYY-MM-DD)

        Returns:
            统计结果 dict
        """
        # 获取当日所有K线
        klines = self.stock_repo.get_klines_by_date(trade_date)
        if not klines:
            logger.warning(f"No kline data for date {trade_date}")
            return {"computed": 0, "failed": 0, "total": 0}

        logger.info(f"Computing cross-sectional factors for {trade_date}: {len(klines)} stocks")

        computed = 0
        failed = 0
        factors_list: list[Factor] = []

        for kline in klines:
            try:
                # 加载该股的历史K线 (用于计算时序因子)
                hist_klines = self.stock_repo.get_klines_by_code(
                    kline.ts_code,
                    end_date=trade_date,
                )
                if not hist_klines or len(hist_klines) < 20:
                    failed += 1
                    continue

                # 转为 DataFrame
                df = pd.DataFrame(
                    [
                        {
                            "ts_code": k.ts_code,
                            "trade_date": k.trade_date,
                            "close": k.close,
                            "close_adj": k.close_adj,
                            "volume": k.volume,
                            "turnover_rate": k.turnover_rate,
                        }
                        for k in hist_klines
                    ]
                )
                df = df.sort_values("trade_date").reset_index(drop=True)

                # 计算时序因子
                ret_20d = compute_ret_20d(df).iloc[-1]
                ret_60d_vol = compute_ret_60d_vol(df).iloc[-1]
                turnover_20d = compute_turnover_20d(df).iloc[-1]

                # 读取已有记录，保留截面因子不被覆盖
                existing_factor = self.factor_repo.get_factor(kline.ts_code, trade_date)
                if existing_factor:
                    existing_factor.ret_20d = self._safe_float(ret_20d)
                    existing_factor.ret_60d_vol = self._safe_float(ret_60d_vol)
                    existing_factor.turnover_20d = self._safe_float(turnover_20d)
                    factors_list.append(existing_factor)
                else:
                    factor = Factor(
                        ts_code=kline.ts_code,
                        trade_date=trade_date,
                        ret_20d=self._safe_float(ret_20d),
                        ret_60d_vol=self._safe_float(ret_60d_vol),
                        turnover_20d=self._safe_float(turnover_20d),
                    )
                    factors_list.append(factor)
                computed += 1

            except Exception as e:
                failed += 1
                logger.error(f"Failed to compute factor for {kline.ts_code} on {trade_date}: {e}")

        # 批量写入
        if factors_list:
            self.factor_repo.upsert_factor_batch(factors_list)

        logger.info(f"Cross-sectional factors for {trade_date}: {computed} computed, {failed} failed")

        return {
            "computed": computed,
            "failed": failed,
            "total": len(klines),
        }

    @staticmethod
    def _safe_float(val) -> float | None:
        """安全转换为 float"""
        if val is None:
            return None
        if isinstance(val, float) and (pd.isna(val) or np.isinf(val)):
            return None
        try:
            return float(val)
        except (ValueError, TypeError):
            return None
