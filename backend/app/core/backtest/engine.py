# -*- coding: utf-8 -*-
"""
月度调仓回测引擎

每月最后一个交易日买入，下月最后一个交易日卖出，等权持仓。
"""

import logging
import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime, date

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
    ) -> dict:
        """
        执行回测

        Args:
            strategy_name: 策略名称
            start_date: 开始日期 (YYYY-MM-DD)
            end_date: 结束日期 (YYYY-MM-DD)
            get_trade_dates: callable(start, end) -> list of date objects
            get_factors_snapshot: callable(date) -> DataFrame(index=ts_code, cols=factor_ids)
            get_kline_snapshot: callable(date) -> DataFrame(index=ts_code, cols=close, close_adj)
            run_strategy_fn: callable(strategy_name, trade_date, factors) -> list of ts_codes

        Returns:
            dict with keys: strategy_name, start_date, end_date, rebalance_count,
                            nav, portfolio_returns, turnover_history
        """
        trade_dates = get_trade_dates(start_date, end_date)
        rebalance_dates = self._get_monthly_rebalance_dates(trade_dates)

        logger.info(
            f"Backtest: {strategy_name}, {start_date} ~ {end_date}, "
            f"{len(rebalance_dates)} rebalance points"
        )

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
            }

        portfolio_returns: List[float] = []
        turnover_history: List[float] = []
        prev_holdings: set = set()

        for i in range(len(rebalance_dates) - 1):
            rdate = rebalance_dates[i]
            next_rdate = rebalance_dates[i + 1]

            # 获取因子快照
            factors = get_factors_snapshot(rdate)
            if factors is None or factors.empty:
                logger.warning(f"No factors for {rdate}, skipping")
                portfolio_returns.append(0.0)
                continue

            # 运行策略选股
            selected_stocks = run_strategy_fn(strategy_name, rdate, factors)
            if not selected_stocks:
                logger.warning(f"No stocks selected for {rdate}")
                prev_holdings = set()
                portfolio_returns.append(0.0)
                turnover_history.append(1.0)
                continue

            # 计算换手率
            new_holdings = set(selected_stocks)
            if prev_holdings:
                overlap = len(new_holdings & prev_holdings)
                turnover = 1.0 - overlap / max(len(new_holdings), 1)
            else:
                turnover = 1.0
            turnover_history.append(turnover)

            # 等权持仓收益: 获取买入日和卖出日的行情
            kline = get_kline_snapshot(rdate)
            next_kline = get_kline_snapshot(next_rdate)

            if kline is None or next_kline is None or kline.empty or next_kline.empty:
                portfolio_returns.append(0.0)
                prev_holdings = new_holdings
                continue

            stock_returns: List[float] = []
            for stock in selected_stocks:
                entry_price = self._get_close_price(kline, stock)
                exit_price = self._get_close_price(next_kline, stock)

                if entry_price is not None and exit_price is not None and entry_price > 0:
                    ret = exit_price / entry_price - 1.0
                    stock_returns.append(ret)

            period_return = float(np.mean(stock_returns)) if stock_returns else 0.0
            portfolio_returns.append(period_return)
            prev_holdings = new_holdings

            logger.info(
                f"  {rdate}: {len(selected_stocks)} stocks selected, "
                f"{len(stock_returns)} with returns, period_return={period_return:.4f}"
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

        return {
            "strategy_name": strategy_name,
            "start_date": start_date,
            "end_date": end_date,
            "rebalance_count": len(rebalance_dates) - 1,
            "nav": nav_series,
            "portfolio_returns": portfolio_returns,
            "turnover_history": turnover_history,
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

        monthly: Dict[tuple, date] = {}
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
    def _get_close_price(kline_df: pd.DataFrame, ts_code: str) -> Optional[float]:
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
