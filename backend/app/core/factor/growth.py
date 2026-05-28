"""
成长因子

- Rev_Growth_YoY: 营业收入同比增长率
- Ear_Growth_YoY: 归母净利润同比增长率

数据由 FundamentalSyncTask 同步到 factor_daily:
- rev_growth_yoy: stock_yjbb_em 批量接口 (已激活)
- ear_growth_yoy: stock_yjbb_em 批量接口 (已激活)
"""

import pandas as pd


def compute_rev_growth_yoy(df: pd.DataFrame) -> pd.Series:
    """
    营收同比增长率 = (当期营收 - 去年同期营收) / 去年同期营收

    Args:
        df: 包含基本面数据的 DataFrame

    Returns:
        营收同比增长因子 Series
    """
    if "rev_growth_yoy" in df.columns:
        return df["rev_growth_yoy"].astype(float)
    if "revenue" in df.columns and "revenue_yoy" in df.columns:
        prev = df["revenue_yoy"].replace(0, float("nan"))
        return (df["revenue"] - df["revenue_yoy"]) / prev
    return pd.Series(dtype=float)


def compute_ear_growth_yoy(df: pd.DataFrame) -> pd.Series:
    """
    净利润同比增长率 = (当期净利润 - 去年同期净利润) / 去年同期净利润

    Args:
        df: 包含基本面数据的 DataFrame

    Returns:
        净利润同比增长因子 Series
    """
    if "ear_growth_yoy" in df.columns:
        return df["ear_growth_yoy"].astype(float)
    if "net_profit" in df.columns and "net_profit_yoy" in df.columns:
        prev = df["net_profit_yoy"].replace(0, float("nan"))
        return (df["net_profit"] - df["net_profit_yoy"]) / prev
    return pd.Series(dtype=float)
