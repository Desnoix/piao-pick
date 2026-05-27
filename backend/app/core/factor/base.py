# -*- coding: utf-8 -*-
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
    def winsorize(series: pd.Series, limits: tuple[float, float] = (-3.0, 3.0)) -> pd.Series:
        """
        极值处理: 将超出 ±Nσ 的值截断到边界。

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

    def process(self, raw_factors: pd.DataFrame, factor_config: list[dict[str, Any]]) -> pd.DataFrame:
        """
        完整因子处理流程:
        1. 极值处理 (Winsorize ±3σ)
        2. 缺失值填充 (全市场均值)
        3. Z-Score 标准化
        4. 方向对齐

        Args:
            raw_factors: 原始因子 DataFrame, index 为股票, columns 为因子名
            factor_config: 因子配置列表, 每项为 dict:
                - id: 因子名称 (对应 raw_factors 的列名)
                - direction: 'positive' | 'negative', 默认 'positive'
                - weight: 权重 (用于 composite_score)

        Returns:
            处理后的 DataFrame, 与 raw_factors 同 index
        """
        processed = pd.DataFrame(index=raw_factors.index)
        for cfg in factor_config:
            fid = cfg["id"]
            direction = cfg.get("direction", "positive")
            if fid not in raw_factors.columns:
                logger.warning(f"Factor '{fid}' not found in raw_factors, skipping")
                continue
            col = raw_factors[fid].copy()
            # Step 1: 极值处理
            col = self.winsorize(col)
            # Step 2: 缺失值填充 (全市场均值)
            col = col.fillna(col.mean())
            # Step 3: Z-Score 标准化
            col = self.z_score(col)
            # Step 4: 方向对齐
            col = self.align_direction(col, direction)
            processed[fid] = col
        return processed

    @staticmethod
    def composite_score(processed: pd.DataFrame, factor_config: list[dict[str, Any]]) -> pd.Series:
        """
        加权综合得分: 按配置权重加权求和, 归一化到 0-100。

        Args:
            processed: 处理后的因子 DataFrame (process 的输出)
            factor_config: 因子配置列表 (同 process)

        Returns:
            综合得分 Series, 范围 [0, 100]
        """
        total_weight = sum(
            cfg.get("weight", 0) for cfg in factor_config if cfg["id"] in processed.columns
        )
        if total_weight == 0:
            return pd.Series(0.0, index=processed.index)
        score = pd.Series(0.0, index=processed.index)
        for cfg in factor_config:
            fid = cfg["id"]
            weight = cfg.get("weight", 1.0)
            if fid in processed.columns:
                score += processed[fid] * (weight / total_weight)
        # Normalize to 0-100
        score_min, score_max = score.min(), score.max()
        if score_max - score_min > 0:
            score = (score - score_min) / (score_max - score_min) * 100
        else:
            score = pd.Series(50.0, index=processed.index)
        return score
