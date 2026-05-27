# -*- coding: utf-8 -*-
"""
估值因子

- PE_TTM: 市盈率 TTM = 总市值 / 归属净利润 TTM
- PB: 市净率 = 总市值 / 归属净资产
- PS_TTM: 市销率 TTM = 总市值 / 营业收入 TTM
- FCF_Yield: 自由现金流收益率 = 自由现金流 / 总市值

NOTE: 需要基本面数据 (净利润、净资产、营业收入、自由现金流),
当前为 stub 实现, 返回空 Series。后续从 AKShare 基本面数据填充。
"""

import pandas as pd


def compute_pe_ttm(df: pd.DataFrame) -> pd.Series:
    """
    市盈率 TTM = 总市值 / 归属净利润 TTM

    Args:
        df: 包含行情和基本面数据的 DataFrame

    Returns:
        PE TTM 因子 Series
    """
    if "pe_ttm" in df.columns:
        return df["pe_ttm"].astype(float)
    if "total_mv" in df.columns and "net_profit_ttm" in df.columns:
        net_profit = df["net_profit_ttm"].replace(0, float("nan"))
        return df["total_mv"] / net_profit
    return pd.Series(dtype=float)


def compute_pb(df: pd.DataFrame) -> pd.Series:
    """
    市净率 = 总市值 / 归属净资产

    Args:
        df: 包含行情和基本面数据的 DataFrame

    Returns:
        PB 因子 Series
    """
    if "pb" in df.columns:
        return df["pb"].astype(float)
    if "total_mv" in df.columns and "net_asset" in df.columns:
        net_asset = df["net_asset"].replace(0, float("nan"))
        return df["total_mv"] / net_asset
    return pd.Series(dtype=float)


def compute_ps_ttm(df: pd.DataFrame) -> pd.Series:
    """
    市销率 TTM = 总市值 / 营业收入 TTM

    Args:
        df: 包含行情和基本面数据的 DataFrame

    Returns:
        PS TTM 因子 Series
    """
    if "ps_ttm" in df.columns:
        return df["ps_ttm"].astype(float)
    if "total_mv" in df.columns and "revenue_ttm" in df.columns:
        revenue = df["revenue_ttm"].replace(0, float("nan"))
        return df["total_mv"] / revenue
    return pd.Series(dtype=float)


def compute_fcf_yield(df: pd.DataFrame) -> pd.Series:
    """
    自由现金流收益率 = 自由现金流 / 总市值

    Args:
        df: 包含行情和基本面数据的 DataFrame

    Returns:
        FCF Yield 因子 Series
    """
    if "fcf_yield" in df.columns:
        return df["fcf_yield"].astype(float)
    if "free_cashflow" in df.columns and "total_mv" in df.columns:
        total_mv = df["total_mv"].replace(0, float("nan"))
        return df["free_cashflow"] / total_mv
    return pd.Series(dtype=float)
