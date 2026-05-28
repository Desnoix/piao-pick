"""
StockRepository + FactorRepository 集成测试

覆盖: 基础 CRUD、K 线查询、因子查询。
使用真实 SQLite 临时文件, 标记为 @pytest.mark.integration。
"""

import pytest

from app.models import Factor, Kline, StockInfo
from app.repositories.factor_repo import FactorRepository
from app.repositories.stock_repo import StockRepository

pytestmark = pytest.mark.integration


class TestStockRepositoryBasic:
    """StockRepository 基本操作"""

    def test_upsert_and_get_stock_info(self, db_manager, sample_stocks):
        repo = StockRepository(db_manager)
        for s in sample_stocks:
            repo.upsert_stock_info(StockInfo(**s))

        info = repo.get_stock_info("600519")
        assert info is not None
        assert info.name == "贵州茅台"

    def test_get_stock_info_not_found(self, db_manager):
        repo = StockRepository(db_manager)
        assert repo.get_stock_info("999999") is None

    def test_get_all_stock_codes(self, db_manager, sample_stocks):
        repo = StockRepository(db_manager)
        for s in sample_stocks:
            repo.upsert_stock_info(StockInfo(**s))

        codes = repo.get_all_stock_codes()
        assert "600519" in codes
        assert "000001" in codes
        assert "300750" in codes

    def test_get_stock_info_list(self, db_manager, sample_stocks):
        repo = StockRepository(db_manager)
        for s in sample_stocks:
            repo.upsert_stock_info(StockInfo(**s))

        infos = repo.get_stock_info_list(["600519", "000001"])
        assert len(infos) == 2
        names = {i.name for i in infos}
        assert "贵州茅台" in names
        assert "平安银行" in names

    def test_upsert_batch(self, db_manager, sample_stocks):
        repo = StockRepository(db_manager)
        stocks = [StockInfo(**s) for s in sample_stocks]
        count = repo.upsert_stock_info_batch(stocks)
        assert count == 3

    def test_upsert_updates_existing(self, db_manager):
        repo = StockRepository(db_manager)
        s1 = StockInfo(ts_code="600519", name="原名", industry="食品饮料")
        repo.upsert_stock_info(s1)
        s2 = StockInfo(ts_code="600519", name="更新名", industry="食品饮料")
        repo.upsert_stock_info(s2)
        info = repo.get_stock_info("600519")
        assert info.name == "更新名"


class TestKlineOperations:
    """K 线数据操作"""

    def test_upsert_and_get_kline(self, db_manager, sample_stocks, sample_klines):
        repo = StockRepository(db_manager)
        for s in sample_stocks:
            repo.upsert_stock_info(StockInfo(**s))
        kl_objs = [Kline(**k) for k in sample_klines]
        repo.upsert_kline_batch(kl_objs[:5])  # insert 5 lines

        kline = repo.get_kline("600519", "2025-05-20")
        assert kline is not None
        assert kline.ts_code == "600519"
        assert kline.trade_date == "2025-05-20"

    def test_get_kline_not_found(self, db_manager):
        repo = StockRepository(db_manager)
        assert repo.get_kline("999999", "2025-01-01") is None

    def test_get_klines_by_date(self, db_manager, sample_stocks, sample_klines):
        repo = StockRepository(db_manager)
        for s in sample_stocks:
            repo.upsert_stock_info(StockInfo(**s))
        # Only 1 kline per stock on that date
        day0 = [Kline(**k) for k in sample_klines if k["trade_date"] == "2025-05-20"]
        repo.upsert_kline_batch(day0)

        klines = repo.get_klines_by_date("2025-05-20")
        assert len(klines) == 3
        codes = {k.ts_code for k in klines}
        assert codes == {"600519", "000001", "300750"}

    def test_get_kline_range(self, db_manager, sample_stocks, sample_klines):
        repo = StockRepository(db_manager)
        for s in sample_stocks:
            repo.upsert_stock_info(StockInfo(**s))
        kl_objs = [Kline(**k) for k in sample_klines]
        repo.upsert_kline_batch(kl_objs)

        klines = repo.get_kline_range("600519", "2025-05-21", "2025-05-23")
        assert len(klines) == 3
        for k in klines:
            assert k.ts_code == "600519"
            assert "2025-05-21" <= k.trade_date <= "2025-05-23"

    def test_has_kline_data(self, db_manager, sample_klines):
        repo = StockRepository(db_manager)
        kl = Kline(**sample_klines[0])
        repo.upsert_kline_batch([kl])
        assert repo.has_kline_data("600519", "2025-05-20") is True
        assert repo.has_kline_data("600519", "1999-01-01") is False


class TestFactorRepository:
    """FactorRepository 基本操作"""

    def test_upsert_and_get_factors(self, db_manager, sample_stocks):
        repo = StockRepository(db_manager)
        for s in sample_stocks:
            repo.upsert_stock_info(StockInfo(**s))

        factor_repo = FactorRepository(db_manager)
        f = Factor(
            ts_code="600519",
            trade_date="2025-05-20",
            pe_ttm=25.5,
            pb=8.2,
            roe_ttm=0.32,
        )
        factor_repo.upsert_factor(f)

        factors = factor_repo.get_factors_by_date("2025-05-20")
        assert len(factors) == 1
        assert factors[0].pe_ttm == 25.5

    def test_upsert_factor_batch(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        factors = [
            Factor(ts_code="000001", trade_date="2025-05-20", pe_ttm=5.0),
            Factor(ts_code="000001", trade_date="2025-05-21", pe_ttm=5.5),
        ]
        count = factor_repo.upsert_factor_batch(factors)
        assert count == 2

    def test_get_factors_by_code(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        factors = [
            Factor(ts_code="000001", trade_date="2025-05-20", pe_ttm=5.0),
            Factor(ts_code="000001", trade_date="2025-05-21", pe_ttm=5.5),
        ]
        factor_repo.upsert_factor_batch(factors)

        result = factor_repo.get_factors_by_code("000001", "2025-05-20", "2025-05-21")
        assert len(result) == 2

    def test_get_factor(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        f = Factor(ts_code="300750", trade_date="2025-05-20", pe_ttm=30.0)
        factor_repo.upsert_factor(f)

        result = factor_repo.get_factor("300750", "2025-05-20")
        assert result is not None
        assert result.pe_ttm == 30.0

    def test_get_factor_not_found(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        assert factor_repo.get_factor("999999", "2025-01-01") is None

    def test_empty_factors_returns_empty_list(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        assert factor_repo.get_factors_by_date("2029-12-31") == []

    def test_get_latest_trade_date(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        factors = [
            Factor(ts_code="000001", trade_date="2025-05-20", pe_ttm=5.0),
            Factor(ts_code="000001", trade_date="2025-05-25", pe_ttm=5.5),
        ]
        factor_repo.upsert_factor_batch(factors)

        latest = factor_repo.get_latest_trade_date("000001")
        assert latest == "2025-05-25"

    def test_get_latest_trade_date_not_found(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        assert factor_repo.get_latest_trade_date("999999") is None

    def test_get_factors_snapshot_empty(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        df = factor_repo.get_factors_snapshot("2029-12-31")
        import pandas as pd
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_get_factors_snapshot_with_data(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        factors = [
            Factor(ts_code="600519", trade_date="2025-05-20", pe_ttm=25.0, pb=8.0),
            Factor(ts_code="000001", trade_date="2025-05-20", pe_ttm=5.0, pb=0.5),
        ]
        factor_repo.upsert_factor_batch(factors)

        df = factor_repo.get_factors_snapshot("2025-05-20")
        assert len(df) == 2
        assert df.index.name == "ts_code"
        assert "pe_ttm" in df.columns

    def test_get_factors_range(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        factors = [
            Factor(ts_code="000001", trade_date="2025-05-20", pe_ttm=5.0),
            Factor(ts_code="000001", trade_date="2025-05-21", pe_ttm=5.5),
            Factor(ts_code="000001", trade_date="2025-05-22", pe_ttm=6.0),
        ]
        factor_repo.upsert_factor_batch(factors)

        df = factor_repo.get_factors_range("2025-05-20", "2025-05-21")
        assert len(df) == 2

    def test_get_factors_range_empty(self, db_manager):
        factor_repo = FactorRepository(db_manager)
        import pandas as pd
        df = factor_repo.get_factors_range("2029-01-01", "2029-01-31")
        assert isinstance(df, pd.DataFrame)
        assert df.empty
