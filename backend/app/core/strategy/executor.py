"""
策略执行器

执行选股策略：对因子加权评分、排序、筛选。
支持三种因子合成方法: fixed (默认) / icir (动态赋权) / equal (等权)。
"""

import logging
from collections.abc import Callable

import pandas as pd

from app.core.factor.base import FactorPipeline
from app.core.strategy.loader import StrategyConfig

logger = logging.getLogger(__name__)


class StrategyExecutor:
    """
    策略执行引擎。

    执行流程：
    1. Universe filtering（基于 stock_info 过滤不合格股票）
    2. Factor processing（极值处理、标准化、方向对齐）
    3. Composite scoring（加权综合得分，支持 fixed / icir / equal 三种方法）
    4. Post-scoring filters（行业分散化、top N 等）
    5. Ranking & enrichment
    """

    def __init__(self, icir_snapshot_fn: Callable | None = None):
        """
        Args:
            icir_snapshot_fn: callable(strategy_name, trade_date) -> dict[str, float]
                返回各因子的 ICIR 值。若为 None 或返回 None, icir 方法降级到 equal。
        """
        self.factor_pipeline = FactorPipeline()
        self.icir_snapshot_fn = icir_snapshot_fn
        logger.info("StrategyExecutor initialized")

    def execute(
        self,
        strategy: StrategyConfig,
        factors_df: pd.DataFrame,
        stock_info_df: pd.DataFrame,
        trade_date: str | None = None,
    ) -> pd.DataFrame:
        """
        执行策略: 过滤 -> 打分 -> 排序。

        Args:
            strategy: 策略配置
            factors_df: 因子数据 DataFrame, index=ts_code, columns=factor_ids
            stock_info_df: 股票基本信息 DataFrame, index=ts_code

        Returns:
            排序后的 DataFrame with columns:
                ts_code, composite_score, rank, status, name, industry
        """
        logger.info(f"Executing strategy: {strategy.name}")

        # Step 1: Universe filtering
        filtered = self._filter_universe(factors_df, stock_info_df, strategy.universe, trade_date=trade_date)
        logger.info(f"  Universe: {len(factors_df)} -> {len(filtered)} after filtering")

        if filtered.empty:
            logger.warning(f"No stocks remaining after universe filtering for {strategy.name}")
            return pd.DataFrame(columns=["ts_code", "composite_score", "rank", "status"])

        # Step 2: Factor processing (极值处理、标准化、中性化、方向对齐)
        pipeline_cfg = strategy.factor_pipeline
        processed = self.factor_pipeline.process(
            raw_factors=filtered,
            factor_config=strategy.factors,
            stock_info_df=stock_info_df,
            neutralization_config=getattr(strategy, "neutralization", None),
            winsorize_method=pipeline_cfg.get("winsorize_method", "mad"),
            winsorize_n_mad=pipeline_cfg.get("winsorize_n_mad", 5.0),
            winsorize_limits_sigma=tuple(pipeline_cfg.get("winsorize_limits_sigma", [-3.0, 3.0])),
        )

        # Step 3: Composite scoring (根据 composite_method 选择赋权方法)
        scores = self._compute_composite(strategy, processed, trade_date)

        # Step 4: Build result DataFrame
        result = pd.DataFrame(
            {
                "ts_code": processed.index,
                "composite_score": scores.values,
            }
        )
        result = result.sort_values("composite_score", ascending=False).reset_index(drop=True)

        # Step 5: Apply post-scoring filters
        result = self._apply_filters(result, processed, stock_info_df, strategy.filters)

        # Step 6: Rank
        result = result.reset_index(drop=True)
        result["rank"] = range(1, len(result) + 1)
        result["status"] = "OK"

        # Step 7: Limit output
        max_stocks = strategy.output.get("max_stocks", 30)
        result = result.head(max_stocks).copy()

        # Step 8: Enrich with stock info
        result = self._enrich_with_stock_info(result, stock_info_df)

        logger.info(f"  Result: {len(result)} stocks selected")
        return result

    def _filter_universe(
        self,
        factors_df: pd.DataFrame,
        stock_info_df: pd.DataFrame,
        universe_config: dict,
        trade_date: str | None = None,
    ) -> pd.DataFrame:
        """
        Apply universe filters to exclude ineligible stocks.

        Filters:
        - exclude_st: remove ST stocks
        - exclude_suspended: remove suspended stocks
        - exclude_new_listing_days: remove newly listed stocks
        - exclude_bse: remove BSE (北交所) stocks
        - min_market_cap: minimum market cap (not available in stock_info, skipped here)
        """
        mask = pd.Series(True, index=factors_df.index)

        if universe_config.get("exclude_st", False):
            if "is_st" in stock_info_df.columns:
                st_mask = ~stock_info_df["is_st"].astype(bool)
                mask = mask & st_mask.reindex(mask.index, fill_value=True)

        if universe_config.get("exclude_suspended", False):
            if "is_suspended" in stock_info_df.columns:
                susp_mask = ~stock_info_df["is_suspended"].astype(bool)
                mask = mask & susp_mask.reindex(mask.index, fill_value=True)

        if "exclude_new_listing_days" in universe_config:
            min_days = universe_config["exclude_new_listing_days"]
            if "list_date" in stock_info_df.columns:
                from datetime import date, timedelta

                ref_date = date.fromisoformat(trade_date) if trade_date else date.today()
                cutoff = (ref_date - timedelta(days=min_days)).isoformat()
                new_mask = stock_info_df["list_date"].fillna("1900-01-01") <= cutoff
                mask = mask & new_mask.reindex(mask.index, fill_value=True)

        if universe_config.get("exclude_bse", False):
            bse_mask = ~pd.Series(
                [_is_bse_code(code) for code in factors_df.index],
                index=factors_df.index,
            )
            mask = mask & bse_mask

        return factors_df[mask]

    def _apply_filters(
        self,
        result: pd.DataFrame,
        processed: pd.DataFrame,
        stock_info_df: pd.DataFrame,
        filters_config: list,
    ) -> pd.DataFrame:
        """Delegate to app.core.strategy.filters.apply_filters"""
        from app.core.strategy.filters import apply_filters

        return apply_filters(result, processed, stock_info_df, filters_config)

    def _enrich_with_stock_info(self, result: pd.DataFrame, stock_info_df: pd.DataFrame) -> pd.DataFrame:
        """Enrich results with stock name, industry etc."""
        enrich_cols = [c for c in ("name", "industry") if c in stock_info_df.columns]
        if enrich_cols:
            info = stock_info_df[enrich_cols].reset_index()
            result = result.merge(info, on="ts_code", how="left")
        return result

    def _compute_composite(
        self,
        strategy: StrategyConfig,
        processed: pd.DataFrame,
        trade_date: str | None,
    ) -> pd.Series:
        """
        根据 composite_method 选择因子合成方法。

        三种方法:
        - equal: 等权, 直接用 processed 的所有列
        - icir:  ICIR 动态赋权 (需 icir_snapshot_fn 提供 ICIR 数据)
        - fixed: YAML 固定权重 (默认, 与原逻辑一致)

        Args:
            strategy: 策略配置 (含 composite_method, max_single_weight 等)
            processed: 处理后的因子 DataFrame
            trade_date: 当前交易日期 (用于 ICIR 窗口截取)

        Returns:
            综合得分 Series
        """
        from app.core.factor.dynamic_weight import compute_dynamic_weights

        method = strategy.composite_method
        available_factors = [f for f in strategy.factors if f["id"] in processed.columns]

        if method == "equal":
            return self.factor_pipeline.equal_weight_composite(processed)

        # 构建 fallback_weights (YAML 中定义的权重)
        fallback = {f["id"]: f.get("weight", 1.0) for f in available_factors}

        if method == "icir":
            # 获取 ICIR 快照
            icir_snap = None
            if self.icir_snapshot_fn and trade_date is not None:
                try:
                    icir_snap = self.icir_snapshot_fn(strategy.name, trade_date)
                except Exception as e:
                    logger.warning(f"ICIR snapshot failed: {e}, falling back to fixed")

            factor_ids = [f["id"] for f in available_factors]
            weights = compute_dynamic_weights(
                factor_ids=factor_ids,
                icir_snapshot=icir_snap,
                fallback_weights=fallback,
                method="icir",
                max_single_weight=strategy.max_single_weight,
            )
            logger.info(f"  ICIR weights: {_round_weights(weights)}")
            return self.factor_pipeline.icir_weighted_composite(processed, weights)

        # method == "fixed" (默认, 与原行为完全一致)
        return self.factor_pipeline.composite_score(processed, strategy.factors)


def _round_weights(weights: dict[str, float], decimals: int = 4) -> dict[str, float]:
    """截断权重显示精度, 用于日志输出"""
    return {k: round(v, decimals) for k, v in weights.items()}


def _is_bse_code(ts_code: str) -> bool:
    """
    判断是否为北交所股票代码。

    北交所代码特征：以 8 开头（83xxxx, 87xxxx, 88xxxx）或以 4 开头（43xxxx）
    """
    if not ts_code:
        return False
    code = ts_code.split(".")[0] if "." in ts_code else ts_code
    return code.startswith(("8", "4"))
