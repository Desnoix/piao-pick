"""
过滤器函数

定义选股流程中的各种过滤规则：
- percentile_top: 取评分前 N 名
- threshold: 评分高于阈值
- industry_diversify: 行业分散化
- market_cap_min: 最小市值
- universe filtering: ST/停牌/北交所/次新股
"""

import logging

import pandas as pd

logger = logging.getLogger(__name__)


def apply_filters(
    result: pd.DataFrame,
    processed: pd.DataFrame,
    stock_info_df: pd.DataFrame,
    filters_config: list,
) -> pd.DataFrame:
    """
    Apply all configured filters sequentially.

    Args:
        result: DataFrame with ts_code, composite_score columns
        processed: Processed factor DataFrame (index=ts_code)
        stock_info_df: Stock info DataFrame (index=ts_code)
        filters_config: List of filter config dicts with 'type' key

    Returns:
        Filtered DataFrame
    """
    for f in filters_config:
        filter_type = f.get("type", "")
        before_count = len(result)

        if filter_type == "percentile_top":
            result = filter_percentile_top(result, f.get("count", 100))
        elif filter_type == "threshold":
            result = filter_threshold(result, f.get("value", 0.0))
        elif filter_type == "industry_diversify":
            result = filter_industry_diversify(result, stock_info_df, f.get("max_per_industry", 5))
        elif filter_type == "market_cap_min":
            result = filter_market_cap_min(result, stock_info_df, f.get("value", 0))
        else:
            logger.warning(f"Unknown filter type: {filter_type}")

        logger.debug(f"  Filter '{filter_type}': {before_count} -> {len(result)}")

    return result


def filter_universe(
    stock_df: pd.DataFrame,
    universe_config: dict,
    trade_date: str | None = None,
) -> pd.DataFrame:
    """
    股票池过滤。

    根据 universe 配置过滤不合格的股票：
    - exclude_st: 排除 ST 股
    - exclude_new_listing_days: 排除次新股（上市天数不足）
    - exclude_suspended: 排除停牌股
    - exclude_bse: 排除北交所股票
    - min_market_cap: 最小市值
    - min_daily_amount: 最小日均成交额

    Args:
        stock_df: 股票 DataFrame with index=ts_code
        universe_config: universe 配置字典

    Returns:
        过滤后的 DataFrame
    """
    from datetime import date, timedelta

    mask = pd.Series(True, index=stock_df.index)

    if universe_config.get("exclude_st", False):
        if "is_st" in stock_df.columns:
            mask = mask & ~stock_df["is_st"].astype(bool)

    if universe_config.get("exclude_suspended", False):
        if "is_suspended" in stock_df.columns:
            mask = mask & ~stock_df["is_suspended"].astype(bool)

    if "exclude_new_listing_days" in universe_config:
        min_days = universe_config["exclude_new_listing_days"]
        if "list_date" in stock_df.columns:
            ref_date = date.fromisoformat(trade_date) if trade_date else date.today()
            cutoff = (ref_date - timedelta(days=min_days)).isoformat()
            mask = mask & (stock_df["list_date"].fillna("1900-01-01") <= cutoff)

    if universe_config.get("exclude_bse", False):
        codes = stock_df.index.astype(str)
        bse_mask = codes.str.match(r"^[84]")
        mask = mask & ~bse_mask

    return stock_df[mask]


def filter_percentile_top(
    scored_df: pd.DataFrame,
    count: int,
    score_column: str = "composite_score",
) -> pd.DataFrame:
    """
    取评分前 N 名。

    Args:
        scored_df: 已评分的 DataFrame (must be sorted by score desc)
        count: 取前 N 名
        score_column: 评分列名

    Returns:
        过滤后的 DataFrame
    """
    return scored_df.head(count).reset_index(drop=True)


def filter_threshold(
    scored_df: pd.DataFrame,
    threshold: float,
    score_column: str = "composite_score",
) -> pd.DataFrame:
    """
    评分高于阈值过滤。

    Args:
        scored_df: 已评分的 DataFrame
        threshold: 评分阈值
        score_column: 评分列名

    Returns:
        过滤后的 DataFrame
    """
    if score_column not in scored_df.columns:
        logger.warning(f"Score column '{score_column}' not found, skipping threshold filter")
        return scored_df
    return scored_df[scored_df[score_column] >= threshold].reset_index(drop=True)


def filter_industry_diversify(
    scored_df: pd.DataFrame,
    stock_info_df: pd.DataFrame = None,
    max_per_industry: int = 5,
    industry_column: str = "industry",
) -> pd.DataFrame:
    """
    行业分散化过滤。

    每个行业最多保留 max_per_industry 只股票。

    Args:
        scored_df: 已评分的 DataFrame
        stock_info_df: 股票基本信息 DataFrame (用于补充 industry 列)
        max_per_industry: 每行业最大保留数
        industry_column: 行业列名

    Returns:
        过滤后的 DataFrame
    """
    df = scored_df.copy()

    if industry_column not in df.columns:
        if stock_info_df is not None and industry_column in stock_info_df.columns:
            info = stock_info_df[[industry_column]].reset_index()
            df = df.merge(info, on="ts_code", how="left")

    if industry_column not in df.columns:
        logger.warning(f"Industry column '{industry_column}' not available, skipping industry diversify filter")
        return scored_df

    industry_counts: dict[str, int] = {}
    keep_indices = []

    for idx, row in df.iterrows():
        industry = row.get(industry_column) or "unknown"
        industry_counts[industry] = industry_counts.get(industry, 0) + 1
        if industry_counts[industry] <= max_per_industry:
            keep_indices.append(idx)

    return df.loc[keep_indices].reset_index(drop=True)


def filter_market_cap_min(
    result: pd.DataFrame,
    stock_info_df: pd.DataFrame,
    min_value: float,
) -> pd.DataFrame:
    """
    Filter by minimum market cap.

    Note: This filter uses 'market_cap' column from stock_info_df.
    If the column is not available, the filter is skipped.

    Args:
        result: Result DataFrame with ts_code column
        stock_info_df: Stock info DataFrame (index=ts_code)
        min_value: Minimum market cap value

    Returns:
        Filtered DataFrame
    """
    if "market_cap" not in stock_info_df.columns:
        logger.debug("market_cap column not available, skipping market_cap_min filter")
        return result

    cap_df = stock_info_df[["market_cap"]].reset_index()
    merged = result.merge(cap_df, on="ts_code", how="left")
    return merged[merged["market_cap"].fillna(0) >= min_value].reset_index(drop=True)
