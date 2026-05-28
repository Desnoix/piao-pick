"""
规模因子

- Ln_Market_Cap: 对数流通市值

可从 stock_info / kline 合并数据计算 (若有 market_cap / circ_mv 列),
否则返回空 Series。
"""

import numpy as np
import pandas as pd


def compute_ln_market_cap(df: pd.DataFrame) -> pd.Series:
    """
    对数流通市值 = log(流通市值)

    优先使用 market_cap, 其次 circ_mv (流通市值), 最后 total_mv (总市值)。
    将 0 值替换为 NaN 后取对数。

    Args:
        df: 包含市值数据的 DataFrame

    Returns:
        对数市值因子 Series
    """
    for col in ("market_cap", "circ_mv", "total_mv"):
        if col in df.columns and df[col].notna().any():
            return np.log(df[col].replace(0, np.nan))
    return pd.Series(dtype=float)
