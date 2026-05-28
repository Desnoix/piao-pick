"""
因子覆盖率服务 — 计算策略中因子的实际可用比例。
Factor coverage service: compute actual availability ratio of strategy factors.

硬编码 stub 因子清单与 factor/*.py 中返回空 Series 的函数同步。
阶段 B 激活因子后，从此清单移除对应名称即可。
"""

from __future__ import annotations

import logging
from typing import Any

import yaml

from app.database import get_db
from app.repositories import StrategyRepository

logger = logging.getLogger(__name__)

# 硬编码 stub 因子清单 — 与 factor/*.py 中返回空 Series 的函数同步
# Hardcoded stub factor list — synced with factor/*.py functions returning empty Series
#
# 阶段 B 已激活 (removed from this set):
# - roe_ttm, rev_growth_yoy, ear_growth_yoy — via stock_yjbb_em batch API
#
# 仍未激活 (需要单股接口或数据不全):
STUB_FACTORS: set[str] = {
    "fcf_yield",  # value.py  单股现金流量表接口，限流风险
    "ps_ttm",  # value.py  需要营收数据，尚无批量接口
    "gross_margin",  # quality.py 单股 financial_analysis_indicator，慢
    "inst_holding_chg",  # size.py 单股接口，覆盖率低
}


class FactorCoverageService:
    """
    计算指定策略的因子覆盖率。
    Computes factor coverage for a given strategy.
    """

    _cache: dict[str, dict[str, Any]] = {}

    def get_coverage(self, strategy_name: str) -> dict[str, Any]:
        """
        获取策略因子覆盖率。
        Get factor coverage for a strategy.

        Returns:
            dict with keys:
                strategy_name, total_factors, available_factors, stub_factors,
                coverage_rate, configured_weights, effective_weights, weight_drift
        """
        cache_key = f"factor_coverage:{strategy_name}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        # 1. 从数据库加载策略
        db = get_db()
        repo = StrategyRepository(db)
        strategy = repo.get_by_name(strategy_name)

        if strategy is None:
            return {
                "strategy_name": strategy_name,
                "error": f"Strategy '{strategy_name}' not found",
            }

        # 2. 解析 YAML 配置，提取因子权重
        try:
            config = yaml.safe_load(strategy.config or "")
        except yaml.YAMLError:
            config = {}

        factor_list = config.get("factors", []) if isinstance(config, dict) else []
        if not isinstance(factor_list, list):
            factor_list = []

        # 收集所有配置的因子名及其权重
        configured_weights: dict[str, float] = {}
        for factor_conf in factor_list:
            if not isinstance(factor_conf, dict):
                continue
            fid = factor_conf.get("id")
            if fid:
                configured_weights[str(fid)] = float(factor_conf.get("weight", 0))

        # 3. 区分可用因子与 stub 因子
        available_factors: list[str] = []
        stub_factors: list[str] = []

        for factor_name in configured_weights:
            if factor_name in STUB_FACTORS:
                stub_factors.append(factor_name)
            else:
                available_factors.append(factor_name)

        total = len(configured_weights)
        coverage_rate = len(available_factors) / total if total > 0 else 0.0

        # 4. 计算实际生效权重 (与 factor/base.py composite_score 逻辑一致)
        effective_weights: dict[str, float] = {}
        weight_drift: dict[str, float] = {}

        available_weight_sum = sum(configured_weights[f] for f in available_factors)

        if available_weight_sum > 0:
            for factor_name, conf_weight in configured_weights.items():
                if factor_name in available_factors:
                    eff = conf_weight / available_weight_sum
                    effective_weights[factor_name] = round(eff, 4)
                    weight_drift[factor_name] = round(eff - conf_weight, 4)
                else:
                    effective_weights[factor_name] = 0.0
                    weight_drift[factor_name] = round(-conf_weight, 4)

        result: dict[str, Any] = {
            "strategy_name": strategy_name,
            "total_factors": total,
            "available_factors": sorted(available_factors),
            "stub_factors": sorted(stub_factors),
            "coverage_rate": round(coverage_rate, 4),
            "configured_weights": configured_weights,
            "effective_weights": effective_weights,
            "weight_drift": weight_drift,
        }

        self._cache[cache_key] = result
        return result

    @classmethod
    def clear_cache(cls) -> None:
        """清除内存缓存。"""
        cls._cache.clear()
