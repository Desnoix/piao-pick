"""
P2-2 回测因子缓存的结果一致性验证。

对比优化前 (逐日 DB 查询) 与优化后 (内存缓存) 的回测输出，确保结果完全一致。

运行: cd backend && python tests/test_backtest_cache_consistency.py
"""

import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.database import get_db
from app.repositories.factor_repo import FactorRepository
from app.repositories.stock_repo import StockRepository
from app.services.backtest_service import BacktestService, _parse_date

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def build_baseline(strategy_name: str, start_date: str, end_date: str) -> dict:
    """用原始逐日查询方式运行回测 (绕过缓存)。"""
    from app.core.backtest.engine import BacktestEngine
    from app.core.backtest.metrics import compute_metrics
    from app.core.strategy.executor import StrategyExecutor
    from app.core.strategy.loader import StrategyLoader
    from app.core.trading_calendar import get_trade_dates_between

    db = get_db()
    factor_repo = FactorRepository(db)
    stock_repo = StockRepository(db)
    engine = BacktestEngine()
    loader = StrategyLoader()
    executor = StrategyExecutor()
    strategy = loader.load_by_name(strategy_name)
    if strategy is None:
        raise ValueError(f"Strategy not found: {strategy_name}")

    def get_trade_dates(s, e):
        return get_trade_dates_between(_parse_date(s), _parse_date(e))

    def get_factors_snapshot(rdate):
        ds = rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate)
        return factor_repo.get_factors_snapshot(ds)

    def get_kline_snapshot(rdate):
        ds = rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate)
        return stock_repo.get_kline_snapshot(ds)

    def run_strategy(name, rdate, factors):
        info = stock_repo.get_all_stock_info_df()
        trade_date_str = rdate.isoformat() if hasattr(rdate, "isoformat") else str(rdate)
        try:
            res = executor.execute(strategy, factors, info, trade_date=trade_date_str)
            return res["ts_code"].tolist() if not res.empty else []
        except Exception as e:
            logger.error(f"Strategy failed: {e}")
            return []

    raw = engine.run(
        strategy_name=strategy_name,
        start_date=start_date,
        end_date=end_date,
        get_trade_dates=get_trade_dates,
        get_factors_snapshot=get_factors_snapshot,
        get_kline_snapshot=get_kline_snapshot,
        run_strategy_fn=run_strategy,
    )
    metrics = compute_metrics(raw["nav"], raw["portfolio_returns"])
    return {
        "nav": raw["nav"],
        "returns": raw["portfolio_returns"],
        "turnover_history": raw["turnover_history"],
        "metrics": metrics,
    }


def compare(baseline: dict, cached: dict) -> bool:
    ok = True
    # NAV
    if len(baseline["nav"]) != len(cached["nav"]):
        logger.error("NAV length mismatch")
        ok = False
    else:
        for i, ((bd, bv), (cd, cv)) in enumerate(zip(baseline["nav"], cached["nav"])):
            if bd != cd:
                logger.error(f"NAV date [{i}]: {bd} vs {cd}")
                ok = False
            if abs(bv - cv) > 1e-10:
                logger.error(f"NAV val [{i}]: {bv} vs {cv}")
                ok = False
    # Returns
    if len(baseline["returns"]) != len(cached["returns"]):
        logger.error("Returns length mismatch")
        ok = False
    else:
        for i, (bv, cv) in enumerate(zip(baseline["returns"], cached["returns"])):
            if abs(bv - cv) > 1e-10:
                logger.error(f"Return [{i}]: {bv} vs {cv}")
                ok = False
    # Turnover
    if baseline["turnover_history"] != cached["turnover_history"]:
        logger.error("Turnover mismatch")
        ok = False
    # Metrics
    for k, bv in baseline["metrics"].items():
        cv = cached["metrics"].get(k)
        if isinstance(bv, float):
            if cv is None or abs(bv - cv) > 1e-6:
                logger.error(f"Metric '{k}': {bv} vs {cv}")
                ok = False
        elif bv != cv:
            logger.error(f"Metric '{k}': {bv} vs {cv}")
            ok = False
    return ok


def main():
    strategy_name = "value_lowvol"
    start_date, end_date = "2023-01-01", "2025-12-31"
    logger.info(f"=== P2-2 Cache Consistency: {strategy_name} {start_date}~{end_date} ===")

    logger.info("--- Baseline (per-day DB) ---")
    t0 = time.time()
    baseline = build_baseline(strategy_name, start_date, end_date)
    t_base = time.time() - t0

    logger.info("--- Optimized (in-memory cache) ---")
    t0 = time.time()
    cached = BacktestService().run_backtest(strategy_name, start_date, end_date)
    t_opt = time.time() - t0

    consistent = compare(baseline, cached)
    speedup = t_base / t_opt if t_opt > 0 else float("inf")

    logger.info(f"Baseline:  {t_base:.2f}s")
    logger.info(f"Optimized: {t_opt:.2f}s")
    logger.info(f"Speedup:   {speedup:.1f}x")
    logger.info(f"Result:    {'PASS' if consistent else 'FAIL'}")
    sys.exit(0 if consistent else 1)


if __name__ == "__main__":
    main()
