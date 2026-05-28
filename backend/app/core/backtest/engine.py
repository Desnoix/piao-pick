"""
月度调仓回测引擎

每月最后一个交易日买入，下月最后一个交易日卖出，等权持仓。
涨跌停处理: 涨停股不纳入买入，跌停股延迟至可交易日卖出。
"""

import logging
from collections.abc import Callable
from datetime import date, datetime

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class BacktestEngine:
    """月度调仓回测引擎"""

    def __init__(self):
        pass

    def run(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        get_trade_dates: Callable,
        get_factors_snapshot: Callable,
        get_kline_snapshot: Callable,
        run_strategy_fn: Callable,
        commission_rate: float = 0.0003,
        stamp_tax: float = 0.0005,
        slippage: float = 0.001,
    ) -> dict:
        """
        执行回测

        Args:
            strategy_name: 策略名称
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            get_trade_dates: callable(start, end) -> list of date objects
            get_factors_snapshot: callable(date) -> DataFrame(index=ts_code, cols=factor_ids)
            get_kline_snapshot: callable(date) -> DataFrame(index=ts_code, cols=close, close_adj,
                                  is_limit_up, is_limit_down, turnover_rate, ...)
            run_strategy_fn: callable(strategy_name, trade_date, factors) -> list of ts_codes
            commission_rate: one-sided commission rate (default 0.0003, i.e. 0.03%)
            stamp_tax: sell-side stamp tax (default 0.0005, i.e. 0.05%)
            slippage: one-sided slippage estimate (default 0.001, i.e. 0.1%)

        Returns:
            dict with keys: strategy_name, start_date, end_date, rebalance_count,
                            nav, portfolio_returns, turnover_history,
                            cost_deductions, total_cost, avg_cost_per_period,
                            tradeability_stats
        """
        trade_dates = get_trade_dates(start_date, end_date)
        rebalance_dates = self._get_monthly_rebalance_dates(trade_dates)

        logger.info(f"Backtest: {strategy_name}, {start_date} ~ {end_date}, {len(rebalance_dates)} rebalance points")

        if len(rebalance_dates) < 2:
            logger.warning("Not enough rebalance dates (need at least 2)")
            return {
                "strategy_name": strategy_name,
                "start_date": start_date,
                "end_date": end_date,
                "rebalance_count": 0,
                "nav": [],
                "portfolio_returns": [],
                "turnover_history": [],
                "cost_deductions": [],
                "total_cost": 0.0,
                "avg_cost_per_period": 0.0,
                "tradeability_stats": {
                    "limit_up_skipped_total": 0,
                    "limit_down_deferred_total": 0,
                    "rebalance_periods": 0,
                },
            }

        portfolio_returns: list[float] = []
        turnover_history: list[float] = []
        period_costs: list[float] = []
        prev_holdings: set = set()

        total_limit_up_skipped = 0
        total_limit_down_deferred = 0

        for i in range(len(rebalance_dates) - 1):
            rdate = rebalance_dates[i]
            next_rdate = rebalance_dates[i + 1]

            # 获取因子快照
            factors = get_factors_snapshot(rdate)
            if factors is None or factors.empty:
                logger.warning(f"No factors for {rdate}, skipping")
                portfolio_returns.append(0.0)
                period_costs.append(0.0)
                continue

            # 运行策略选股
            selected_stocks = run_strategy_fn(strategy_name, rdate, factors)
            if not selected_stocks:
                logger.warning(f"No stocks selected for {rdate}")
                prev_holdings = set()
                portfolio_returns.append(0.0)
                turnover_history.append(1.0)
                period_costs.append(0.0)
                continue

            # 获取买入日和卖出日行情
            kline = get_kline_snapshot(rdate)
            next_kline = get_kline_snapshot(next_rdate)

            if kline is None or next_kline is None or kline.empty or next_kline.empty:
                portfolio_returns.append(0.0)
                turnover_history.append(0.0)
                prev_holdings = set()
                period_costs.append(0.0)
                continue

            # === 买入侧: 涨停过滤 ===
            tradeable_stocks = []
            limit_up_skipped = []
            for stock in selected_stocks:
                if self._is_limit_up(kline, stock):
                    limit_up_skipped.append(stock)
                    logger.debug(f"  {rdate}: {stock} 涨停, 跳过买入")
                else:
                    tradeable_stocks.append(stock)

            if limit_up_skipped:
                logger.info(f"  {rdate}: {len(limit_up_skipped)} stocks skipped (涨停): " + ", ".join(limit_up_skipped))

            # 换手率 (基于实际可交易股票)
            new_holdings = set(tradeable_stocks)
            if prev_holdings:
                overlap = len(new_holdings & prev_holdings)
                turnover = 1.0 - overlap / max(len(new_holdings), 1)
            else:
                turnover = 1.0
            turnover_history.append(turnover)

            # === 收益计算: 含跌停延迟卖出 ===
            stock_returns: list[float] = []
            limit_down_deferred: list[str] = []

            for stock in tradeable_stocks:
                entry_price = self._get_close_price(kline, stock)
                exit_price = self._get_close_price(next_kline, stock)

                if entry_price is None or entry_price <= 0:
                    continue

                # 卖出日跌停检查
                if self._is_limit_down(next_kline, stock):
                    deferred_price, deferred_date = self._find_next_sell_exit(
                        stock, next_rdate, trade_dates, get_kline_snapshot, max_delay=5
                    )
                    if deferred_price is not None:
                        exit_price = deferred_price
                        dd_str = (
                            deferred_date.isoformat() if hasattr(deferred_date, "isoformat") else str(deferred_date)
                        )
                        limit_down_deferred.append(f"{stock}(->{dd_str})")
                        logger.debug(f"  {next_rdate}: {stock} 跌停, 延迟至 {dd_str} 卖出")
                    else:
                        logger.warning(f"  {next_rdate}: {stock} 连续跌停5日无法卖出, 使用跌停价")

                if exit_price is not None:
                    ret = exit_price / entry_price - 1.0
                    stock_returns.append(ret)

            raw_period_return = float(np.mean(stock_returns)) if stock_returns else 0.0

            # 交易成本 = 换手比例 × 单次往返总摩擦
            round_trip_cost = commission_rate * 2.0 + stamp_tax + slippage * 2.0
            cost_deduction = turnover * round_trip_cost
            period_return = raw_period_return - cost_deduction

            portfolio_returns.append(period_return)
            period_costs.append(cost_deduction)
            prev_holdings = new_holdings

            total_limit_up_skipped += len(limit_up_skipped)
            total_limit_down_deferred += len(limit_down_deferred)

            if limit_down_deferred:
                logger.info(
                    f"  {next_rdate}: {len(limit_down_deferred)} stocks deferred (跌停): "
                    + ", ".join(limit_down_deferred)
                )

            logger.info(
                f"  {rdate}: {len(selected_stocks)} selected, "
                f"{len(tradeable_stocks)} tradeable, "
                f"{len(stock_returns)} returns, period_return={period_return:.4f}"
            )

        # 计算净值曲线
        nav_values = [1.0]
        for ret in portfolio_returns:
            nav_values.append(nav_values[-1] * (1.0 + ret))

        nav_series = list(
            zip(
                [d.isoformat() for d in rebalance_dates],
                nav_values,
            )
        )

        # 成本统计
        total_cost = round(sum(period_costs), 6)
        avg_cost_per_period = round(total_cost / len(period_costs), 6) if period_costs else 0.0

        return {
            "strategy_name": strategy_name,
            "start_date": start_date,
            "end_date": end_date,
            "rebalance_count": len(rebalance_dates) - 1,
            "nav": nav_series,
            "portfolio_returns": portfolio_returns,
            "turnover_history": turnover_history,
            "cost_deductions": period_costs,
            "total_cost": total_cost,
            "avg_cost_per_period": avg_cost_per_period,
            "tradeability_stats": {
                "limit_up_skipped_total": total_limit_up_skipped,
                "limit_down_deferred_total": total_limit_down_deferred,
                "rebalance_periods": len(portfolio_returns),
            },
        }

    def _get_monthly_rebalance_dates(self, trade_dates: list) -> list:
        """
        提取每月最后一个交易日。

        Args:
            trade_dates: list of date objects or ISO date strings

        Returns:
            Sorted list of date objects (last trading day per month)
        """
        if not trade_dates:
            return []

        monthly: dict[tuple, date] = {}
        for d in trade_dates:
            if isinstance(d, str):
                d = datetime.fromisoformat(d).date()
            elif isinstance(d, datetime):
                d = d.date()
            key = (d.year, d.month)
            if key not in monthly or d > monthly[key]:
                monthly[key] = d

        return sorted(monthly.values())

    @staticmethod
    def _get_close_price(kline_df: pd.DataFrame, ts_code: str) -> float | None:
        """
        从行情快照中获取某只股票的收盘价（优先 close_adj, 退化到 close）。

        Args:
            kline_df: DataFrame with index=ts_code
            ts_code: stock code

        Returns:
            Close price or None
        """
        if ts_code not in kline_df.index:
            return None

        row = kline_df.loc[ts_code]

        # Handle duplicate index (multiple rows for same ts_code)
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        if "close_adj" in kline_df.columns and pd.notna(row.get("close_adj")):
            val = row["close_adj"]
            return float(val) if pd.notna(val) and val > 0 else None

        if "close" in kline_df.columns and pd.notna(row.get("close")):
            val = row["close"]
            return float(val) if pd.notna(val) and val > 0 else None

        return None

    @staticmethod
    def _is_limit_up(kline_df: pd.DataFrame, ts_code: str) -> bool:
        """
        检查股票是否涨停 (不可买入)。

        Args:
            kline_df: 行情快照 DataFrame, 需包含 is_limit_up 列
            ts_code: 股票代码

        Returns:
            True=涨停不可买, False=可交易或无数据
        """
        if kline_df is None or kline_df.empty:
            return False
        if ts_code not in kline_df.index:
            return False
        if "is_limit_up" not in kline_df.columns:
            return False

        row = kline_df.loc[ts_code]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        return bool(row.get("is_limit_up", False))

    @staticmethod
    def _is_limit_down(kline_df: pd.DataFrame, ts_code: str) -> bool:
        """
        检查股票是否跌停 (不可卖出)。

        Args:
            kline_df: 行情快照 DataFrame, 需包含 is_limit_down 列
            ts_code: 股票代码

        Returns:
            True=跌停不可卖, False=可交易或无数据
        """
        if kline_df is None or kline_df.empty:
            return False
        if ts_code not in kline_df.index:
            return False
        if "is_limit_down" not in kline_df.columns:
            return False

        row = kline_df.loc[ts_code]
        if isinstance(row, pd.DataFrame):
            row = row.iloc[0]

        return bool(row.get("is_limit_down", False))

    def _find_next_sell_exit(
        self,
        ts_code: str,
        start_date,
        trade_dates: list,
        get_kline_snapshot: Callable,
        max_delay: int = 5,
    ) -> tuple:
        """
        为跌停股寻找下一个可卖出交易日。

        从 start_date 之后逐日检查，找到第一个非跌停日并返回该日收盘价。
        处理连续跌停场景，超过 max_delay 天仍无法卖出则返回 None。

        Args:
            ts_code: 股票代码
            start_date: 跌停日 (date 或 ISO 字符串)
            trade_dates: 全量交易日列表 (升序)
            get_kline_snapshot: callable(date_str) -> DataFrame
            max_delay: 最大延迟天数, 默认5

        Returns:
            (exit_price: float|None, exit_date: date|None)
        """
        start_d = start_date
        if isinstance(start_d, str):
            start_d = datetime.fromisoformat(start_d).date()
        elif isinstance(start_d, datetime):
            start_d = start_d.date()

        start_idx = None
        for i, td in enumerate(trade_dates):
            td_d = td
            if isinstance(td_d, str):
                td_d = datetime.fromisoformat(td_d).date()
            elif isinstance(td_d, datetime):
                td_d = td_d.date()
            if td_d == start_d:
                start_idx = i
                break

        if start_idx is None:
            return (None, None)

        for offset in range(1, max_delay + 1):
            next_idx = start_idx + offset
            if next_idx >= len(trade_dates):
                break

            next_td = trade_dates[next_idx]
            next_td_str = next_td.isoformat() if hasattr(next_td, "isoformat") else str(next_td)
            next_kline = get_kline_snapshot(next_td_str)

            if next_kline is None or next_kline.empty:
                continue

            if not self._is_limit_down(next_kline, ts_code):
                price = self._get_close_price(next_kline, ts_code)
                if price is not None:
                    return (price, next_td)

        return (None, None)
