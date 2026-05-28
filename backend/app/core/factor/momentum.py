"""
动量因子 (可从 kline_daily 行情数据计算)

- Ret_20d: 20 日收益率动量
- Ret_60d_Vol: 60 日收益率波动率 (年化)
- Turnover_20d: 20 日平均换手率 / 成交量
"""

import numpy as np
import pandas as pd


def _get_close(df: pd.DataFrame) -> pd.Series:
    """优先使用复权价 close_adj, 否则使用 close"""
    if "close_adj" in df.columns and df["close_adj"].notna().any():
        return df["close_adj"]
    return df["close"]


def compute_ret_20d(df: pd.DataFrame) -> pd.Series:
    """
    20 日动量 = (close_t - close_{t-20}) / close_{t-20}

    Args:
        df: kline_daily DataFrame, 需包含 close 或 close_adj 列,
            按 trade_date 升序排列

    Returns:
        20 日收益率 Series
    """
    close = _get_close(df)
    return close.pct_change(periods=20)


def compute_ret_60d_vol(df: pd.DataFrame) -> pd.Series:
    """
    60 日波动率 = std(daily_returns, 60d) * sqrt(252)

    年化波动率, 窗口 60 日, 最少 20 日有效数据。

    Args:
        df: kline_daily DataFrame, 需包含 close 或 close_adj 列,
            按 trade_date 升序排列

    Returns:
        60 日年化波动率 Series
    """
    close = _get_close(df)
    daily_returns = close.pct_change()
    return daily_returns.rolling(window=60, min_periods=20).std() * np.sqrt(252)


def compute_turnover_20d(df: pd.DataFrame) -> pd.Series:
    """
    20 日平均换手率 / 成交量

    优先使用 turnover_rate (换手率), 否则回降至 volume (成交量)。

    Args:
        df: kline_daily DataFrame, 需包含 turnover_rate 或 volume 列,
            按 trade_date 升序排列

    Returns:
        20 日均值 Series, 若无可用列则返回空 Series
    """
    if "turnover_rate" in df.columns and df["turnover_rate"].notna().any():
        return df["turnover_rate"].rolling(window=20, min_periods=5).mean()
    if "volume" in df.columns and df["volume"].notna().any():
        return df["volume"].astype(float).rolling(window=20, min_periods=5).mean()
    return pd.Series(dtype=float)
