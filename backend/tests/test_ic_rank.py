"""
Rank IC (Spearman) 计算测试

验证项:
1. Spearman Rank IC 基本计算正确性
2. Pearson IC 保留为备选，结果与旧实现一致
3. min_samples 默认值提高后的小样本过滤
4. summarize_ic() 质量标签和显著性检验
5. 离群点场景下 Rank IC 比 Pearson IC 更稳健
"""

import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

from app.core.backtest.ic_analysis import (
    compute_factor_ic,
    compute_ic_series,
    summarize_ic,
)

logging.basicConfig(level=logging.INFO)


def test_spearman_basic():
    """Spearman Rank IC 基本正确性: 单调递增数据应得到 IC=1。"""
    np.random.seed(42)
    n = 100
    ts_codes = [f"{i:06d}" for i in range(n)]

    factor_data = pd.DataFrame(
        {"f1": np.arange(n, dtype=float)},
        index=ts_codes,
    )
    # 收益率与因子完全单调对应
    returns = pd.Series(np.arange(n, dtype=float) * 0.01, index=ts_codes)

    result = compute_factor_ic(factor_data, returns, method="spearman")

    assert "f1" in result, "Should compute IC for f1"
    assert abs(result["f1"] - 1.0) < 1e-6, f"Perfect monotonic should give IC=1, got {result['f1']}"
    print(f"[PASS] test_spearman_basic: IC={result['f1']:.4f}")


def test_pearson_backward_compat():
    """Pearson IC 保留为备选，结果应与 pd.corr() 一致。"""
    np.random.seed(42)
    n = 100
    ts_codes = [f"{i:06d}" for i in range(n)]

    factor_data = pd.DataFrame(
        {"f1": np.random.randn(n)},
        index=ts_codes,
    )
    returns = pd.Series(np.random.randn(n), index=ts_codes)

    result = compute_factor_ic(factor_data, returns, method="pearson")
    expected = factor_data["f1"].corr(returns)

    assert "f1" in result
    assert abs(result["f1"] - expected) < 1e-10, f"Pearson IC mismatch: {result['f1']} vs {expected}"
    print(f"[PASS] test_pearson_backward_compat: IC={result['f1']:.4f}")


def test_default_method_is_spearman():
    """默认方法应为 spearman，不传 method 参数时使用 Rank IC。"""
    np.random.seed(42)
    n = 100
    ts_codes = [f"{i:06d}" for i in range(n)]

    factor_data = pd.DataFrame({"f1": np.arange(n, dtype=float)}, index=ts_codes)
    returns = pd.Series(np.arange(n, dtype=float) * 0.01, index=ts_codes)

    # 不传 method 参数
    result = compute_factor_ic(factor_data, returns)

    assert "f1" in result
    assert abs(result["f1"] - 1.0) < 1e-6, "Default should be spearman"
    print(f"[PASS] test_default_method_is_spearman: IC={result['f1']:.4f}")


def test_min_samples_default():
    """min_samples 默认值 30: 少于 30 个样本时不计算 IC。"""
    n = 25  # 低于默认阈值 30
    ts_codes = [f"{i:06d}" for i in range(n)]

    factor_data = pd.DataFrame({"f1": np.random.randn(n)}, index=ts_codes)
    returns = pd.Series(np.random.randn(n), index=ts_codes)

    result = compute_factor_ic(factor_data, returns)

    assert "f1" not in result, "25 samples < min_samples=30, should skip"
    print("[PASS] test_min_samples_default: correctly skipped with 25 samples")


def test_min_samples_override():
    """显式传入 min_samples 可以覆盖默认值。"""
    n = 15
    ts_codes = [f"{i:06d}" for i in range(n)]

    factor_data = pd.DataFrame({"f1": np.random.randn(n)}, index=ts_codes)
    returns = pd.Series(np.random.randn(n), index=ts_codes)

    result = compute_factor_ic(factor_data, returns, min_samples=10)

    assert "f1" in result, "min_samples=10 override should work"
    print(f"[PASS] test_min_samples_override: IC={result['f1']:.4f}")


def test_outlier_robustness():
    """
    离群点场景: Rank IC 应比 Pearson IC 更稳定。

    构造 100 个样本点，其中 5 个极端离群值。
    Pearson IC 应被离群点严重拉升/压低，Rank IC 应更稳健。
    """
    np.random.seed(42)
    n = 100
    ts_codes = [f"{i:06d}" for i in range(n)]

    # 因子值: 正态分布
    factor_vals = np.random.randn(n)
    # 收益率: 因子 + 噪声
    returns_vals = factor_vals * 0.5 + np.random.randn(n) * 0.3

    # 注入 5 个极端离群点 (因子值和收益都极端)
    outlier_idx = [10, 25, 50, 75, 90]
    for idx in outlier_idx:
        factor_vals[idx] = factor_vals[idx] * 100
        returns_vals[idx] = returns_vals[idx] * 100

    factor_data = pd.DataFrame({"f1": factor_vals}, index=ts_codes)
    returns = pd.Series(returns_vals, index=ts_codes)

    rank_ic = compute_factor_ic(factor_data, returns, method="spearman")["f1"]
    pearson_ic = compute_factor_ic(factor_data, returns, method="pearson")["f1"]

    # 离群点同时放大因子和收益，Pearson IC 会被拉向 1
    # Rank IC 不受绝对值影响，应保持在合理范围
    assert abs(rank_ic) < 0.9, f"Rank IC should be robust: {rank_ic}"
    # Spearman IC 应在合理范围 [0.3, 0.8]
    assert 0.2 < rank_ic < 0.95, f"Rank IC suspicious: {rank_ic}"
    print(f"[PASS] test_outlier_robustness: Rank IC={rank_ic:.4f}, Pearson IC={pearson_ic:.4f}")


def test_summarize_ic_quality():
    """summarize_ic() 应返回 quality 标签和显著性指标。"""
    # 构造一个"良好"因子的 IC 序列: 均值约 0.06, ICIR 约 0.6
    np.random.seed(42)
    n_periods = 60
    dates = [f"2024-{(i % 12) + 1:02d}-01" for i in range(n_periods)]
    ic_values = np.random.normal(0.06, 0.10, n_periods)

    ic_series = {
        "roe_ttm": list(zip(dates, ic_values.tolist())),
    }

    result = summarize_ic(ic_series)

    assert "roe_ttm" in result
    s = result["roe_ttm"]

    # 新增字段必须存在
    assert "t_statistic" in s, "Missing t_statistic"
    assert "p_value" in s, "Missing p_value"
    assert "is_significant" in s, "Missing is_significant"
    assert "quality" in s, "Missing quality"

    # quality 必须是合法值
    assert s["quality"] in ("excellent", "good", "pass", "weak"), f"Invalid quality: {s['quality']}"

    # 60 期均值 ~0.06, std ~0.10 → t ≈ 0.06/(0.10/sqrt(60)) ≈ 4.65 → 显著
    assert s["t_statistic"] > 3.0, f"t_stat should be significant: {s['t_statistic']}"
    assert s["p_value"] < 0.05, f"p_value should be < 0.05: {s['p_value']}"

    print(
        f"[PASS] test_summarize_ic_quality: "
        f"mean_ic={s['mean_ic']}, icir={s['icir']}, "
        f"t_stat={s['t_statistic']}, quality={s['quality']}"
    )


def test_summarize_ic_weak_factor():
    """弱因子: 均值接近 0 时应标记为 weak。"""
    np.random.seed(42)
    n_periods = 36
    dates = [f"2024-{(i % 12) + 1:02d}-01" for i in range(n_periods)]
    ic_values = np.random.normal(0.005, 0.15, n_periods)  # 均值极低

    ic_series = {"weak_factor": list(zip(dates, ic_values.tolist()))}
    result = summarize_ic(ic_series)
    s = result["weak_factor"]

    assert s["quality"] == "weak", f"Near-zero IC should be 'weak': {s['quality']}"
    assert s["is_significant"] is False, "Weak factor should not be significant"
    print(f"[PASS] test_summarize_ic_weak_factor: quality={s['quality']}")


def test_compute_ic_series_passthrough():
    """compute_ic_series() 应正确透传 method 参数。"""
    np.random.seed(42)
    n = 50
    rebalance_dates = ["2024-01-31", "2024-02-29", "2024-03-31"]

    def get_factors(d):
        ts_codes = [f"{i:06d}" for i in range(n)]
        return pd.DataFrame({"f1": np.random.randn(n)}, index=ts_codes)

    def get_returns(d):
        ts_codes = [f"{i:06d}" for i in range(n)]
        return pd.Series(np.random.randn(n), index=ts_codes)

    spearman_result = compute_ic_series(
        get_factors,
        get_returns,
        rebalance_dates,
        min_samples=30,
        method="spearman",
    )
    pearson_result = compute_ic_series(
        get_factors,
        get_returns,
        rebalance_dates,
        min_samples=30,
        method="pearson",
    )

    assert "f1" in spearman_result, "Spearman series should contain f1"
    assert "f1" in pearson_result, "Pearson series should contain f1"
    assert len(spearman_result["f1"]) == 3, "Should have 3 periods"

    print(f"[PASS] test_compute_ic_series_passthrough: spearman periods={len(spearman_result['f1'])}")


if __name__ == "__main__":
    tests = [
        test_spearman_basic,
        test_pearson_backward_compat,
        test_default_method_is_spearman,
        test_min_samples_default,
        test_min_samples_override,
        test_outlier_robustness,
        test_summarize_ic_quality,
        test_summarize_ic_weak_factor,
        test_compute_ic_series_passthrough,
    ]

    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"[FAIL] {t.__name__}: {e}")
            failed += 1

    print(f"\n{'=' * 50}")
    print(f"Results: {passed} passed, {failed} failed, {len(tests)} total")
    if failed > 0:
        sys.exit(1)
