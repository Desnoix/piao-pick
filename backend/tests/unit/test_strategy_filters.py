"""
策略过滤器 (filters.py) 单元测试

覆盖: filter_percentile_top, filter_threshold, filter_industry_diversify,
filter_universe, apply_filters 分发逻辑。
纯 DataFrame 操作, 无数据库/网络, 标记为 @pytest.mark.unit。
"""

import pandas as pd
import pytest

from app.core.strategy.filters import (
    apply_filters,
    filter_industry_diversify,
    filter_percentile_top,
    filter_threshold,
    filter_universe,
)

pytestmark = pytest.mark.unit


def _scored_df(n: int = 20) -> pd.DataFrame:
    """构造 n 行已评分的 DataFrame (已按 composite_score 降序)。"""
    return pd.DataFrame(
        {
            "ts_code": [f"{i:06d}" for i in range(1, n + 1)],
            "composite_score": list(range(n, 0, -1)),
        }
    )


class TestFilterPercentileTop:
    def test_keeps_top_n(self):
        df = _scored_df(20)
        result = filter_percentile_top(df, count=5)
        assert len(result) == 5
        assert list(result["ts_code"]) == ["000001", "000002", "000003", "000004", "000005"]

    def test_count_larger_than_df(self):
        df = _scored_df(3)
        result = filter_percentile_top(df, count=10)
        assert len(result) == 3


class TestFilterThreshold:
    def test_keeps_above_threshold(self):
        df = _scored_df(10)
        result = filter_threshold(df, threshold=5.0)
        assert all(result["composite_score"] >= 5.0)

    def test_zero_threshold_keeps_all(self):
        df = _scored_df(5)
        result = filter_threshold(df, threshold=0.0)
        assert len(result) == 5

    def test_missing_column_returns_unchanged(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        result = filter_threshold(df, threshold=1.0)
        pd.testing.assert_frame_equal(result, df)


class TestFilterIndustryDiversify:
    def test_limits_per_industry(self):
        df = pd.DataFrame(
            {
                "ts_code": ["A", "B", "C", "D", "E", "F"],
                "composite_score": [6, 5, 4, 3, 2, 1],
                "industry": ["X", "X", "X", "Y", "Y", "Y"],
            }
        )
        result = filter_industry_diversify(df, max_per_industry=2)
        assert len(result) == 4
        assert list(result["industry"]).count("X") == 2
        assert list(result["industry"]).count("Y") == 2

    def test_missing_industry_column_skips(self):
        df = pd.DataFrame({"ts_code": ["A"], "composite_score": [1]})
        result = filter_industry_diversify(df, max_per_industry=1)
        pd.testing.assert_frame_equal(result, df)

    def test_merges_from_stock_info(self):
        df = pd.DataFrame(
            {
                "ts_code": ["A", "B"],
                "composite_score": [2, 1],
            }
        )
        stock_info = pd.DataFrame(
            {"industry": ["食品", "食品"]},
            index=pd.Index(["A", "B"], name="ts_code"),
        )
        result = filter_industry_diversify(df, stock_info_df=stock_info, max_per_industry=1)
        assert len(result) == 1


class TestFilterUniverse:
    def _base_df(self) -> pd.DataFrame:
        return pd.DataFrame(
            {
                "ts_code": ["600519", "000001", "833171", "870001"],
                "is_st": [False, True, False, False],
                "is_suspended": [False, False, True, False],
                "list_date": ["2001-08-27", "1991-04-03", "2024-01-01", "2024-12-01"],
            },
            index=pd.Index(["600519", "000001", "833171", "870001"], name="ts_code"),
        )

    def test_exclude_st(self):
        df = self._base_df()
        result = filter_universe(df, {"exclude_st": True})
        assert "000001" not in result.index

    def test_exclude_suspended(self):
        df = self._base_df()
        result = filter_universe(df, {"exclude_suspended": True})
        assert "833171" not in result.index

    def test_exclude_bse(self):
        df = self._base_df()
        result = filter_universe(df, {"exclude_bse": True})
        assert "833171" not in result.index
        assert "870001" not in result.index

    def test_exclude_new_listing_days(self):
        df = self._base_df()
        # 设定 trade_date, 排除上市不足 1 年的
        result = filter_universe(
            df,
            {"exclude_new_listing_days": 365},
            trade_date="2025-06-01",
        )
        # 870001 上市 2024-12-01, 距今 < 365 天, 排除
        assert "870001" not in result.index
        assert "600519" in result.index


class TestApplyFilters:
    def test_applies_in_sequence(self):
        result = _scored_df(20)
        processed = pd.DataFrame(index=result["ts_code"])
        stock_info = pd.DataFrame(index=result["ts_code"])
        filters_config = [
            {"type": "percentile_top", "count": 10},
            {"type": "threshold", "value": 5.0},
        ]
        out = apply_filters(result, processed, stock_info, filters_config)
        assert len(out) <= 10
        assert all(out["composite_score"] >= 5.0)

    def test_unknown_filter_logs_and_continues(self):
        result = _scored_df(5)
        processed = pd.DataFrame(index=result["ts_code"])
        stock_info = pd.DataFrame(index=result["ts_code"])
        filters_config = [{"type": "totally_unknown_filter"}]
        out = apply_filters(result, processed, stock_info, filters_config)
        assert len(out) == 5
