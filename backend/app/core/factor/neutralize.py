"""
因子中性化

通过横截面 OLS 回归去除因子中的行业效应和市值效应，取残差作为中性化后的因子值。

方法:
    对 Z-Score 后的因子值 y，构建控制变量矩阵 X (行业虚拟变量 + 对数市值)，
    拟合 y = Xβ + ε，取残差 ε 作为中性化后的因子。

参考:
    聚宽 neutralize(): factor_neu = neutralize(factor_win, how=['jq_l1', 'market_cap'])
"""

import logging

import numpy as np
import pandas as pd
import statsmodels.api as sm

logger = logging.getLogger(__name__)


def neutralize(
    factor: pd.Series,
    industry: pd.Series | None = None,
    ln_market_cap: pd.Series | None = None,
) -> pd.Series:
    """
    横截面中性化: OLS 回归取残差。

    对单因子截面值做回归，控制行业虚拟变量和/或对数市值，
    返回残差作为中性化后的因子值。

    Args:
        factor: Z-Score 后的因子值 (index=ts_code, dtype=float)
        industry: 行业分类 Series (index=ts_code, dtype=str)
            来自 stock_info.industry，假设为申万一级行业。
            为 None 时跳过行业中性化。
        ln_market_cap: 对数市值 Series (index=ts_code, dtype=float)
            来自 ln_market_cap 因子 (log(market_cap))。
            为 None 时跳过市值中性化。

    Returns:
        中性化后的因子残差 Series, index 与 factor 相同。
        若无控制变量可用则原样返回 factor。
    """
    controls: list[pd.DataFrame] = []

    # 行业虚拟变量
    if industry is not None:
        ind = industry.reindex(factor.index)
        valid_mask = ind.notna()
        if valid_mask.sum() > 0:
            dummies = pd.get_dummies(
                ind.fillna("__unknown__"),
                prefix="ind",
                drop_first=True,
                dtype=float,
            )
            controls.append(dummies)

    # 对数市值
    if ln_market_cap is not None:
        mc = ln_market_cap.reindex(factor.index)
        if mc.notna().sum() > 0:
            controls.append(mc.fillna(mc.median()).to_frame("ln_mktcap"))

    if not controls:
        logger.debug("neutralize: no control variables available, returning factor as-is")
        return factor

    # 对齐 index，仅保留 factor 和 controls 都有值的股票
    X = pd.concat(controls, axis=1).reindex(factor.index)
    valid = factor.notna() & X.notna().all(axis=1)
    n_valid = valid.sum()

    if n_valid < 10:
        logger.warning(f"neutralize: only {n_valid} valid observations, skipping neutralization")
        return factor

    y_valid = factor[valid].values
    X_valid = X[valid].values

    # OLS 回归: y = Xβ + ε
    X_with_const = sm.add_constant(X_valid)
    try:
        model = sm.OLS(y_valid, X_with_const).fit()
        residuals = model.resid
    except Exception as e:
        logger.warning(f"neutralize: OLS fit failed ({e}), returning factor as-is")
        return factor

    # 将残差写回原 index，无效位置填 NaN
    result = pd.Series(np.nan, index=factor.index, name=factor.name)
    result[valid] = residuals

    # 残差再标准化 (保证均值 0 方差 1，与 z_score 输出一致)
    r_mean, r_std = result.mean(), result.std()
    if r_std > 0 and not pd.isna(r_std):
        result = (result - r_mean) / r_std

    logger.debug(f"neutralize: {n_valid} stocks, R²={model.rsquared:.4f}, controls={X.shape[1]} dims")
    return result
