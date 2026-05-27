# -*- coding: utf-8 -*-
"""
回测服务层

封装 BacktestEngine，提供完整的回测执行流程：
1. 获取交易日历
2. 获取因子快照
3. 运行策略选股
4. 计算收益与风险指标
"""

import logging
from datetime import date, datetime
from typing import Optional

import pandas as pd

from app.core.backtest.engine import BacktestEngine
from app.core.backtest.metrics import compute_metrics
from app.core.strategy.loader import StrategyLoader
from app.core.strategy.executor import StrategyExecutor
from app.core.trading_calendar import get_trade_dates_between
from app.database import get_db
from app.repositories.stock_repo import StockRepository
from app.repositories.factor_repo import FactorRepository

logger = logging.getLogger(__name__)


class BacktestService:
    """回测服务"""

    def __init__(self):
        self.engine = BacktestEngine()
        self.strategy_loader = StrategyLoader()
        self.db = get_db()
        self._stock_repo: Optional[StockRepository] = None
        self._factor_repo: Optional[FactorRepository] = None

    @property
    def stock_repo(self) -> StockRepository:
        if self._stock_repo is None:
            self._stock_repo = StockRepository(self.db)
        return self._stock_repo

    @property
    def factor_repo(self) -> FactorRepository:
        if self._factor_repo is None:
            self._factor_repo = FactorRepository(self.db)
        return self._factor_repo

    def run_backtest(self, strategy_name: str, start_date: str, end_date: str) -> dict:
        """
        执行回测。

        Args:
            strategy_name: 策略名称 (YAML 文件名不含 .yaml)
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD

        Returns:
            dict with strategy_name, start_date, end_date, period, metrics,
            nav_series, returns, turnover_history
        """
        logger.info(f"Starting backtest: {strategy_name}, {start_date} ~ {end_date}")

        # 预加载策略配置，避免每次选股都重新加载
        strategy = self.strategy_loader.load_by_name(strategy_name)
        if strategy is None:
            raise ValueError(f"Strategy not found: {strategy_name}")

        executor = StrategyExecutor()

        def get_trade_dates(start: str, end: str) -> list:
            """获取交易日列表，返回 date 对象"""
            sd = _parse_date(start)
            ed = _parse_date(end)
            return get_trade_dates_between(sd, ed)

        def get_factors_snapshot(rdate) -> pd.DataFrame:
            """获取某日因子快照"""
            date_str = rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate)
            return self.factor_repo.get_factors_snapshot(date_str)

        def get_kline_snapshot(rdate) -> pd.DataFrame:
            """获取某日行情快照"""
            date_str = rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate)
            return self.stock_repo.get_kline_snapshot(date_str)

        def run_strategy(name: str, rdate, factors: pd.DataFrame) -> list:
            """运行策略选股，返回 ts_code 列表"""
            stock_info_df = self.stock_repo.get_all_stock_info_df()
            try:
                result_df = executor.execute(strategy, factors, stock_info_df)
                if result_df.empty:
                    return []
                return result_df["ts_code"].tolist()
            except Exception as e:
                logger.error(f"Strategy execution failed for {rdate}: {e}")
                return []

        raw_result = self.engine.run(
            strategy_name=strategy_name,
            start_date=start_date,
            end_date=end_date,
            get_trade_dates=get_trade_dates,
            get_factors_snapshot=get_factors_snapshot,
            get_kline_snapshot=get_kline_snapshot,
            run_strategy_fn=run_strategy,
        )

        # 计算风险指标
        nav = raw_result["nav"]
        returns = raw_result["portfolio_returns"]
        metrics = compute_metrics(nav, returns)

        # 平均换手率
        turnover_history = raw_result.get("turnover_history", [])
        avg_turnover = (
            round(sum(turnover_history) / len(turnover_history), 4)
            if turnover_history
            else 0.0
        )
        metrics["avg_turnover"] = avg_turnover

        return {
            "strategy_name": strategy_name,
            "start_date": start_date,
            "end_date": end_date,
            "period": {
                "start": start_date,
                "end": end_date,
                "rebalance_count": raw_result["rebalance_count"],
            },
            "metrics": metrics,
            "nav_series": nav,
            "returns": returns,
            "turnover_history": turnover_history,
        }

    def get_available_dates(self) -> dict:
        """
        获取可用于回测的日期范围。

        Returns:
            dict with start_date, end_date, trade_date_count
        """
        from sqlmodel import select
        from app.models import Kline

        with self.db.get_session() as session:
            min_date = session.exec(
                select(Kline.trade_date).order_by(Kline.trade_date).limit(1)
            ).first()
            max_date = session.exec(
                select(Kline.trade_date).order_by(Kline.trade_date.desc()).limit(1)
            ).first()

        if not min_date or not max_date:
            return {
                "start_date": None,
                "end_date": None,
                "trade_date_count": 0,
            }

        sd = _parse_date(min_date)
        ed = _parse_date(max_date)
        trade_dates = get_trade_dates_between(sd, ed)

        return {
            "start_date": min_date,
            "end_date": max_date,
            "trade_date_count": len(trade_dates),
        }


def _parse_date(value) -> date:
    """将字符串或 date 解析为 date 对象"""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.fromisoformat(value).date()
    raise TypeError(f"Cannot parse date from {type(value)}: {value}")
