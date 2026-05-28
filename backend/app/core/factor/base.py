"""
因子计算与标准化管道

提供 FactorPipeline 类，包含:
- winsorize: 极值处理 (MAD / ±Nσ)
- z_score: Z-Score 标准化
- align_direction: 方向对齐 (正向/反向)
- process: 完整因子处理流程
- composite_score: 加权综合得分
"""

import logging
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


class FactorPipeline:
    """因子计算与标准化管道"""

    @staticmethod
    def winsorize_sigma(series: pd.Series, limits: tuple[float, float] = (-3.0, 3.0)) -> pd.Series:
        """
        基于均值标准差的极值处理 (旧方法, 保留兼容)。

        mean/std 对极端值敏感, 重尾分布下推荐 winsorize_mad()。

        Args:
            series: 原始因子序列
            limits: (下界倍数, 上界倍数), 默认 (-3, 3) 即 ±3σ

        Returns:
            截断后的 Series
        """
        mean, std = series.mean(), series.std()
        if std == 0 or pd.isna(std):
            return series
        lower = mean + limits[0] * std
        upper = mean + limits[1] * std
        return series.clip(lower=lower, upper=upper)

    # 兼容别名: 旧调用 self.winsorize() 不受影响
    winsorize = winsorize_sigma

    @staticmethod
    def winsorize_mad(series: pd.Series, n: float = 5.0) -> pd.Series:
        """
        基于 MAD 的鲁棒极值处理。

        MAD = median(|X - median(X)|)
        边界 = median ± n × 1.4826 × MAD
        n=5 等效 ±3.37σ, n=3 等效 ±2.02σ。

        Args:
            series: 原始因子序列
            n: 边界倍数, 默认 5.0

        Returns:
            截断后的 Series
        """
        median = series.median()
        mad = (series - median).abs().median()
        if mad == 0 or pd.isna(mad):
            return series
        adjusted_mad = 1.4826 * mad
        lower = median - n * adjusted_mad
        upper = median + n * adjusted_mad
        return series.clip(lower=lower, upper=upper)

    def winsorize_dispatch(
        self,
        series: pd.Series,
        method: str = "mad",
        n_mad: float = 5.0,
        limits_sigma: tuple[float, float] = (-3.0, 3.0),
    ) -> pd.Series:
        """
        极值处理分发器。

        Args:
            series: 原始因子序列
            method: 'mad' (默认) 或 'sigma'
            n_mad: MAD 方法的边界倍数
            limits_sigma: sigma 方法的边界倍数

        Returns:
            截断后的 Series
        """
        if method == "sigma":
            return self.winsorize_sigma(series, limits=limits_sigma)
        return self.winsorize_mad(series, n=n_mad)

    @staticmethod
    def z_score(series: pd.Series) -> pd.Series:
        """
        Z-Score 标准化: (x - mean) / std

        Args:
            series: 原始因子序列

        Returns:
            标准化后的 Series, 若 std 为 0 则返回全 0
        """
        mean, std = series.mean(), series.std()
        if std == 0 or pd.isna(std):
            return pd.Series(0.0, index=series.index)
        return (series - mean) / std

    @staticmethod
    def align_direction(series: pd.Series, direction: str) -> pd.Series:
        """
        方向对齐: 将反向因子取负, 使得所有因子都是越大越好。

        Args:
            series: 标准化后的因子序列
            direction: 'positive' (越大越好) 或 'negative' (越小越好)

        Returns:
            方向对齐后的 Series
        """
        if direction == "negative":
            return -series
        return series

    def process(
        self,
        raw_factors: pd.DataFrame,
        factor_config: list[dict[str, Any]],
        stock_info_df: pd.DataFrame | None = None,
        neutralization_config: dict[str, Any] | None = None,
        winsorize_method: str = "mad",
        winsorize_n_mad: float = 5.0,
        winsorize_limits_sigma: tuple[float, float] = (-3.0, 3.0),
    ) -> pd.DataFrame:
        """
        完整因子处理流程:
        1. 极值处理 (Winsorize, 默认 MAD)
        2. 缺失值填充 (全市场均值)
        3. Z-Score 标准化
        4. 中性化 (行业/市值, 可选)
        5. 方向对齐

        Args:
            raw_factors: 原始因子 DataFrame, index 为股票, columns 为因子名
            factor_config: 因子配置列表, 每项为 dict:
                - id: 因子名称 (对应 raw_factors 的列名)
                - direction: 'positive' | 'negative', 默认 'positive'
                - weight: 权重 (用于 composite_score)
            stock_info_df: 股票基本信息 DataFrame (含 industry 列)
            neutralization_config: 中性化配置 dict:
                - enabled: bool
                - dimensions: list of 'industry' / 'market_cap'
            winsorize_method: 极值处理方法, 'mad' (默认) 或 'sigma'
            winsorize_n_mad: MAD 方法边界倍数, 默认 5.0
            winsorize_limits_sigma: sigma 方法边界倍数, 默认 (-3.0, 3.0)

        Returns:
            处理后的 DataFrame, 与 raw_factors 同 index
        """
        processed = pd.DataFrame(index=raw_factors.index)

        # 预提取中性化控制变量
        industry_series = None
        ln_mktcap_series = None
        do_neutralize = False

        if neutralization_config and neutralization_config.get("enabled", False):
            do_neutralize = True
            dims = neutralization_config.get("dimensions", [])

            if "industry" in dims and stock_info_df is not None:
                if "industry" in stock_info_df.columns:
                    industry_series = stock_info_df["industry"]

            if "market_cap" in dims:
                if "ln_market_cap" in raw_factors.columns:
                    ln_mktcap_series = raw_factors["ln_market_cap"]
                elif stock_info_df is not None and "market_cap" in stock_info_df.columns:
                    ln_mktcap_series = np.log(stock_info_df["market_cap"].replace(0, np.nan))

        for cfg in factor_config:
            fid = cfg["id"]
            direction = cfg.get("direction", "positive")
            if fid not in raw_factors.columns:
                logger.warning(f"Factor '{fid}' not found in raw_factors, skipping")
                continue
            col = raw_factors[fid].copy()
            # Step 1: 极值处理 (可配置方法)
            col = self.winsorize_dispatch(
                col,
                method=winsorize_method,
                n_mad=winsorize_n_mad,
                limits_sigma=winsorize_limits_sigma,
            )
            # Step 2: 缺失值填充 (全市场均值)
            col = col.fillna(col.mean())
            # Step 3: Z-Score 标准化
            col = self.z_score(col)
            # Step 4: 中性化 (行业/市值)
            if do_neutralize and fid != "ln_market_cap":
                from app.core.factor.neutralize import neutralize

                col = neutralize(
                    factor=col,
                    industry=industry_series,
                    ln_market_cap=ln_mktcap_series,
                )
            # Step 5: 方向对齐
            col = self.align_direction(col, direction)
            processed[fid] = col
        return processed

    @staticmethod
    def composite_score(processed: pd.DataFrame, factor_config: list[dict[str, Any]]) -> pd.Series:
        """
        加权综合得分: 按配置权重加权求和, 返回加权 Z-Score。

        不做 MinMax 归一化 — Z-Score 本身跨期可比 (均值 0, 标准差 ~1)。
        典型值域 [-3, +3]: 正数优于均值, 负数低于均值。

        Args:
            processed: 处理后的因子 DataFrame (process 的输出, 已 Z-Score 标准化)
            factor_config: 因子配置列表 (同 process)

        Returns:
            加权 Z-Score Series, 典型范围 [-3, +3], 跨期可比
        """
        total_weight = sum(cfg.get("weight", 0) for cfg in factor_config if cfg["id"] in processed.columns)
        if total_weight == 0:
            return pd.Series(0.0, index=processed.index)
        score = pd.Series(0.0, index=processed.index)
        for cfg in factor_config:
            fid = cfg["id"]
            weight = cfg.get("weight", 1.0)
            if fid in processed.columns:
                score += processed[fid] * (weight / total_weight)
        return score  # 加权 Z-Score, 不做 MinMax 归一化

    @staticmethod
    def icir_weighted_composite(
        processed: pd.DataFrame,
        weights: dict[str, float],
    ) -> pd.Series:
        """
        ICIR 动态赋权综合得分: 按给定权重加权求和, 归一化到 0-100。

        与 composite_score() 不同, 此方法的权重由外部 (dynamic_weight 模块) 计算,
        不从 factor_config 读取。

        Args:
            processed: 处理后的因子 DataFrame (process 的输出)
            weights: dict of factor_id -> weight (已归一化, 总和 = 1.0)

        Returns:
            综合得分 Series, 范围 [0, 100]
        """
        score = pd.Series(0.0, index=processed.index)
        for fid, weight in weights.items():
            if fid in processed.columns and weight > 0:
                score += processed[fid] * weight

        # 归一化到 0-100
        score_min, score_max = score.min(), score.max()
        if score_max - score_min > 0:
            score = (score - score_min) / (score_max - score_min) * 100
        else:
            score = pd.Series(50.0, index=processed.index)
        return score

    @staticmethod
    def equal_weight_composite(
        processed: pd.DataFrame,
    ) -> pd.Series:
        """
        等权综合得分: 所有因子等权加权求和, 归一化到 0-100。

        Args:
            processed: 处理后的因子 DataFrame

        Returns:
            综合得分 Series, 范围 [0, 100]
        """
        if processed.empty or processed.columns.empty:
            return pd.Series(50.0, index=processed.index)

        n = len(processed.columns)
        weight = 1.0 / n
        score = pd.Series(0.0, index=processed.index)
        for col in processed.columns:
            score += processed[col] * weight

        score_min, score_max = score.min(), score.max()
        if score_max - score_min > 0:
            score = (score - score_min) / (score_max - score_min) * 100
        else:
            score = pd.Series(50.0, index=processed.index)
        return score
