# -*- coding: utf-8 -*-
"""Phase 1 Integration Test"""
import sys
import os
sys.path.insert(0, '.')

def test_imports():
    """Test all core module imports"""
    print("=" * 60)
    print("TEST 1: Core Module Imports")
    print("=" * 60)

    modules = [
        ("app.main", "app"),
        ("app.config", "config"),
        ("app.database", "database"),
        ("app.logging_config", "logging"),
        ("app.core.trading_calendar", "trading_calendar"),
        ("app.core.pipeline", "pipeline"),
        ("app.core.scheduler", "scheduler"),
        ("app.core.factor.base", "factor"),
        ("app.core.strategy.loader", "strategy_loader"),
        ("app.core.strategy.executor", "strategy_executor"),
        ("app.core.strategy.filters", "strategy_filters"),
        ("app.repositories.stock_repo", "stock_repo"),
        ("app.repositories.factor_repo", "factor_repo"),
        ("app.repositories.strategy_repo", "strategy_repo"),
        ("app.repositories.selection_repo", "selection_repo"),
        ("app.repositories.backtest_repo", "backtest_repo"),
        ("app.schemas.stock", "stock_schema"),
        ("app.schemas.strategy", "strategy_schema"),
        ("app.schemas.selection", "selection_schema"),
        ("app.services.data_service", "data_service"),
        ("data_provider", "data_provider"),
        ("data_provider.base", "base_fetcher"),
        ("data_provider.akshare_fetcher", "akshare_fetcher"),
        ("data_provider.tushare_fetcher", "tushare_fetcher"),
    ]

    passed = 0
    failed = 0
    for mod_name, label in modules:
        try:
            __import__(mod_name)
            print(f"  OK {label}")
            passed += 1
        except Exception as e:
            print(f"  FAIL {label}: {e}")
            failed += 1

    print(f"\n  Results: {passed} passed, {failed} failed")
    return failed == 0


def test_config():
    """Test config loading"""
    print("\n" + "=" * 60)
    print("TEST 2: Config Loading")
    print("=" * 60)

    from app.config import get_config, Config
    config = get_config()
    print(f"  db_path: {config.db_path}")
    print(f"  schedule_enabled: {config.schedule_enabled}")
    print(f"  schedule_time: {config.schedule_time}")
    print(f"  max_workers: {config.max_workers}")
    print(f"  log_level: {config.log_level}")

    issues = config.validate()
    if issues:
        print(f"  Validation issues: {issues}")
    else:
        print("  Validation: OK")
    return True


def test_database():
    """Test database connection and table creation"""
    print("\n" + "=" * 60)
    print("TEST 3: Database")
    print("=" * 60)

    from app.database import get_db
    db = get_db()
    print(f"  db_path: {db.db_path}")

    with db.get_session() as session:
        from app.models import StockInfo, Kline, Factor, Strategy, SelectionResult
        # Check tables exist
        from sqlalchemy import inspect
        inspector = inspect(session.bind)
        tables = inspector.get_table_names()
        print(f"  Tables: {tables}")

    return True


def test_trading_calendar():
    """Test trading calendar"""
    print("\n" + "=" * 60)
    print("TEST 4: Trading Calendar")
    print("=" * 60)

    from app.core.trading_calendar import is_market_open, get_market_now
    from datetime import date

    now = get_market_now()
    print(f"  Market now: {now}")

    today = date.today()
    is_open = is_market_open(today)
    print(f"  Is {today} a trading day? {is_open}")

    return True


def test_data_provider():
    """Test data provider"""
    print("\n" + "=" * 60)
    print("TEST 5: Data Provider")
    print("=" * 60)

    from data_provider import DataFetcherManager, normalize_stock_code, canonical_stock_code
    from data_provider import is_st_stock, is_bse_code

    # Test code normalization
    tests = [
        ("600519.SH", "600519"),
        ("000001.SZ", "000001"),
        ("SH600519", "600519"),
        ("600519", "600519"),
    ]
    for input_code, expected in tests:
        result = normalize_stock_code(input_code)
        status = "OK" if result == expected else "FAIL"
        print(f"  {status} normalize('{input_code}') = '{result}' (expected '{expected}')")

    # Test ST detection
    print(f"  ST check: is_st_stock('*ST某股') = {is_st_stock('*ST某股')}")

    # Test BSE detection
    print(f"  BSE check: is_bse_code('920748') = {is_bse_code('920748')}")

    # Test manager
    manager = DataFetcherManager()
    fetcher_names = manager.available_fetchers
    print(f"  Manager initialized ({len(fetcher_names)} fetchers)")
    for name in fetcher_names:
        print(f"    - {name}")

    return True


def test_fastapi():
    """Test FastAPI app"""
    print("\n" + "=" * 60)
    print("TEST 6: FastAPI Server")
    print("=" * 60)

    try:
        from app.main import app
        from fastapi.testclient import TestClient

        client = TestClient(app)

        # Health check
        resp = client.get("/api/health")
        print(f"  GET /api/health: {resp.status_code}")

        # v1 endpoints
        endpoints = [
            "/api/v1/stocks",
            "/api/v1/strategies",
            "/api/v1/selection/results",
            "/api/v1/data/status",
        ]
        for ep in endpoints:
            resp = client.get(ep)
            print(f"  GET {ep}: {resp.status_code}")

        return True
    except Exception as e:
        print(f"  FAIL: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_strategy_loader():
    """Test strategy YAML loading"""
    print("\n" + "=" * 60)
    print("TEST 7: Strategy Loader")
    print("=" * 60)

    from app.core.strategy.loader import StrategyLoader

    loader = StrategyLoader()
    strategies = loader.load_all()

    print(f"  Loaded {len(strategies)} strategies")
    for cfg in strategies:
        print(f"    - {cfg.name} ({cfg.display_name}): {len(cfg.factors)} factors")

    return len(strategies) > 0


def test_repositories():
    """Test repository CRUD"""
    print("\n" + "=" * 60)
    print("TEST 8: Repositories")
    print("=" * 60)

    from app.database import get_db
    from app.repositories.stock_repo import StockRepository
    from app.repositories.strategy_repo import StrategyRepository
    from app.repositories.factor_repo import FactorRepository
    from app.repositories.selection_repo import SelectionRepository

    db = get_db()

    stock_repo = StockRepository(db)
    codes = stock_repo.get_all_stock_codes()
    print(f"  StockRepository: {len(codes)} stocks")

    strategy_repo = StrategyRepository(db)
    strategies = strategy_repo.get_all()
    print(f"  StrategyRepository: {len(strategies)} strategies")

    factor_repo = FactorRepository(db)
    print(f"  FactorRepository: OK")

    selection_repo = SelectionRepository(db)
    print(f"  SelectionRepository: OK")

    return True


def main():
    print("Piao Pick - Phase 1 Integration Test")
    print("=" * 60)

    results = {}
    tests = [
        ("imports", test_imports),
        ("config", test_config),
        ("database", test_database),
        ("trading_calendar", test_trading_calendar),
        ("data_provider", test_data_provider),
        ("fastapi", test_fastapi),
        ("strategy_loader", test_strategy_loader),
        ("repositories", test_repositories),
    ]

    for name, fn in tests:
        try:
            results[name] = fn()
        except Exception as e:
            print(f"\n  EXCEPTION in {name}: {e}")
            import traceback
            traceback.print_exc()
            results[name] = False

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    for name, ok in results.items():
        status = "PASS" if ok else "FAIL"
        print(f"  {status}: {name}")
    print(f"\n  Total: {passed}/{total} passed")

    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
