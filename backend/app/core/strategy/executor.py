# -*- coding: utf-8 -*-
"""
策略执行器

执行选股策略：对因子加权评分、排序、筛选。
"""

import logging

import pandas as pd

from app.core.strategy.loader import StrategyConfig
from app.core.factor.base import FactorPipeline

logger = logging.getLogger(__name__)


class StrategyExecutor:
    """
    策略执行引擎。

    执行流程：
    1. Universe filtering（基于 stock_info 过滤不合格股票）
    2. Factor processing（极值处理、标准化、方向对齐）
    3. Composite scoring（加权综合得分，归一化到 0-100）
    4. Post-scoring filters（行业分散化、top N 等）
    5. Ranking & enrichment
    """

    def __init__(self):
        self.factor_pipeline = FactorPipeline()
        logger.info("StrategyExecutor initialized")

    def execute(
        self,
        strategy: StrategyConfig,
        factors_df: pd.DataFrame,
        stock_info_df: pd.DataFrame,
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
        filtered = self._filter_universe(factors_df, stock_info_df, strategy.universe)
        logger.info(f"  Universe: {len(factors_df)} -> {len(filtered)} after filtering")

        if filtered.empty:
            logger.warning(f"No stocks remaining after universe filtering for {strategy.name}")
            return pd.DataFrame(
                columns=["ts_code", "composite_score", "rank", "status"]
            )

        # Step 2: Factor processing (极值处理、标准化、方向对齐)
        processed = self.factor_pipeline.process(filtered, strategy.factors)

        # Step 3: Composite scoring (加权综合得分)
        scores = self.factor_pipeline.composite_score(processed, strategy.factors)

        # Step 4: Build result DataFrame
        result = pd.DataFrame({
            "ts_code": processed.index,
            "composite_score": scores.values,
        })
        result = result.sort_values(
            "composite_score", ascending=False
        ).reset_index(drop=True)

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
                cutoff = (date.today() - timedelta(days=min_days)).isoformat()
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

    def _enrich_with_stock_info(
        self, result: pd.DataFrame, stock_info_df: pd.DataFrame
    ) -> pd.DataFrame:
        """Enrich results with stock name, industry etc."""
        enrich_cols = [c for c in ("name", "industry") if c in stock_info_df.columns]
        if enrich_cols:
            info = stock_info_df[enrich_cols].reset_index()
            result = result.merge(info, on="ts_code", how="left")
        return result


def _is_bse_code(ts_code: str) -> bool:
    """
    判断是否为北交所股票代码。

    北交所代码特征：以 8 开头（83xxxx, 87xxxx, 88xxxx）或以 4 开头（43xxxx）
    """
    if not ts_code:
        return False
    code = ts_code.split(".")[0] if "." in ts_code else ts_code
    return code.startswith(("8", "4"))
