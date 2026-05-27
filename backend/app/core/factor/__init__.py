# -*- coding: utf-8 -*-
"""
因子模块

导出所有因子计算函数及 FactorPipeline。
ALL_FACTORS 字典将因子名称映射到对应的计算函数。
"""

from typing import Any, Callable

from .base import FactorPipeline
from .value import compute_pe_ttm, compute_pb, compute_ps_ttm, compute_fcf_yield
from .momentum import compute_ret_20d, compute_ret_60d_vol, compute_turnover_20d
from .quality import compute_roe_ttm, compute_gross_margin
from .growth import compute_rev_growth_yoy, compute_ear_growth_yoy
from .size import compute_ln_market_cap

ALL_FACTORS: dict[str, Callable[..., Any]] = {
    # 估值因子
    "pe_ttm": compute_pe_ttm,
    "pb": compute_pb,
    "ps_ttm": compute_ps_ttm,
    "fcf_yield": compute_fcf_yield,
    # 动量因子
    "ret_20d": compute_ret_20d,
    "ret_60d_vol": compute_ret_60d_vol,
    "turnover_20d": compute_turnover_20d,
    # 质量因子
    "roe_ttm": compute_roe_ttm,
    "gross_margin": compute_gross_margin,
    # 成长因子
    "rev_growth_yoy": compute_rev_growth_yoy,
    "ear_growth_yoy": compute_ear_growth_yoy,
    # 规模因子
    "ln_market_cap": compute_ln_market_cap,
}

__all__ = [
    "FactorPipeline",
    "ALL_FACTORS",
    "compute_pe_ttm",
    "compute_pb",
    "compute_ps_ttm",
    "compute_fcf_yield",
    "compute_ret_20d",
    "compute_ret_60d_vol",
    "compute_turnover_20d",
    "compute_roe_ttm",
    "compute_gross_margin",
    "compute_rev_growth_yoy",
    "compute_ear_growth_yoy",
    "compute_ln_market_cap",
]
