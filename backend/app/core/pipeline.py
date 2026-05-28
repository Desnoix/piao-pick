"""
选股管道

编排完整的多因子选股流程：
策略加载 → 数据准备 → 股票池过滤 → 因子处理 → 策略评分 → 结果保存
"""

import json
import logging
import uuid
from collections.abc import Callable
from datetime import datetime

import pandas as pd

from app.config import get_config
from app.core.strategy.executor import StrategyExecutor
from app.core.strategy.loader import StrategyLoader
from app.database import DatabaseManager, get_db
from app.models.selection import SelectionResult
from app.repositories.factor_repo import FactorRepository
from app.repositories.selection_repo import SelectionRepository
from app.repositories.stock_repo import StockRepository
from app.repositories.strategy_repo import StrategyRepository

logger = logging.getLogger(__name__)


class SelectionPipeline:
    """
    多因子选股管道。

    执行流程：
    1. 加载策略配置 (StrategyLoader)
    2. 获取因子快照数据 (FactorRepository)
    3. 获取股票基本信息 (StockRepository)
    4. 执行策略 (StrategyExecutor, 支持 fixed / icir / equal 合成)
    5. 保存结果到 selection_results 表
    """

    def __init__(
        self,
        config=None,
        progress_callback: Callable[[int, str], None] | None = None,
    ):
        self.config = config or get_config()
        self.progress_callback = progress_callback
        self.db: DatabaseManager = get_db()
        self.strategy_loader = StrategyLoader()
        self.executor = StrategyExecutor(icir_snapshot_fn=self._get_icir_snapshot)
        self.stock_repo = StockRepository(self.db)
        self.factor_repo = FactorRepository(self.db)
        self.strategy_repo = StrategyRepository(self.db)
        self.selection_repo = SelectionRepository(self.db)
        self._icir_service = None  # 懒加载
        logger.info("SelectionPipeline initialized")

    def _get_icir_snapshot(self, strategy_name: str, trade_date: str) -> dict[str, float] | None:
        """
        ICIR 快照回调: 供 StrategyExecutor 在 icir 合成方法中调用。

        从策略配置读取 lookback/min_periods 参数后委托给 IcirService。
        懒加载 IcirService 以避免循环导入。
        """
        if self._icir_service is None:
            from app.services.icir_service import IcirService

            self._icir_service = IcirService()

        strategy = self.strategy_loader.load_by_name(strategy_name)
        if strategy is None:
            return None
        return self._icir_service.get_icir_snapshot(
            strategy_name=strategy_name,
            trade_date=trade_date,
            lookback=strategy.icir_lookback,
            min_periods=strategy.icir_min_periods,
        )

    def _emit_progress(self, progress: int, message: str):
        """Emit progress update to callback and logger."""
        if self.progress_callback:
            self.progress_callback(progress, message)
        logger.info(f"[Pipeline {progress}%] {message}")

    def run(
        self,
        strategy_name: str | None = None,
        trade_date: str | None = None,
        strategy_id: str | None = None,
    ) -> dict:
        """
        Run selection pipeline for a given strategy and date.

        Args:
            strategy_name: Strategy name (YAML file name, e.g. 'value_lowvol')
            trade_date: Trading date string (YYYY-MM-DD). If None, uses latest.
            strategy_id: Deprecated backward-compat param. If provided and
                         strategy_name is None, resolves strategy by DB id.

        Returns:
            dict with trade_date, strategy_name, universe_count,
            final_count, results (list of dicts)
        """
        # Resolve strategy name from DB id if needed (backward compat)
        if strategy_name is None and strategy_id is not None:
            db_strategy = self.strategy_repo.get_by_id(strategy_id)
            if db_strategy is not None:
                strategy_name = db_strategy.name
            else:
                raise ValueError(f"Strategy not found by id: {strategy_id}")

        if strategy_name is None:
            raise ValueError("strategy_name or strategy_id is required")

        # Step 1: Resolve trading date
        if trade_date is None:
            from app.core.trading_calendar import get_effective_trading_date

            trade_date = get_effective_trading_date().isoformat()

        self._emit_progress(10, f"Loading strategy: {strategy_name}")

        # Step 2: Load strategy config from YAML
        strategy = self.strategy_loader.load_by_name(strategy_name)
        if strategy is None:
            raise ValueError(f"Strategy not found: {strategy_name}")

        # Step 3: Ensure strategy exists in DB (for saving results with strategy_id)
        db_strategy = self.strategy_repo.get_by_name(strategy_name)
        if db_strategy is None:
            # Auto-create from YAML config
            from app.models.strategy import Strategy

            db_strategy = Strategy(
                id=str(uuid.uuid4()),
                name=strategy.name,
                display_name=strategy.display_name,
                description=strategy.description,
                category=strategy.category,
                config=json.dumps(strategy.raw, ensure_ascii=False),
                is_active=strategy.default_active,
                priority=strategy.default_priority,
                created_at=datetime.now().isoformat(),
                updated_at=datetime.now().isoformat(),
            )
            self.strategy_repo.create(db_strategy)
            logger.info(f"Auto-created strategy in DB: {strategy_name}")

        strategy_db_id = db_strategy.id

        # Step 4: Load factors snapshot
        self._emit_progress(20, f"Loading factors for {trade_date}")
        factors_snapshot = self.factor_repo.get_factors_snapshot(trade_date)

        if factors_snapshot.empty:
            self._emit_progress(100, f"No factor data for {trade_date}")
            return {
                "trade_date": trade_date,
                "strategy_name": strategy.display_name or strategy.name,
                "universe_count": 0,
                "final_count": 0,
                "results": [],
            }

        # Step 5: Load stock info
        self._emit_progress(40, "Loading stock info")
        stock_info_df = self.stock_repo.get_all_stock_info_df()

        # Step 6: Execute strategy
        self._emit_progress(60, f"Executing strategy: {strategy.name}")
        results_df = self.executor.execute(strategy, factors_snapshot, stock_info_df, trade_date=trade_date)

        # Step 7: Save results to DB
        self._emit_progress(80, f"Saving {len(results_df)} results")
        self._save_results(strategy_db_id, trade_date, results_df)

        self._emit_progress(100, f"Complete: {len(results_df)} stocks selected")

        return {
            "trade_date": trade_date,
            "strategy_name": strategy.display_name or strategy.name,
            "universe_count": len(factors_snapshot),
            "final_count": len(results_df),
            "results": results_df.to_dict("records"),
        }

    def _save_results(
        self,
        strategy_id: str,
        trade_date: str,
        results_df: pd.DataFrame,
    ) -> int:
        """
        Save selection results to database.

        Deletes existing results for the same strategy+date first,
        then upserts the new results.
        """
        # Delete existing results for this strategy+date
        deleted = self.selection_repo.delete_by_strategy_date(strategy_id, trade_date)
        if deleted:
            logger.info(f"Deleted {deleted} existing results for strategy={strategy_id}, date={trade_date}")

        if results_df.empty:
            return 0

        now = datetime.now().isoformat()
        selection_results = []

        for _, row in results_df.iterrows():
            # Build factor snapshot: per-factor Z-Scores (typical [-3, +3])
            factor_snap = {}
            for col in results_df.columns:
                if col not in ("ts_code", "composite_score", "rank", "status", "name", "industry"):
                    val = row.get(col)
                    if val is not None and not (isinstance(val, float) and pd.isna(val)):
                        factor_snap[col] = val

            result = SelectionResult(
                strategy_id=strategy_id,
                ts_code=row["ts_code"],
                trade_date=trade_date,
                rank=int(row.get("rank", 0)),
                composite_score=float(row.get("composite_score", 0)),
                status=row.get("status", "OK"),
                factor_snapshot=json.dumps(factor_snap, ensure_ascii=False) if factor_snap else None,
                created_at=now,
            )
            selection_results.append(result)

        count = self.selection_repo.upsert_batch(selection_results)
        logger.info(f"Saved {count} selection results")
        return count
