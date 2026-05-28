"""
质量因子

- ROE_TTM: 净资产收益率 TTM = 归属净利润 TTM / 归属净资产
- Gross_Margin: 毛利率 = (营业收入 - 营业成本) / 营业收入

数据由 FundamentalSyncTask 同步到 factor_daily:
- roe_ttm: stock_yjbb_em 批量接口 (已激活)
- gross_margin: stock_financial_analysis_indicator 单股接口 (待激活)
"""

import pandas as pd


def compute_roe_ttm(df: pd.DataFrame) -> pd.Series:
    """
    净资产收益率 TTM = 归属净利润 TTM / 归属净资产

    Args:
        df: 包含基本面数据的 DataFrame

    Returns:
        ROE TTM 因子 Series
    """
    if "roe_ttm" in df.columns:
        return df["roe_ttm"].astype(float)
    if "net_profit_ttm" in df.columns and "net_asset" in df.columns:
        net_asset = df["net_asset"].replace(0, float("nan"))
        return df["net_profit_ttm"] / net_asset
    return pd.Series(dtype=float)


def compute_gross_margin(df: pd.DataFrame) -> pd.Series:
    """
    毛利率 = (营业收入 - 营业成本) / 营业收入

    Args:
        df: 包含基本面数据的 DataFrame

    Returns:
        毛利率因子 Series
    """
    if "gross_margin" in df.columns:
        return df["gross_margin"].astype(float)
    if "revenue" in df.columns and "cost" in df.columns:
        revenue = df["revenue"].replace(0, float("nan"))
        return (df["revenue"] - df["cost"]) / revenue
    return pd.Series(dtype=float)
