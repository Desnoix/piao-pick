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

import pandas as pd

from app.core.backtest.engine import BacktestEngine
from app.core.backtest.metrics import compute_metrics
from app.core.strategy.executor import StrategyExecutor
from app.core.strategy.loader import StrategyLoader
from app.core.trading_calendar import get_trade_dates_between
from app.database import get_db
from app.repositories.factor_repo import FactorRepository
from app.repositories.stock_repo import StockRepository
from app.services.icir_service import IcirService

logger = logging.getLogger(__name__)


class BacktestService:
    """回测服务"""

    def __init__(self):
        self.engine = BacktestEngine()
        self.strategy_loader = StrategyLoader()
        self.db = get_db()
        self._stock_repo: StockRepository | None = None
        self._factor_repo: FactorRepository | None = None
        self._icir_service: IcirService | None = None

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

    @property
    def icir_service(self) -> IcirService:
        if self._icir_service is None:
            self._icir_service = IcirService()
        return self._icir_service

    def run_backtest(
        self,
        strategy_name: str,
        start_date: str,
        end_date: str,
        commission_rate: float = 0.0003,
        stamp_tax: float = 0.0005,
        slippage: float = 0.001,
    ) -> dict:
        """
        执行回测（含交易成本扣除）。

        Args:
            strategy_name: 策略名称 (YAML 文件名不含 .yaml)
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            commission_rate: 单边佣金费率 (默认 0.0003, 万三)
            stamp_tax: 卖出印花税 (默认 0.0005, 万五)
            slippage: 单边滑点 (默认 0.001, 千一)

        Returns:
            dict with strategy_name, start_date, end_date, period, metrics,
            nav_series, returns, turnover_history
        """
        logger.info(f"Starting backtest: {strategy_name}, {start_date} ~ {end_date}")

        # 预加载策略配置，避免每次选股都重新加载
        strategy = self.strategy_loader.load_by_name(strategy_name)
        if strategy is None:
            raise ValueError(f"Strategy not found: {strategy_name}")

        executor = StrategyExecutor(icir_snapshot_fn=self._make_icir_snapshot_fn(strategy_name, strategy))

        def get_trade_dates(start: str, end: str) -> list:
            """获取交易日列表，返回 date 对象"""
            sd = _parse_date(start)
            ed = _parse_date(end)
            return get_trade_dates_between(sd, ed)

        # ── 预加载全区间因子到内存 ──
        logger.info(f"Preloading factors: {start_date} ~ {end_date}")
        range_df = self.factor_repo.get_factors_range(start_date, end_date)
        factor_cache = _build_factor_cache(range_df)
        logger.info(f"Factor cache built: {len(factor_cache)} dates, {len(range_df)} rows loaded")

        def get_factors_snapshot(rdate) -> pd.DataFrame:
            """获取某日因子快照 (从内存缓存取)"""
            date_str = rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate)
            return factor_cache.get(date_str, pd.DataFrame())

        def get_kline_snapshot(rdate) -> pd.DataFrame:
            """获取某日行情快照"""
            date_str = rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate)
            return self.stock_repo.get_kline_snapshot(date_str)

        def run_strategy(name: str, rdate, factors: pd.DataFrame) -> list:
            """运行策略选股，返回 ts_code 列表"""
            stock_info_df = self.stock_repo.get_all_stock_info_df()
            trade_date_str = rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate)
            try:
                result_df = executor.execute(strategy, factors, stock_info_df, trade_date=trade_date_str)
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
            commission_rate=commission_rate,
            stamp_tax=stamp_tax,
            slippage=slippage,
        )

        # 计算风险指标
        nav = raw_result["nav"]
        returns = raw_result["portfolio_returns"]

        # 构建基准 NAV (沪深 300)
        benchmark_nav = self._build_benchmark_nav(nav)

        metrics = compute_metrics(nav, returns, benchmark_nav=benchmark_nav)

        # 平均换手率
        turnover_history = raw_result.get("turnover_history", [])
        avg_turnover = round(sum(turnover_history) / len(turnover_history), 4) if turnover_history else 0.0
        metrics["avg_turnover"] = avg_turnover

        # 成本统计
        metrics["total_cost"] = raw_result.get("total_cost", 0.0)
        metrics["avg_cost_per_period"] = raw_result.get("avg_cost_per_period", 0.0)

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
            "benchmark_nav": self._extract_benchmark_nav_dict(benchmark_nav),
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
            min_date = session.exec(select(Kline.trade_date).order_by(Kline.trade_date).limit(1)).first()
            max_date = session.exec(select(Kline.trade_date).order_by(Kline.trade_date.desc()).limit(1)).first()

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

    def _make_icir_snapshot_fn(
        self,
        strategy_name: str,
        strategy,
    ):
        """
        构建 ICIR 快照回调函数, 供 StrategyExecutor 在 icir 方法中使用。

        Args:
            strategy_name: 策略名称
            strategy: StrategyConfig 对象 (提供 lookback / min_periods 参数)

        Returns:
            callable(strategy_name, trade_date) -> dict[str, float] | None
        """
        lookback = strategy.icir_lookback
        min_periods = strategy.icir_min_periods
        svc = self.icir_service

        def _get_icir(name: str, trade_date: str) -> dict[str, float] | None:
            return svc.get_icir_snapshot(
                strategy_name=name,
                trade_date=trade_date,
                lookback=lookback,
                min_periods=min_periods,
            )

        return _get_icir

    def _build_benchmark_nav(self, strategy_nav: list) -> list | None:
        """
        根据策略净值日期序列，获取沪深 300 基准 NAV。

        返回格式与 strategy_nav 一致: [(date_iso, close_value), ...]
        close_value 为原始收盘价 (不归一化，归一化在 metrics.py 中做)。
        """
        if not strategy_nav:
            return None

        dates = [d for d, _ in strategy_nav]
        start_date = dates[0]
        end_date = dates[-1]

        df = self.stock_repo.get_index_kline_range("000300", start_date, end_date)
        if df.empty:
            logger.warning("No benchmark data found for 000300")
            return None

        # 构建日期->收盘价映射
        price_map = dict(zip(df["trade_date"], df["close"]))

        # 按策略调仓日期提取基准收盘价
        result = []
        for d in dates:
            close = price_map.get(d)
            if close is not None:
                result.append((d, float(close)))
            else:
                # 如果该日无数据 (节假日等)，用上一个有效值
                if result:
                    result.append((d, result[-1][1]))

        return result if len(result) >= 2 else None

    def _extract_benchmark_nav_dict(self, benchmark_nav: list | None) -> list | None:
        """
        将基准 NAV 归一化为从 1.0 开始，返回 [(date, normalized_nav), ...]。
        用于前端直接绘制对比曲线。
        """
        if not benchmark_nav or len(benchmark_nav) < 2:
            return None

        first_close = benchmark_nav[0][1]
        if first_close <= 0:
            return None

        return [(d, round(v / first_close, 4)) for d, v in benchmark_nav]


def _parse_date(value) -> date:
    """将字符串或 date 解析为 date 对象"""
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        return datetime.fromisoformat(value).date()
    raise TypeError(f"Cannot parse date from {type(value)}: {value}")


def _build_factor_cache(range_df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    将区间因子 DataFrame 按 trade_date 拆分为字典。

    Args:
        range_df: get_factors_range() 的返回值, 含 trade_date 和 ts_code 列

    Returns:
        Dict[str, pd.DataFrame], key=日期, value=当日因子快照 (index=ts_code)
    """
    if range_df.empty:
        return {}

    cache = {}
    for date_str, group in range_df.groupby("trade_date"):
        snapshot = group.drop(columns=["trade_date"]).set_index("ts_code")
        cache[date_str] = snapshot

    return cache
