"""
FactorPipeline 单元测试

覆盖: winsorize (sigma + MAD), z_score, align_direction, process, composite_score。
纯数值计算, 无数据库, 无网络, 标记为 @pytest.mark.unit。
"""

import numpy as np
import pandas as pd
import pytest

from app.core.factor.base import FactorPipeline

pytestmark = pytest.mark.unit


class TestWinsorizeSigma:
    """基于 ±Nσ 的极值截断"""

    def test_clips_outliers_at_3sigma(self):
        pipe = FactorPipeline()
        # 需要足够多的正常值以避免 masking 效应 (σ 被离群值膨胀)
        data = pd.Series([1.0] * 19 + [2.0, 3.0, 4.0, 5.0, 100.0])
        result = pipe.winsorize_sigma(data, limits=(-3.0, 3.0))
        assert result.max() < 100, "100 是离群值, 应被截断"

    def test_alias_winsorize(self):
        # winsorize 是 winsorize_sigma 的别名
        assert FactorPipeline.winsorize is FactorPipeline.winsorize_sigma

    def test_no_change_when_all_normal(self):
        pipe = FactorPipeline()
        data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        result = pipe.winsorize_sigma(data)
        pd.testing.assert_series_equal(result, data)

    def test_zero_std_returns_original(self):
        pipe = FactorPipeline()
        data = pd.Series([5.0, 5.0, 5.0, 5.0])
        result = pipe.winsorize_sigma(data)
        pd.testing.assert_series_equal(result, data)

    def test_custom_limits(self):
        pipe = FactorPipeline()
        data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0])
        result_tight = pipe.winsorize_sigma(data, limits=(-1.0, 1.0))
        result_wide = pipe.winsorize_sigma(data, limits=(-3.0, 3.0))
        assert result_tight.max() <= result_wide.max()
        assert result_tight.min() >= result_wide.min()

    def test_handles_nan_values(self):
        pipe = FactorPipeline()
        data = pd.Series([1.0, 2.0, np.nan, 4.0, 100.0])
        result = pipe.winsorize_sigma(data)
        assert result.notna().sum() >= 4


class TestWinsorizeMad:
    """基于 MAD 的鲁棒极值处理"""

    def test_clips_outliers(self):
        pipe = FactorPipeline()
        data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 1000.0])
        result = pipe.winsorize_mad(data, n=5.0)
        assert result.max() < 1000

    def test_zero_mad_returns_original(self):
        pipe = FactorPipeline()
        data = pd.Series([5.0, 5.0, 5.0, 5.0])
        result = pipe.winsorize_mad(data, n=5.0)
        pd.testing.assert_series_equal(result, data)

    def test_tighter_n_clips_more(self):
        pipe = FactorPipeline()
        data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 100.0, 200.0])
        tight = pipe.winsorize_mad(data, n=3.0)
        wide = pipe.winsorize_mad(data, n=10.0)
        assert tight.max() <= wide.max()


class TestWinsorizeDispatch:
    """分发器: 按 method 参数选择 sigma / MAD"""

    def test_dispatch_sigma(self):
        pipe = FactorPipeline()
        data = pd.Series([1.0] * 19 + [2.0, 3.0, 4.0, 5.0, 100.0])
        out = pipe.winsorize_dispatch(data, method="sigma", limits_sigma=(-3.0, 3.0))
        assert out.max() < 100

    def test_dispatch_mad_default(self):
        pipe = FactorPipeline()
        data = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 1000.0])
        out = pipe.winsorize_dispatch(data)
        assert out.max() < 1000


class TestZScore:
    """Z-Score 标准化测试"""

    def test_mean_zero_std_one(self):
        pipe = FactorPipeline()
        data = pd.Series([10.0, 20.0, 30.0, 40.0, 50.0])
        result = pipe.z_score(data)
        assert abs(result.mean()) < 1e-10, "Z-Score 后均值应为 0"
        assert abs(result.std() - 1.0) < 0.1, "Z-Score 后标准差约为 1 (ddof=1)"

    def test_zero_std_returns_zeros(self):
        pipe = FactorPipeline()
        data = pd.Series([7.0, 7.0, 7.0])
        result = pipe.z_score(data)
        assert all(result == 0.0), "std=0 时应返回全 0"

    def test_nan_std_returns_zeros(self):
        pipe = FactorPipeline()
        data = pd.Series([np.nan, np.nan])
        result = pipe.z_score(data)
        assert all(result == 0.0)

    def test_preserves_index(self):
        pipe = FactorPipeline()
        data = pd.Series([1, 2, 3], index=["A", "B", "C"])
        result = pipe.z_score(data)
        assert list(result.index) == ["A", "B", "C"]


class TestAlignDirection:
    """方向对齐测试"""

    def test_positive_unchanged(self):
        pipe = FactorPipeline()
        data = pd.Series([1.0, -2.0, 3.0])
        result = pipe.align_direction(data, "positive")
        pd.testing.assert_series_equal(result, data)

    def test_negative_inverts(self):
        pipe = FactorPipeline()
        data = pd.Series([1.0, 2.0, 3.0])
        result = pipe.align_direction(data, "negative")
        pd.testing.assert_series_equal(result, pd.Series([-1.0, -2.0, -3.0]))


class TestProcess:
    """完整因子处理流程测试 (process)"""

    def test_process_produces_all_configured_factors(self):
        pipe = FactorPipeline()
        raw = pd.DataFrame(
            {
                "pe_ttm": [10, 15, 20, 25, 12, 18, 22, 30, 14, 16],
                "roe_ttm": [0.15, 0.20, 0.10, 0.25, 0.18, 0.12, 0.22, 0.08, 0.19, 0.21],
            }
        )
        config = [
            {"id": "pe_ttm", "direction": "negative", "weight": 0.5},
            {"id": "roe_ttm", "direction": "positive", "weight": 0.5},
        ]
        result = pipe.process(raw, config)
        assert "pe_ttm" in result.columns
        assert "roe_ttm" in result.columns
        assert len(result) == 10

    def test_process_skips_missing_factors(self):
        pipe = FactorPipeline()
        raw = pd.DataFrame({"pe_ttm": [10.0, 20.0, 30.0]})
        config = [
            {"id": "pe_ttm", "direction": "negative", "weight": 0.5},
            {"id": "nonexistent_factor", "direction": "positive", "weight": 0.5},
        ]
        result = pipe.process(raw, config)
        assert "pe_ttm" in result.columns
        assert "nonexistent_factor" not in result.columns

    def test_process_handles_nan_fillna(self):
        pipe = FactorPipeline()
        raw = pd.DataFrame({"pe_ttm": [10.0, np.nan, 20.0, 30.0, 25.0]})
        config = [{"id": "pe_ttm", "direction": "negative", "weight": 1.0}]
        result = pipe.process(raw, config)
        assert result["pe_ttm"].notna().all(), "NaN 应被均值填充"

    def test_process_sigma_method(self):
        pipe = FactorPipeline()
        raw = pd.DataFrame({"pe_ttm": list(range(1, 11))})
        config = [{"id": "pe_ttm", "direction": "positive", "weight": 1.0}]
        result = pipe.process(raw, config, winsorize_method="sigma")
        assert "pe_ttm" in result.columns
        assert result["pe_ttm"].notna().all()

    def test_process_preserves_index(self):
        pipe = FactorPipeline()
        raw = pd.DataFrame(
            {"pe_ttm": [10.0, 20.0, 30.0, 40.0]},
            index=["600519", "000001", "300750", "601318"],
        )
        config = [{"id": "pe_ttm", "direction": "positive", "weight": 1.0}]
        result = pipe.process(raw, config)
        assert list(result.index) == ["600519", "000001", "300750", "601318"]


class TestCompositeScore:
    """加权综合得分测试 (返回加权 Z-Score, 非 0-100)"""

    def test_score_is_zscore_centered(self):
        pipe = FactorPipeline()
        raw = pd.DataFrame(
            {
                "pe_ttm": [10, 15, 20, 25, 30],
                "roe_ttm": [0.1, 0.2, 0.15, 0.3, 0.05],
            }
        )
        config = [
            {"id": "pe_ttm", "direction": "negative", "weight": 0.5},
            {"id": "roe_ttm", "direction": "positive", "weight": 0.5},
        ]
        processed = pipe.process(raw, config)
        scores = pipe.composite_score(processed, config)
        assert len(scores) == 5
        # 加权 Z-Score 均值接近 0
        assert abs(scores.mean()) < 0.5

    def test_zero_weight_returns_zero(self):
        pipe = FactorPipeline()
        processed = pd.DataFrame({"pe_ttm": [1.0, -1.0]})
        config = [{"id": "pe_ttm", "direction": "positive", "weight": 0}]
        scores = pipe.composite_score(processed, config)
        assert all(scores == 0.0)

    def test_all_equal_values_returns_zero(self):
        pipe = FactorPipeline()
        raw = pd.DataFrame({"pe_ttm": [1.0, 1.0, 1.0]})
        config = [{"id": "pe_ttm", "direction": "positive", "weight": 1.0}]
        processed = pipe.process(raw, config)
        scores = pipe.composite_score(processed, config)
        # 所有值相同 -> Z-Score 全 0 -> 加权后仍为 0
        assert all(scores == 0.0)

    def test_weight_proportion_matters(self):
        pipe = FactorPipeline()
        processed = pd.DataFrame(
            {
                "a": [1.0, 0.5, 0.0],
                "b": [0.0, 0.5, 1.0],
            }
        )
        config_heavy_a = [
            {"id": "a", "weight": 0.9, "direction": "positive"},
            {"id": "b", "weight": 0.1, "direction": "positive"},
        ]
        config_heavy_b = [
            {"id": "a", "weight": 0.1, "direction": "positive"},
            {"id": "b", "weight": 0.9, "direction": "positive"},
        ]
        scores_a = pipe.composite_score(processed, config_heavy_a)
        scores_b = pipe.composite_score(processed, config_heavy_b)
        assert scores_a.iloc[0] > scores_b.iloc[0], "A 权重大时第一行应更高"
        assert scores_b.iloc[2] > scores_a.iloc[2], "B 权重大时第三行应更高"

    def test_ignores_missing_factor_column(self):
        pipe = FactorPipeline()
        processed = pd.DataFrame({"pe_ttm": [1.0, -1.0, 0.5]})
        config = [
            {"id": "pe_ttm", "direction": "positive", "weight": 0.5},
            {"id": "ghost", "direction": "positive", "weight": 0.5},
        ]
        scores = pipe.composite_score(processed, config)
        assert len(scores) == 3
        assert scores.notna().all()
