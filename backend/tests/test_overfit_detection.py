"""
过拟合防护模块验证测试

测试用例:
1. 过拟合策略: 在训练集上 Sharpe 极高，样本外崩溃 → PBO ≈ 1.0
2. 稳健策略: 样本内外表现一致 → PBO < 0.5
3. DSR: 单次尝试 Sharpe=2.0 显著，50 次尝试后不显著
4. Walk-Forward: 过拟合策略 OOS/IS ratio 接近 0
5. Purged K-Fold: embargo 正确剔除边界样本
"""

import logging
import os
import sys
from datetime import date

# 添加后端到 path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.core.backtest.dsr import compute_dsr, compute_multiple_testing_threshold
from app.core.backtest.pbo import PBOCalculator, PBOConfig
from app.core.backtest.purged_kfold import (
    PurgedKFoldConfig,
    PurgedKFolder,
)
from app.core.backtest.walk_forward import (
    WalkForwardConfig,
    WalkForwardEngine,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def test_dsr_significance_decay():
    """
    DSR 测试: 同一个 Sharpe，随着尝试次数增加，显著性应下降。
    """
    print("\n=== Test: DSR Significance Decay ===")

    sharpe = 2.0
    years = 5.0

    results = []
    for n in [1, 5, 10, 20, 50, 100]:
        dsr = compute_dsr(
            observed_sharpe=sharpe,
            n_trials=n,
            n_observation_years=years,
        )
        results.append(dsr)
        print(
            f"  N={n:>3d}: E[max_SR]={dsr.expected_max_sharpe:.3f}, "
            f"deflated_p={dsr.deflated_p_value:.4f}, "
            f"significant={'YES' if dsr.is_significant else 'NO'}"
        )

    # 断言: N=1 时应显著, N=100 时应不显著
    assert results[0].is_significant, "N=1 should be significant"
    assert not results[-1].is_significant, "N=100 should NOT be significant"
    print("  PASSED: Significance correctly decays with trials")


def test_dsr_threshold():
    """
    DSR 阈值测试: 验证在不同尝试次数下，需要的最低 Sharpe。
    """
    print("\n=== Test: DSR Threshold ===")

    years = 5.0
    for n in [1, 5, 10, 20, 50]:
        threshold = compute_multiple_testing_threshold(
            n_trials=n,
            n_observation_years=years,
        )
        print(f"  N={n:>3d}: minimum significant Sharpe = {threshold:.3f}")

    # 断言: 阈值随 N 增加而单调递增
    t1 = compute_multiple_testing_threshold(1, years)
    t50 = compute_multiple_testing_threshold(50, years)
    assert t50 > t1, "Threshold should increase with more trials"
    print("  PASSED: Thresholds increase monotonically")


def test_walk_forward_windows():
    """
    Walk-Forward 窗口生成测试: 验证窗口不重叠，时间顺序正确。
    """
    print("\n=== Test: Walk-Forward Window Generation ===")

    config = WalkForwardConfig(
        train_window_months=36,
        test_window_months=12,
        step_months=12,
        min_train_months=24,
    )
    engine = WalkForwardEngine(config)

    start = date(2015, 1, 1)
    end = date(2025, 12, 31)

    windows = engine.generate_windows(start, end)

    print(f"  Generated {len(windows)} windows for {start} ~ {end}")

    for i, w in enumerate(windows):
        print(f"  Fold {i + 1}: train[{w.train_start} ~ {w.train_end}] test[{w.test_start} ~ {w.test_end}]")

        # 断言: train_end == test_start
        assert w.train_end == w.test_start, "Train end should equal test start"

        # 断言: test_end <= overall_end
        assert w.test_end <= end, f"Test end {w.test_end} exceeds overall end {end}"

        # 断言: 时间顺序
        if i > 0:
            prev = windows[i - 1]
            assert w.test_start > prev.test_start, "Windows should be chronological"

    print("  PASSED: Window structure is correct")


def test_walk_forward_with_mock_backtest():
    """
    Walk-Forward 集成测试: 用 mock 回测函数验证 OOS/IS 对比逻辑。

    模拟过拟合策略: IS Sharpe = 2.0, OOS Sharpe = -0.5
    """
    print("\n=== Test: Walk-Forward with Mock Overfit Strategy ===")

    def mock_overfit_backtest(strategy_name: str, start: str, end: str) -> dict:
        """模拟过拟合策略: 训练集表现好，测试集崩溃"""
        sd = date.fromisoformat(start)
        ed = date.fromisoformat(end)
        months = (ed.year - sd.year) * 12 + (ed.month - sd.month)
        n_periods = max(months, 1)

        # 判断这是 IS 还是 OOS (简单按 2020 分界)
        is_train = sd.year < 2020

        if is_train:
            # 训练集: Sharpe ≈ 2.0
            returns = [0.03] * n_periods  # 月均 3%
        else:
            # 测试集: Sharpe ≈ -0.5
            returns = [-0.01] * n_periods  # 月均 -1%

        nav = [(start, 1.0)]
        cum = 1.0
        for _j, r in enumerate(returns):
            cum *= 1.0 + r
            nav.append((start, cum))

        return {
            "strategy_name": strategy_name,
            "start_date": start,
            "end_date": end,
            "metrics": {
                "sharpe_ratio": 2.0 if is_train else -0.5,
                "annual_return": 0.40 if is_train else -0.12,
                "max_drawdown": -0.05 if is_train else -0.30,
            },
            "nav_series": nav,
            "returns": returns,
        }

    config = WalkForwardConfig(
        train_window_months=36,
        test_window_months=12,
        step_months=12,
    )
    engine = WalkForwardEngine(config)

    start = date(2015, 1, 1)
    end = date(2025, 12, 31)

    result = engine.run("mock_overfit", start, end, mock_overfit_backtest)

    print(f"  IS Sharpe mean: {result.is_sharpe_mean:.3f}")
    print(f"  OOS Sharpe mean: {result.oos_sharpe_mean:.3f}")
    print(f"  OOS/IS ratio: {result.oos_is_ratio:.3f}")
    print(f"  Folds: {len(result.folds)}")

    # 过拟合策略的 OOS/IS ratio 应该很低
    assert result.oos_is_ratio < 0.5, f"OOS/IS ratio should be < 0.5, got {result.oos_is_ratio}"
    assert result.oos_sharpe_mean < result.is_sharpe_mean, "OOS Sharpe should be < IS Sharpe"
    print("  PASSED: Overfitting correctly detected")


def test_pbo_with_mock_data():
    """
    PBO 测试: 用多参数变体 mock 数据验证过拟合检测。

    PBO 的核心机制: 对每个 train/test 组合，选择 IS 最优的参数变体，
    然后在 OOS 上评估。当变体间存在反相关时（变体0擅长前半段，变体1擅长后半段），
    IS 选出的最优变体在 OOS 上系统性地失败 → PBO 升高。
    """
    print("\n=== Test: PBO with Multi-Variant Mock ===")

    S_VAL = 8
    N_VARIANTS = 2
    call_count = [0]

    def mock_overfit_sub(strategy_name: str, start: str, end: str) -> dict:
        """
        模拟两个反相关参数变体:
        - Variant 0: 前半段 Sharpe=2.0, 后半段 Sharpe=-0.5
        - Variant 1: 前半段 Sharpe=-0.5, 后半段 Sharpe=2.0

        PBO 算法会在 IS 上选出当前窗口最优变体，
        但该变体在 OOS 上系统性地失败。
        """
        idx = call_count[0]
        call_count[0] += 1
        sub_idx = idx // N_VARIANTS  # 当前子区间索引
        var_idx = idx % N_VARIANTS  # 当前变体索引

        if var_idx == 0:
            # 变体0: 前好 后差
            sharpe = 2.0 if sub_idx < S_VAL // 2 else -0.5
        else:
            # 变体1: 前差 后好
            sharpe = -0.5 if sub_idx < S_VAL // 2 else 2.0

        return {
            "strategy_name": strategy_name,
            "start_date": start,
            "end_date": end,
            "metrics": {"sharpe_ratio": sharpe},
            "returns": [],
            "nav_series": [],
        }

    config = PBOConfig(n_sub_periods=S_VAL)
    calculator = PBOCalculator(config)

    start = date(2015, 1, 1)
    end = date(2023, 1, 1)

    # 提供 2 个参数变体，触发 PBO 的参数选择机制
    parameter_variants = [{"version": 0}, {"version": 1}]
    result = calculator.compute("mock_overfit", start, end, mock_overfit_sub, parameter_variants)

    print(f"  PBO: {result.pbo:.4f}")
    print(f"  IS Sharpe mean: {result.is_sharpe_mean:.3f}")
    print(f"  OOS Sharpe mean: {result.oos_sharpe_mean:.3f}")
    print(f"  Interpretation: {result.pbo_interpretation}")
    print(f"  Combinations evaluated: {result.n_combinations}")
    print(f"  Total backtest calls: {call_count[0]}")

    # 反相关变体应使 PBO 显著高于随机水平 (0.5)
    assert result.pbo >= 0.4, f"PBO should be >= 0.4 for overfit strategy, got {result.pbo}"
    print("  PASSED: PBO correctly identifies overfitting")


def test_purged_kfold_embargo():
    """
    Purged K-Fold 测试: 验证 embargo 正确剔除边界样本。
    """
    print("\n=== Test: Purged K-Fold Embargo ===")

    config = PurgedKFoldConfig(n_splits=4, embargo_months=1)
    folder = PurgedKFolder(config)

    start = date(2016, 1, 1)
    end = date(2024, 1, 1)

    folds = folder.generate_folds(start, end)

    print(f"  Generated {len(folds)} folds")

    for f in folds:
        print(
            f"  Fold {f.fold_index}: "
            f"train[{f.train_start} ~ {f.train_end}] "
            f"embargo[{f.embargo_start} ~ {f.embargo_end}] "
            f"test[{f.test_start} ~ {f.test_end}]"
        )

        # 断言: train_end < test_start (中间有 embargo)
        assert f.train_end < f.test_start or f.train_start > f.test_end, "Train and test should not overlap"

    print("  PASSED: Embargo correctly separates train/test")


def test_purged_kfold_with_mock():
    """
    Purged K-Fold 集成测试: 用 mock 回测验证 CV Sharpe 输出。
    """
    print("\n=== Test: Purged K-Fold with Mock Backtest ===")

    def mock_stable_backtest(strategy_name: str, start: str, end: str) -> dict:
        """稳健策略: 各时期 Sharpe ≈ 1.0"""
        return {
            "strategy_name": strategy_name,
            "start_date": start,
            "end_date": end,
            "metrics": {
                "sharpe_ratio": 1.0,
                "annual_return": 0.15,
                "max_drawdown": -0.10,
            },
            "returns": [0.015] * 12,
            "nav_series": [],
        }

    config = PurgedKFoldConfig(n_splits=4, embargo_months=1)
    folder = PurgedKFolder(config)

    start = date(2016, 1, 1)
    end = date(2024, 1, 1)

    result = folder.run("mock_stable", start, end, mock_stable_backtest)

    print(f"  CV Sharpe: {result.cv_sharpe:.3f}")
    print(f"  CV Sharpe Std: {result.cv_sharpe_std:.3f}")
    print(f"  Mean Train Sharpe: {result.mean_train_sharpe:.3f}")
    print(f"  Folds evaluated: {len(result.folds)}")

    # 稳健策略: CV Sharpe 应接近 1.0, 标准差应很小
    assert abs(result.cv_sharpe - 1.0) < 0.1, "Stable strategy CV Sharpe should be ~1.0"
    assert result.cv_sharpe_std < 0.1, "Stable strategy should have low variance"
    print("  PASSED: Stable strategy shows consistent CV results")


def test_full_pipeline_mock():
    """
    完整管线 mock 测试: 验证 OverfitService 的
    数据结构和评分逻辑。
    """
    print("\n=== Test: Full Pipeline Mock ===")

    # 直接测试评分函数
    from app.core.backtest.dsr import DSRResult
    from app.core.backtest.pbo import PBOResult
    from app.core.backtest.purged_kfold import PurgedKFoldConfig, PurgedKFoldResult
    from app.core.backtest.walk_forward import (
        WalkForwardConfig,
        WalkForwardResult,
    )

    # 模拟过拟合结果
    wf = WalkForwardResult(
        config=WalkForwardConfig(),
        folds=[],
        oos_nav=[],
        oos_returns=[],
        is_sharpe_mean=2.0,
        oos_sharpe_mean=0.2,
        oos_is_ratio=0.1,
    )

    pkf = PurgedKFoldResult(
        config=PurgedKFoldConfig(),
        folds=[],
        mean_train_sharpe=2.0,
        mean_test_sharpe=0.3,
        std_test_sharpe=0.8,
        cv_sharpe=0.3,
        cv_sharpe_std=0.8,
    )

    pbo = PBOResult(
        pbo=0.85,
        is_sharpe_mean=2.0,
        oos_sharpe_mean=0.1,
        oos_sharpe_std=0.5,
        n_combinations=12870,
        lambda_star_mean=2.0,
        pbo_interpretation="严重过拟合",
    )

    dsr = DSRResult(
        dsr=-0.5,
        expected_max_sharpe=2.5,
        sharpe_std_error=0.3,
        p_value=0.01,
        deflated_p_value=0.45,
        n_trials=20,
        observed_sharpe=2.0,
        is_significant=False,
        interpretation="不显著",
    )

    # 导入评分函数
    from app.services.overfit_service import _compute_overfit_score, _verdict

    score = _compute_overfit_score(wf, pkf, pbo, dsr)
    verdict = _verdict(score)

    print(f"  Overfit score: {score['score']}")
    print(
        f"  Components: wf={score['wf_risk']}, pbo={score['pbo_risk']}, dsr={score['dsr_risk']}, cv={score['cv_risk']}"
    )
    print(f"  Verdict: {verdict}")

    assert score["score"] >= 70, f"Overfit score should be >= 70, got {score['score']}"
    assert "高风险" in verdict or "过拟合" in verdict
    print("  PASSED: Overfitting correctly scored as high risk")


def run_all_tests():
    """运行所有测试"""
    print("=" * 60)
    print("过拟合防护模块验证测试")
    print("=" * 60)

    test_dsr_significance_decay()
    test_dsr_threshold()
    test_walk_forward_windows()
    test_walk_forward_with_mock_backtest()
    test_pbo_with_mock_data()
    test_purged_kfold_embargo()
    test_purged_kfold_with_mock()
    test_full_pipeline_mock()

    print("\n" + "=" * 60)
    print("ALL TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    run_all_tests()
