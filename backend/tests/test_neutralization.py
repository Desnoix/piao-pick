"""
中性化效果验证测试

验证项:
1. neutralize() 函数单元测试
2. 行业中性化后不同行业因子得分分布收敛
3. 市值中性化后因子与市值相关性降低
4. FactorPipeline.process() 向后兼容性 (不传中性化参数时行为不变)
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np
import pandas as pd

from app.core.factor.base import FactorPipeline
from app.core.factor.neutralize import neutralize


def _make_test_data(n_stocks: int = 500, seed: int = 42) -> tuple:
    """
    构造测试数据: 模拟银行/科技/消费三个行业的 PE 因子。

    Returns:
        (factor_series, industry_series, ln_mktcap_series, stock_info_df)
    """
    rng = np.random.RandomState(seed)
    industries = np.array(["银行", "科技", "消费"])
    ind_assignment = rng.choice(industries, size=n_stocks)

    # PE 值: 银行天然低, 科技天然高
    pe_base = {"银行": 6.0, "科技": 50.0, "消费": 30.0}
    pe_values = np.array([pe_base[ind] + rng.normal(0, 5) for ind in ind_assignment])

    # 对数市值: 银行大, 科技小
    ln_mc_base = {"银行": 26.0, "科技": 22.0, "消费": 24.0}
    ln_mc_values = np.array([ln_mc_base[ind] + rng.normal(0, 1) for ind in ind_assignment])

    codes = [f"{600000 + i:06d}" for i in range(n_stocks)]
    factor = pd.Series(pe_values, index=codes, name="pe_ttm")
    industry = pd.Series(ind_assignment, index=codes, name="industry")
    ln_mktcap = pd.Series(ln_mc_values, index=codes, name="ln_market_cap")

    stock_info_df = pd.DataFrame(
        {
            "industry": ind_assignment,
        },
        index=codes,
    )

    return factor, industry, ln_mktcap, stock_info_df


def test_neutralize_basic():
    """测试 1: neutralize() 基本功能"""
    factor, industry, ln_mktcap, _ = _make_test_data()

    # 原始因子: 银行 PE 远低于科技
    raw_bank_mean = factor[industry == "银行"].mean()
    raw_tech_mean = factor[industry == "科技"].mean()
    raw_diff = abs(raw_bank_mean - raw_tech_mean)
    print(f"  原始因子: 银行PE均值={raw_bank_mean:.2f}, 科技PE均值={raw_tech_mean:.2f}, 差距={raw_diff:.2f}")

    # 行业+市值中性化
    neu = neutralize(factor, industry=industry, ln_market_cap=ln_mktcap)

    # 验证: 残差均值接近 0
    assert abs(neu.mean()) < 0.01, f"残差均值应接近 0, 实际={neu.mean():.6f}"

    # 验证: 行业间差距大幅缩小
    neu_bank_mean = neu[industry == "银行"].mean()
    neu_tech_mean = neu[industry == "科技"].mean()
    neu_diff = abs(neu_bank_mean - neu_tech_mean)
    print(f"  中性化后: 银行={neu_bank_mean:.4f}, 科技={neu_tech_mean:.4f}, 差距={neu_diff:.4f}")
    print(f"  行业差距缩小: {raw_diff:.2f} -> {neu_diff:.4f} (缩小 {raw_diff / max(neu_diff, 1e-8):.1f} 倍)")

    assert neu_diff < raw_diff * 0.1, f"中性化后行业差距应缩小 90%+ 以上, 原始={raw_diff:.2f}, 中性化后={neu_diff:.4f}"
    print("  [PASS] 行业中性化效果显著\n")


def test_neutralize_industry_only():
    """测试 2: 仅行业中性化"""
    factor, industry, ln_mktcap, _ = _make_test_data()
    neu = neutralize(factor, industry=industry, ln_market_cap=None)
    assert abs(neu.mean()) < 0.01
    # 行业间均值差异应缩小
    bank_mean = neu[industry == "银行"].mean()
    tech_mean = neu[industry == "科技"].mean()
    assert abs(bank_mean - tech_mean) < 0.5, f"仅行业中性化后行业差距应 < 0.5, 实际={abs(bank_mean - tech_mean):.4f}"
    print("  [PASS] 仅行业中性化\n")


def test_neutralize_market_cap_only():
    """测试 3: 仅市值中性化"""
    factor, industry, ln_mktcap, _ = _make_test_data()
    neu = neutralize(factor, industry=None, ln_market_cap=ln_mktcap)
    assert abs(neu.mean()) < 0.01

    # 中性化后因子与市值的相关性应大幅降低
    valid = factor.notna() & ln_mktcap.notna() & neu.notna()
    corr_before = factor[valid].corr(ln_mktcap[valid])
    corr_after = neu[valid].corr(ln_mktcap[valid])
    print(f"  因子与市值相关性: {corr_before:.4f} -> {corr_after:.4f}")
    assert abs(corr_after) < abs(corr_before) * 0.3, (
        f"市值中性化后相关性应降低 70%+, 原始={corr_before:.4f}, 中性化后={corr_after:.4f}"
    )
    print("  [PASS] 仅市值中性化\n")


def test_neutralize_no_controls():
    """测试 4: 无控制变量时返回原因子"""
    factor, _, _, _ = _make_test_data()
    result = neutralize(factor, industry=None, ln_market_cap=None)
    pd.testing.assert_series_equal(result, factor)
    print("  [PASS] 无控制变量时原样返回\n")


def test_pipeline_backward_compat():
    """测试 5: FactorPipeline.process() 向后兼容性"""
    rng = np.random.RandomState(123)
    n = 100
    codes = [f"{600000 + i:06d}" for i in range(n)]
    raw = pd.DataFrame(
        {
            "pe_ttm": rng.normal(20, 10, n),
            "roe_ttm": rng.normal(15, 5, n),
        },
        index=codes,
    )

    factor_config = [
        {"id": "pe_ttm", "direction": "negative", "weight": 0.5},
        {"id": "roe_ttm", "direction": "positive", "weight": 0.5},
    ]

    pipeline = FactorPipeline()

    # 不传中性化参数, 行为与修改前完全一致
    result = pipeline.process(raw, factor_config)
    assert "pe_ttm" in result.columns
    assert "roe_ttm" in result.columns
    assert len(result) == n
    assert result.notna().all().all()
    print("  [PASS] 向后兼容性 (不传中性化参数)\n")


def test_pipeline_with_neutralization():
    """测试 6: FactorPipeline.process() 带中性化配置"""
    factor, industry, ln_mktcap, stock_info_df = _make_test_data()

    raw = pd.DataFrame(
        {
            "pe_ttm": factor,
            "ln_market_cap": ln_mktcap,
        }
    )

    factor_config = [
        {"id": "pe_ttm", "direction": "negative", "weight": 0.7},
        {"id": "ln_market_cap", "direction": "negative", "weight": 0.3},
    ]

    neu_config = {
        "enabled": True,
        "dimensions": ["industry", "market_cap"],
    }

    pipeline = FactorPipeline()
    result = pipeline.process(raw, factor_config, stock_info_df, neu_config)

    # PE 中性化后行业差距缩小
    pe_neu_bank = result.loc[industry == "银行", "pe_ttm"].mean()
    pe_neu_tech = result.loc[industry == "科技", "pe_ttm"].mean()
    print(f"  PE 中性化后: 银行={pe_neu_bank:.4f}, 科技={pe_neu_tech:.4f}")

    # ln_market_cap 不应被中性化 (fid == 'ln_market_cap' 跳过)
    assert "ln_market_cap" in result.columns
    print("  [PASS] 带中性化配置的完整管线\n")


def test_pipeline_disabled_neutralization():
    """测试 7: 中性化配置 enabled=false 时不执行"""
    factor, industry, ln_mktcap, stock_info_df = _make_test_data()
    raw = pd.DataFrame({"pe_ttm": factor, "ln_market_cap": ln_mktcap})

    factor_config = [{"id": "pe_ttm", "direction": "negative", "weight": 1.0}]
    neu_config = {"enabled": False, "dimensions": ["industry"]}

    pipeline = FactorPipeline()

    # enabled=false 应与不传中性化结果相同
    result_off = pipeline.process(raw, factor_config, stock_info_df, neu_config)
    result_none = pipeline.process(raw, factor_config)

    pd.testing.assert_frame_equal(result_off, result_none)
    print("  [PASS] enabled=false 等效于不做中性化\n")


if __name__ == "__main__":
    print("=" * 60)
    print("中性化效果验证测试")
    print("=" * 60)

    tests = [
        test_neutralize_basic,
        test_neutralize_industry_only,
        test_neutralize_market_cap_only,
        test_neutralize_no_controls,
        test_pipeline_backward_compat,
        test_pipeline_with_neutralization,
        test_pipeline_disabled_neutralization,
    ]

    passed = 0
    failed = 0
    for t in tests:
        print(f"\n>> {t.__doc__}")
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {e}")
            failed += 1

    print("\n" + "=" * 60)
    print(f"结果: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)
    sys.exit(1 if failed else 0)
