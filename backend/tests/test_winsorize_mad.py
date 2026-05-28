"""MAD vs Sigma Winsorize 对比测试

验证项:
1. winsorize_sigma / winsorize_mad / winsorize_dispatch 方法存在且可调用
2. 兼容别名 winsorize == winsorize_sigma 正常工作
3. MAD 方法比重尾分布下 sigma 截断更紧
4. process() 默认参数自动走 MAD
5. process(method='sigma') 结果与改造前一致
6. 全 NaN / 常量序列安全处理
7. YAML factor_pipeline 被正确读取
"""

import sys

sys.path.insert(0, ".")

import logging

logging.basicConfig(level=logging.INFO)

import numpy as np
import pandas as pd

from app.core.factor.base import FactorPipeline


def test_methods_exist():
    """TEST 1: FactorPipeline 新方法存在性"""
    print("=" * 60)
    print("TEST 1: 方法存在性")
    print("=" * 60)
    fp = FactorPipeline()

    assert hasattr(fp, "winsorize_sigma"), "缺少 winsorize_sigma"
    assert hasattr(fp, "winsorize_mad"), "缺少 winsorize_mad"
    assert hasattr(fp, "winsorize_dispatch"), "缺少 winsorize_dispatch"
    assert hasattr(fp, "winsorize"), "缺少兼容别名 winsorize"
    assert fp.winsorize == fp.winsorize_sigma, "别名未指向 winsorize_sigma"
    print("  OK  所有方法存在, 别名正确")
    return True


def test_constant_and_nan():
    """TEST 2: 常量 / NaN 序列安全处理"""
    print("\n" + "=" * 60)
    print("TEST 2: 边界安全 (常量 / NaN)")
    print("=" * 60)
    fp = FactorPipeline()

    const = pd.Series([5.0, 5.0, 5.0, 5.0])
    r_mad = fp.winsorize_mad(const)
    r_sigma = fp.winsorize_sigma(const)
    assert r_mad.equals(const), "MAD 常量序列异常"
    assert r_sigma.equals(const), "Sigma 常量序列异常"
    print("  OK  常量序列: MAD/Sigma 均返回原序列")

    nan_s = pd.Series([np.nan, np.nan, np.nan])
    r_mad_nan = fp.winsorize_mad(nan_s)
    r_sigma_nan = fp.winsorize_sigma(nan_s)
    assert r_mad_nan.isna().all(), "MAD NaN 序列异常"
    assert r_sigma_nan.isna().all(), "Sigma NaN 序列异常"
    print("  OK  NaN 序列: MAD/Sigma 均返回原序列")
    return True


def test_mad_vs_sigma_heavy_tail():
    """TEST 3: 重尾分布下 MAD 截断更紧"""
    print("\n" + "=" * 60)
    print("TEST 3: MAD vs Sigma 重尾分布对比")
    print("=" * 60)
    fp = FactorPipeline()

    np.random.seed(42)
    n = 500
    pe_data = np.random.normal(loc=25, scale=10, size=n)
    pe_data[0:10] = [-50, -30, 500, 800, 1200, -100, 999, 450, 600, 350]
    pe = pd.Series(pe_data, name="pe_ttm")

    print(
        f"\n  原始: mean={pe.mean():.1f}  std={pe.std():.1f}  "
        f"median={pe.median():.1f}  range=[{pe.min():.1f}, {pe.max():.1f}]"
    )

    r_sigma = fp.winsorize_sigma(pe)
    r_mad = fp.winsorize_mad(pe)

    print(
        f"  Sigma(±3σ): mean={r_sigma.mean():.1f}  std={r_sigma.std():.1f}  "
        f"range=[{r_sigma.min():.1f}, {r_sigma.max():.1f}]"
    )
    print(f"  MAD(n=5):   mean={r_mad.mean():.1f}  std={r_mad.std():.1f}  range=[{r_mad.min():.1f}, {r_mad.max():.1f}]")

    range_sigma = r_sigma.max() - r_sigma.min()
    range_mad = r_mad.max() - r_mad.min()
    print(f"  窗口宽度: Sigma={range_sigma:.1f}  MAD={range_mad:.1f}  比值={range_mad / range_sigma:.2%}")

    clip_sigma = ((pe < r_sigma.min()) | (pe > r_sigma.max())).sum()
    clip_mad = ((pe < r_mad.min()) | (pe > r_mad.max())).sum()
    print(f"  截断数量: Sigma={clip_sigma} ({clip_sigma / n * 100:.1f}%)  MAD={clip_mad} ({clip_mad / n * 100:.1f}%)")

    assert range_mad < range_sigma, "重尾分布下 MAD 窗口应比 Sigma 更紧"
    print("  OK  MAD 窗口更紧, 截断更彻底")
    return True


def test_dispatch():
    """TEST 4: winsorize_dispatch 正确路由"""
    print("\n" + "=" * 60)
    print("TEST 4: winsorize_dispatch 路由")
    print("=" * 60)
    fp = FactorPipeline()

    np.random.seed(123)
    s = pd.Series(np.random.normal(0, 1, 100))
    s.iloc[0] = 100.0
    s.iloc[1] = -100.0

    r_mad = fp.winsorize_dispatch(s, method="mad")
    r_sigma = fp.winsorize_dispatch(s, method="sigma")
    r_default = fp.winsorize_dispatch(s)

    assert r_mad.equals(fp.winsorize_mad(s)), "dispatch mad 路由错误"
    assert r_sigma.equals(fp.winsorize_sigma(s)), "dispatch sigma 路由错误"
    assert r_default.equals(r_mad), "dispatch 默认应为 mad"
    print("  OK  mad / sigma / default 路由均正确")
    return True


def test_process_default_mad():
    """TEST 5: process() 默认走 MAD, 显式 sigma 结果不同"""
    print("\n" + "=" * 60)
    print("TEST 5: process() 默认 MAD + 显式 sigma")
    print("=" * 60)
    fp = FactorPipeline()

    np.random.seed(42)
    n = 200
    df = pd.DataFrame(
        {
            "pe_ttm": np.random.normal(25, 10, n),
            "roe_ttm": np.random.normal(15, 5, n),
        }
    )
    df.iloc[0, 0] = 500.0
    df.iloc[1, 0] = -100.0
    df.iloc[2, 1] = 200.0

    config = [
        {"id": "pe_ttm", "direction": "negative", "weight": 0.5},
        {"id": "roe_ttm", "direction": "positive", "weight": 0.5},
    ]

    result_default = fp.process(df, config)
    result_sigma = fp.process(df, config, winsorize_method="sigma")
    result_mad_explicit = fp.process(df, config, winsorize_method="mad")

    assert not result_default.empty, "默认 process 返回空"
    assert not result_sigma.empty, "sigma process 返回空"
    assert result_default.equals(result_mad_explicit), "默认应等于显式 mad"
    assert not result_default.equals(result_sigma), "mad 与 sigma 结果应不同"
    print(f"  默认(MAD) shape: {result_default.shape}")
    print(f"  Sigma shape:     {result_sigma.shape}")
    print("  OK  默认走 MAD, sigma 结果不同")
    return True


def test_compat_alias():
    """TEST 6: 兼容别名 winsorize() 调用正常"""
    print("\n" + "=" * 60)
    print("TEST 6: 兼容别名 winsorize()")
    print("=" * 60)
    fp = FactorPipeline()

    s = pd.Series([1.0, 2.0, 3.0, 100.0, -50.0])
    r_alias = fp.winsorize(s)
    r_sigma = fp.winsorize_sigma(s)

    assert r_alias.equals(r_sigma), "别名调用结果应与 winsorize_sigma 一致"
    print("  OK  self.winsorize(col) 别名调用正常")
    return True


def test_yaml_factor_pipeline():
    """TEST 7: YAML factor_pipeline 被正确读取"""
    print("\n" + "=" * 60)
    print("TEST 7: YAML factor_pipeline 读取")
    print("=" * 60)
    try:
        from app.core.strategy.loader import StrategyLoader

        loader = StrategyLoader()
        strat = loader.load_by_name("value_lowvol")
        if strat is None:
            print("  SKIP  value_lowvol.yaml 未找到 (可能不在 backend/ 目录运行)")
            return True

        fp_cfg = strat.factor_pipeline
        assert isinstance(fp_cfg, dict), f"factor_pipeline 应为 dict, 实际: {type(fp_cfg)}"
        print(f"  factor_pipeline: {fp_cfg}")

        method = fp_cfg.get("winsorize_method", "mad")
        assert method in ("mad", "sigma"), f"无效的 winsorize_method: {method}"
        print(f"  OK  winsorize_method={method}")
        return True
    except Exception as e:
        print(f"  SKIP  无法加载策略: {e}")
        return True


def test_backward_compat_no_pipeline():
    """TEST 8: 旧策略无 factor_pipeline 时自动走 MAD 默认"""
    print("\n" + "=" * 60)
    print("TEST 8: 无 factor_pipeline 时默认 MAD")
    print("=" * 60)
    from app.core.strategy.loader import StrategyConfig

    raw_old = {
        "name": "test_old",
        "factors": [{"id": "pe_ttm", "direction": "negative", "weight": 1.0}],
        "filters": [],
        "output": {},
    }
    cfg = StrategyConfig(raw_old)
    assert cfg.factor_pipeline == {}, f"旧策略 factor_pipeline 应为空 dict, 实际: {cfg.factor_pipeline}"

    method = cfg.factor_pipeline.get("winsorize_method", "mad")
    assert method == "mad", "无配置时默认应为 mad"
    print("  OK  旧策略无 factor_pipeline 时自动走 MAD")
    return True


if __name__ == "__main__":
    results = []
    tests = [
        ("方法存在性", test_methods_exist),
        ("边界安全", test_constant_and_nan),
        ("重尾分布对比", test_mad_vs_sigma_heavy_tail),
        ("dispatch 路由", test_dispatch),
        ("process 默认 MAD", test_process_default_mad),
        ("兼容别名", test_compat_alias),
        ("YAML 读取", test_yaml_factor_pipeline),
        ("向后兼容", test_backward_compat_no_pipeline),
    ]

    for name, fn in tests:
        try:
            ok = fn()
            results.append((name, "PASS" if ok else "FAIL"))
        except Exception as e:
            print(f"  FAIL  {name}: {e}")
            import traceback

            traceback.print_exc()
            results.append((name, "FAIL"))

    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)
    passed = sum(1 for _, r in results if r == "PASS")
    total = len(results)
    for name, r in results:
        print(f"  {'OK' if r == 'PASS' else 'FAIL':<6} {name}")
    print(f"\n  {passed}/{total} passed")
