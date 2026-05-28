"""
ICIR 快照服务

为选股执行器提供当前截面的 ICIR 权重。
从历史因子数据和行情数据计算滚动 IC (Information Coefficient),
再基于滚动窗口 IC 计算 ICIR (IC 均值 / IC 标准差)。

设计要点:
- 严格使用 trade_date 之前的历史数据, 无前视偏差
- IC 计算用 trade_date 截面因子 vs 下一期收益率 (用于评估因子有效性)
- ICIR 窗口仅包含 trade_date 及更早的 IC 值
- 缓存 IC 时间序列, 避免重复计算
"""

import logging
from datetime import date, datetime

import pandas as pd

from app.core.backtest.ic_analysis import compute_factor_ic, rolling_icir
from app.database import get_db
from app.repositories.factor_repo import FactorRepository
from app.repositories.stock_repo import StockRepository

logger = logging.getLogger(__name__)


class IcirService:
    """ICIR 快照服务: 为选股执行器提供当前截面的 ICIR 权重"""

    def __init__(self):
        self.db = get_db()
        self.factor_repo = FactorRepository(self.db)
        self.stock_repo = StockRepository(self.db)
        # IC 序列缓存: key = (lookback_key) -> ic_series dict
        self._ic_series_cache: dict[str, dict[str, list]] = {}

    def get_icir_snapshot(
        self,
        strategy_name: str,
        trade_date: str | date,
        lookback: int = 12,
        min_periods: int = 6,
        factor_ids: list[str] | None = None,
    ) -> dict[str, float] | None:
        """
        获取指定日期截面的各因子 ICIR。

        实现步骤:
        1. 从 factor_daily 表取该策略相关因子在最近 (lookback + min_periods) 个月的月末数据
        2. 对每个月末截面计算 IC (因子值 vs 下月收益)
        3. 对 IC 时间序列计算滚动 ICIR
        4. 返回 trade_date 截面的 ICIR dict

        Args:
            strategy_name: 策略名称
            trade_date: 当前交易日期 (str YYYY-MM-DD 或 date 对象)
            lookback: 滚动窗口月数
            min_periods: 最少有效 IC 期数
            factor_ids: 指定因子列表, None 时使用全部可用因子

        Returns:
            dict of factor_id -> ICIR value, 或 None (数据不足时)
        """
        if isinstance(trade_date, str):
            trade_date_obj = datetime.fromisoformat(trade_date).date()
        else:
            trade_date_obj = trade_date

        date_iso = trade_date_obj.isoformat()

        # 获取历史月度日期
        month_count = lookback + min_periods
        monthly_dates = self._get_monthly_dates(trade_date_obj, month_count)

        if len(monthly_dates) < min_periods:
            logger.warning(f"Not enough monthly dates for ICIR: need {min_periods}, got {len(monthly_dates)}")
            return None

        # 构建 IC 时间序列 (带缓存)
        cache_key = f"{date_iso}_{month_count}"
        if cache_key in self._ic_series_cache:
            ic_series = self._ic_series_cache[cache_key]
        else:
            ic_series = self._build_ic_series(monthly_dates, factor_ids)
            self._ic_series_cache[cache_key] = ic_series

        if not ic_series:
            logger.warning("No IC data available for ICIR computation")
            return None

        # 计算滚动 ICIR
        rolling_result = rolling_icir(ic_series, lookback=lookback, min_periods=min_periods)

        # 取 trade_date 截面 (取 <= trade_date 的最新截面)
        snapshot_icir = None
        for d in sorted(rolling_result.keys(), reverse=True):
            if d <= date_iso:
                snapshot_icir = rolling_result[d]
                break

        if snapshot_icir is None:
            return None

        logger.info(
            f"ICIR snapshot for {strategy_name} @ {date_iso}: { {k: round(v, 3) for k, v in snapshot_icir.items()} }"
        )
        return snapshot_icir

    def _build_ic_series(
        self,
        monthly_dates: list[date],
        factor_ids: list[str] | None,
    ) -> dict[str, list]:
        """
        对每个月度截面计算 IC, 汇总为 IC 时间序列。

        Args:
            monthly_dates: 月度日期列表 (升序)
            factor_ids: 指定因子列表, None 时使用全部可用因子

        Returns:
            dict of factor_id -> list of (date_iso, IC) tuples
        """
        ic_series: dict[str, list] = {}

        for i, mdate in enumerate(monthly_dates):
            # IC 需要当期因子值 + 下一期收益率
            # 下一期 = monthly_dates[i+1] (如果存在)
            if i + 1 >= len(monthly_dates):
                break

            mdate_iso = mdate.isoformat()
            next_date_iso = monthly_dates[i + 1].isoformat()

            # 获取当前月因子截面
            snapshot = self._get_factor_snapshot(mdate_iso, factor_ids)
            if snapshot is None or snapshot.empty:
                continue

            # 获取下期收益率
            returns = self._get_period_returns(mdate_iso, next_date_iso)
            if returns is None or returns.empty:
                continue

            # 计算截面 IC
            ic_scores = compute_factor_ic(snapshot, returns)

            for fid, ic_val in ic_scores.items():
                if fid not in ic_series:
                    ic_series[fid] = []
                ic_series[fid].append((mdate_iso, ic_val))

        logger.info(f"Built IC series: {len(ic_series)} factors, {len(monthly_dates)} monthly dates")
        return ic_series

    def _get_monthly_dates(self, end_date: date, count: int) -> list[date]:
        """
        获取 end_date 之前 count 个月的月末日期 (不含 end_date 所在月)。

        返回升序排列的日期列表。
        """
        from dateutil.relativedelta import relativedelta

        dates = []
        cursor = end_date
        for _ in range(count):
            cursor = cursor - relativedelta(months=1)
            # 取该月末
            month_end = cursor.replace(day=28) + relativedelta(days=4)
            month_end = month_end - relativedelta(days=month_end.day)
            dates.append(month_end)

        return sorted(dates)

    def _get_factor_snapshot(self, date_iso: str, factor_ids: list[str] | None) -> pd.DataFrame | None:
        """
        从 factor_daily 表获取指定日期的因子截面。

        返回 DataFrame, index=ts_code, columns=factor_ids。
        """
        try:
            df = self.factor_repo.get_factors_snapshot(date_iso)
            if df is None or df.empty:
                return None
            if factor_ids:
                available = [c for c in factor_ids if c in df.columns]
                if not available:
                    return None
                df = df[available]
            return df
        except Exception as e:
            logger.warning(f"Failed to get factor snapshot for {date_iso}: {e}")
            return None

    def _get_period_returns(self, start_date_iso: str, end_date_iso: str) -> pd.Series | None:
        """
        计算 start_date 到 end_date 区间的收益率。

        Returns:
            Series, index=ts_code, values=期间收益率 (小数形式)
        """
        try:
            start_kline = self.stock_repo.get_kline_snapshot(start_date_iso)
            end_kline = self.stock_repo.get_kline_snapshot(end_date_iso)

            if start_kline is None or start_kline.empty:
                return None
            if end_kline is None or end_kline.empty:
                return None

            # 优先使用 close_adj (复权价), 退化到 close
            start_col = "close_adj" if "close_adj" in start_kline.columns else "close"
            end_col = "close_adj" if "close_adj" in end_kline.columns else "close"

            if start_col not in start_kline.columns or end_col not in end_kline.columns:
                return None

            # 对齐 index 计算收益率
            common_idx = start_kline.index.intersection(end_kline.index)
            if len(common_idx) < 10:
                return None

            start_prices = start_kline.loc[common_idx, start_col]
            end_prices = end_kline.loc[common_idx, end_col]

            returns = (end_prices / start_prices - 1.0).dropna()
            # 过滤极端值 (涨跌停、停牌等)
            returns = returns[returns.between(-0.5, 1.0)]
            return returns

        except Exception as e:
            logger.warning(f"Failed to get period returns for {start_date_iso} -> {end_date_iso}: {e}")
            return None
