"""
ICIR 动态赋权验证测试

验证项:
1. 等权分配 (equal) 正确性
2. 固定权重 (fixed) + 截断归一化
3. ICIR 赋权基本逻辑 (ICIR > 0 vs ICIR < 0)
4. 全负 ICIR 自动降级 (fallback to equal)
5. 截断再归一化收敛性 (_cap_and_renormalize)
6. 滚动 ICIR 计算 (rolling_icir)
7. ICIR 赋权综合得分计算 (icir_weighted_composite)
8. 固定权重 vs ICIR 动态权重对比 (rank correlation)
"""

import sys

sys.path.insert(0, ".")

import logging

logging.basicConfig(level=logging.INFO)

import numpy as np
import pandas as pd

from app.core.backtest.ic_analysis import rolling_icir
from app.core.factor.base import FactorPipeline
from app.core.factor.dynamic_weight import (
    _cap_and_renormalize,
    compute_dynamic_weights,
)


def test_equal_weights():
    """TEST 1: 等权分配"""
    print("=" * 60)
    print("TEST 1: 等权分配")
    print("=" * 60)

    factor_ids = ["pe_ttm", "roa", "mom_20d"]
    w = compute_dynamic_weights(
        factor_ids=factor_ids,
        icir_snapshot=None,
        fallback_weights={},
        method="equal",
    )

    expected = {fid: 1.0 / 3 for fid in factor_ids}
    for fid in factor_ids:
        assert abs(w[fid] - expected[fid]) < 1e-10, f"{fid}: {w[fid]} != {expected[fid]}"

    total = sum(w.values())
    assert abs(total - 1.0) < 1e-10, f"Sum should be 1.0, got {total}"
    print(f"  OK  equal weights: {w}")
    return True


def test_fixed_weights_with_cap():
    """TEST 2: 固定权重 + 截断"""
    print("\n" + "=" * 60)
    print("TEST 2: 固定权重 + 截断")
    print("=" * 60)

    factor_ids = ["a", "b", "c", "d"]
    fallback = {"a": 0.50, "b": 0.30, "c": 0.15, "d": 0.05}

    w = compute_dynamic_weights(
        factor_ids=factor_ids,
        icir_snapshot=None,
        fallback_weights=fallback,
        method="fixed",
        max_single_weight=0.40,
    )

    # a 原始 0.50 应被截断到 <= 0.40
    assert w["a"] <= 0.40 + 1e-10, f"'a' should be capped: {w['a']}"
    total = sum(w.values())
    assert abs(total - 1.0) < 1e-10, f"Sum should be 1.0, got {total}"
    print(f"  OK  fixed weights (capped): {w}")
    return True


def test_icir_weights_basic():
    """TEST 3: ICIR 赋权基本逻辑"""
    print("\n" + "=" * 60)
    print("TEST 3: ICIR 赋权基本逻辑")
    print("=" * 60)

    factor_ids = ["pe_ttm", "roa", "mom_20d", "size", "vol_60d"]
    icir_snap = {
        "pe_ttm": 2.0,  # 高 ICIR, 应得最高权重 (被 cap 到 0.40)
        "roa": 0.5,  # 中等
        "mom_20d": 0.3,  # 低
        "size": 0.2,  # 低
        "vol_60d": -0.2,  # 负 ICIR, 权重应为 0
    }
    fallback = {fid: 0.20 for fid in factor_ids}

    w = compute_dynamic_weights(
        factor_ids=factor_ids,
        icir_snapshot=icir_snap,
        fallback_weights=fallback,
        method="icir",
        max_single_weight=0.40,
    )

    # vol_60d ICIR < 0, 权重应为 0
    assert w["vol_60d"] == 0.0, f"Negative ICIR should get 0 weight: {w['vol_60d']}"

    # pe_ttm 应 >= 其他正向因子 (可能被 cap)
    assert w["pe_ttm"] >= w["roa"], f"pe_ttm ({w['pe_ttm']}) should >= roa ({w['roa']})"
    assert w["pe_ttm"] >= w["mom_20d"], f"pe_ttm ({w['pe_ttm']}) should >= mom_20d ({w['mom_20d']})"

    # roa 应高于 mom_20d (ICIR 0.5 > 0.3, 且都未被 cap)
    assert w["roa"] > w["mom_20d"], f"roa ({w['roa']}) should > mom_20d ({w['mom_20d']})"

    total = sum(w.values())
    assert abs(total - 1.0) < 1e-10, f"Sum should be 1.0, got {total}"
    print(f"  OK  ICIR weights: {w}")
    return True


def test_icir_all_negative_fallback():
    """TEST 4: 全负 ICIR 自动降级到等权"""
    print("\n" + "=" * 60)
    print("TEST 4: 全负 ICIR 自动降级")
    print("=" * 60)

    factor_ids = ["pe_ttm", "roa"]
    icir_snap = {"pe_ttm": -0.5, "roa": -0.3}
    fallback = {"pe_ttm": 0.6, "roa": 0.4}

    w = compute_dynamic_weights(
        factor_ids=factor_ids,
        icir_snapshot=icir_snap,
        fallback_weights=fallback,
        method="icir",
        max_single_weight=0.40,
    )

    # 全负 ICIR 应降级到 equal, 即各 0.5
    assert abs(w["pe_ttm"] - 0.5) < 1e-10, f"Should fallback to equal: {w['pe_ttm']}"
    assert abs(w["roa"] - 0.5) < 1e-10, f"Should fallback to equal: {w['roa']}"
    total = sum(w.values())
    assert abs(total - 1.0) < 1e-10, f"Sum should be 1.0, got {total}"
    print(f"  OK  all-negative ICIR fallback: {w}")
    return True


def test_cap_and_renormalize():
    """TEST 5: 截断再归一化收敛性"""
    print("\n" + "=" * 60)
    print("TEST 5: 截断再归一化收敛性")
    print("=" * 60)

    weights = {"a": 0.50, "b": 0.30, "c": 0.20}
    capped = _cap_and_renormalize(weights, 0.35)

    assert capped["a"] <= 0.35 + 1e-10, f"'a' should be capped: {capped['a']}"
    total = sum(capped.values())
    assert abs(total - 1.0) < 1e-10, f"Sum should be 1.0, got {total}"

    # 测试极端情况: 所有因子都超限, 应收敛到等权
    extreme = {"x": 0.90, "y": 0.05, "z": 0.05}
    capped_extreme = _cap_and_renormalize(extreme, 0.35)
    total_extreme = sum(capped_extreme.values())
    assert abs(total_extreme - 1.0) < 1e-10, f"Extreme case sum should be 1.0, got {total_extreme}"
    assert capped_extreme["x"] <= 0.35 + 1e-10, f"'x' should be capped: {capped_extreme['x']}"

    print(f"  OK  cap result: {capped}")
    print(f"  OK  extreme case: {capped_extreme}")
    return True


def test_rolling_icir_computation():
    """TEST 6: 滚动 ICIR 计算"""
    print("\n" + "=" * 60)
    print("TEST 6: 滚动 ICIR 计算")
    print("=" * 60)

    # 模拟 18 个月的 IC 数据
    np.random.seed(42)
    ic_series = {
        "factor_a": [(f"2024-{m:02d}-28", 0.05 + np.random.normal(0, 0.02)) for m in range(1, 19)],
        "factor_b": [(f"2024-{m:02d}-28", 0.02 + np.random.normal(0, 0.03)) for m in range(1, 19)],
    }

    result = rolling_icir(ic_series, lookback=6, min_periods=4)

    assert isinstance(result, dict), "Result should be a dict"
    assert len(result) > 0, "Result should not be empty"

    # 最后一个月应有有效 ICIR
    last_date = sorted(result.keys())[-1]
    last_icir = result[last_date]
    assert "factor_a" in last_icir, "factor_a missing from last ICIR"
    assert "factor_b" in last_icir, "factor_b missing from last ICIR"

    # 早期日期 (< min_periods) 应为 0
    early_dates = sorted(result.keys())[:3]
    for ed in early_dates:
        for fid in last_icir:
            assert result[ed][fid] == 0.0, f"Early date {ed} should have ICIR=0 for {fid}"

    print(f"  OK  rolling ICIR computed for {len(result)} dates")
    print(f"  OK  last_date={last_date}, icir={last_icir}")
    return True


def test_icir_weighted_composite():
    """TEST 7: ICIR 赋权的综合得分计算"""
    print("\n" + "=" * 60)
    print("TEST 7: ICIR 赋权综合得分")
    print("=" * 60)

    pipeline = FactorPipeline()

    # 模拟 100 只股票, 4 个因子的 processed 数据
    np.random.seed(123)
    processed = pd.DataFrame(
        np.random.randn(100, 4),
        index=[f"00000{i:02d}" for i in range(100)],
        columns=["pe_ttm", "roa", "mom_20d", "vol_60d"],
    )

    weights = {"pe_ttm": 0.35, "roa": 0.30, "mom_20d": 0.25, "vol_60d": 0.10}

    scores = pipeline.icir_weighted_composite(processed, weights)

    assert len(scores) == 100, f"Should have 100 scores, got {len(scores)}"
    assert scores.min() >= 0.0 - 1e-10, f"Min should be >= 0, got {scores.min()}"
    assert scores.max() <= 100.0 + 1e-10, f"Max should be <= 100, got {scores.max()}"

    # 至少一端应精确等于 0 或 100 (因为做了 MinMax 归一化)
    assert abs(scores.max() - 100.0) < 1e-10 or abs(scores.min() - 0.0) < 1e-10, (
        f"MinMax normalization failed: min={scores.min()}, max={scores.max()}"
    )
    print(f"  OK  scores: min={scores.min():.2f}, max={scores.max():.2f}, mean={scores.mean():.2f}")
    return True


def test_fixed_vs_icir_comparison():
    """TEST 8: 固定权重 vs ICIR 动态权重对比"""
    print("\n" + "=" * 60)
    print("TEST 8: 固定权重 vs ICIR 动态权重")
    print("=" * 60)

    pipeline = FactorPipeline()

    np.random.seed(456)
    processed = pd.DataFrame(
        np.random.randn(200, 3),
        index=[f"00000{i:03d}" for i in range(200)],
        columns=["value", "momentum", "quality"],
    )

    # 固定权重 (composite_score 返回加权 Z-Score)
    fixed_config = [
        {"id": "value", "weight": 0.33, "direction": "positive"},
        {"id": "momentum", "weight": 0.34, "direction": "positive"},
        {"id": "quality", "weight": 0.33, "direction": "positive"},
    ]
    fixed_scores = pipeline.composite_score(processed, fixed_config)

    # ICIR 动态权重 (icir_weighted_composite 返回 [0,100])
    icir_weights = {"value": 0.50, "momentum": 0.30, "quality": 0.20}
    icir_scores = pipeline.icir_weighted_composite(processed, icir_weights)

    # 计算排名相关性 (Spearman)
    from scipy.stats import spearmanr

    corr, pval = spearmanr(fixed_scores.values, icir_scores.values)
    print(f"  Spearman correlation (fixed vs icir): {corr:.4f} (p={pval:.4e})")

    # 两种方法的排名应有正相关性但非完全一致 (因为权重不同)
    assert corr > 0.5, f"Correlation too low: {corr}"
    assert corr < 1.0, "Correlation should < 1.0 (different weighting)"
    print("  OK  correlation in expected range (0.5, 1.0)")
    return True


if __name__ == "__main__":
    tests = [
        test_equal_weights,
        test_fixed_weights_with_cap,
        test_icir_weights_basic,
        test_icir_all_negative_fallback,
        test_cap_and_renormalize,
        test_rolling_icir_computation,
        test_icir_weighted_composite,
        test_fixed_vs_icir_comparison,
    ]

    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            result = test_fn()
            if result:
                passed += 1
            else:
                failed += 1
                print(f"  FAIL  {test_fn.__name__} returned falsy")
        except Exception as e:
            failed += 1
            print(f"  FAIL  {test_fn.__name__}: {e}")
            import traceback

            traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed, {len(tests)} total")
    print("=" * 60)

    if failed == 0:
        print("\n=== ALL TESTS PASSED ===")
    else:
        print(f"\n=== {failed} TEST(S) FAILED ===")
        sys.exit(1)
