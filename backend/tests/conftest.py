"""
pytest 共享 fixtures

提供测试数据库、示例数据、FastAPI 测试客户端等基础设施。
所有 fixture 均使用 function scope, 确保测试间完全隔离。
"""

import os
import sys
import tempfile
import uuid
from pathlib import Path
from typing import Generator

import pytest
from sqlmodel import Session, SQLModel, create_engine

# 确保 backend/ 在 sys.path 中, 以便 `import app`, `import data_provider` 等
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))


# --------------------------------------------------------------------
# Singletons reset
# --------------------------------------------------------------------


@pytest.fixture(scope="session", autouse=True)
def _reset_singletons():
    """会话开始前/结束后重置 Config 和 DatabaseManager 单例, 防止跨测试污染。"""
    from app.config import Config
    from app.database import DatabaseManager

    Config.reset_instance()
    DatabaseManager.reset_instance()
    yield
    Config.reset_instance()
    DatabaseManager.reset_instance()


# --------------------------------------------------------------------
# Database fixtures
# --------------------------------------------------------------------


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """为每个测试创建一个独立的临时 SQLite 数据库文件路径。"""
    return str(tmp_path / "test_piao_pick.db")


@pytest.fixture
def db_session(db_path: str):
    """
    测试数据库引擎 + 会话工厂。

    使用 SQLite 临时文件, 每个测试独立建表, 测试结束自动销毁。
    返回一个 callable, 调用即可获取新的 Session 实例 (上下文管理器)。
    """
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={"check_same_thread": False},
    )

    # 导入所有模型以注册到 SQLModel.metadata
    from app.models import (  # noqa: F401
        Factor,
        HistorySyncTask,
        Kline,
        SelectionResult,
        StockInfo,
        Strategy,
    )

    SQLModel.metadata.create_all(engine)

    def _get_session() -> Session:
        return Session(engine)

    yield _get_session

    engine.dispose()


@pytest.fixture
def db_manager(db_path: str):
    """
    覆盖 DatabaseManager 单例, 指向临时数据库。

    返回 DatabaseManager 实例, 可直接传入 Repository 构造函数。
    测试结束后恢复原 __init__ 并重置单例。
    """
    from app.database import DatabaseManager

    # 重置单例, 防止旧实例污染
    DatabaseManager.reset_instance()

    # 直接构造一个指向临时路径的实例并注入为单例
    manager = DatabaseManager(db_path=db_path)
    DatabaseManager._instance = manager

    yield manager

    DatabaseManager.reset_instance()


# --------------------------------------------------------------------
# Sample data fixtures
# --------------------------------------------------------------------


@pytest.fixture
def sample_stocks() -> list[dict]:
    """3 只测试股票数据 (600519, 000001, 300750)。"""
    return [
        {
            "ts_code": "600519",
            "name": "贵州茅台",
            "industry": "食品饮料",
            "list_date": "2001-08-27",
            "is_st": False,
            "is_suspended": False,
        },
        {
            "ts_code": "000001",
            "name": "平安银行",
            "industry": "银行",
            "list_date": "1991-04-03",
            "is_st": False,
            "is_suspended": False,
        },
        {
            "ts_code": "300750",
            "name": "宁德时代",
            "industry": "电气设备",
            "list_date": "2018-06-11",
            "is_st": False,
            "is_suspended": False,
        },
    ]


@pytest.fixture
def sample_klines() -> list[dict]:
    """3 只股票 x 5 个交易日的 K 线数据。"""
    dates = ["2025-05-20", "2025-05-21", "2025-05-22", "2025-05-23", "2025-05-26"]
    codes = ["600519", "000001", "300750"]
    base_prices = {"600519": 1800.0, "000001": 12.0, "300750": 210.0}
    klines = []
    for code in codes:
        base = base_prices[code]
        for i, d in enumerate(dates):
            klines.append(
                {
                    "ts_code": code,
                    "trade_date": d,
                    "open": base + i * 2,
                    "high": base + i * 2 + 5,
                    "low": base + i * 2 - 3,
                    "close": base + i * 2 + 1,
                    "volume": 100000 + i * 10000,
                    "amount": (base + i * 2) * 100000,
                    "close_adj": base + i * 2 + 1,
                }
            )
    return klines


@pytest.fixture
def sample_strategy_yaml() -> str:
    """一个完整的测试策略 YAML 配置字符串 (满足 API 校验: 含 name 和 factors)。"""
    return (
        "name: test_value\n"
        "display_name: 测试价值策略\n"
        "description: 用于单元测试的策略配置\n"
        "category: value\n"
        "version: '1.0'\n"
        "default_active: true\n"
        "default_priority: 10\n"
        "\n"
        "universe:\n"
        "  exclude_st: true\n"
        "  exclude_new_listing_days: 60\n"
        "  exclude_suspended: true\n"
        "  exclude_bse: true\n"
        "\n"
        "factors:\n"
        "  - id: pe_ttm\n"
        "    name: 'PE(TTM)'\n"
        "    weight: 0.30\n"
        "    direction: negative\n"
        "  - id: roe_ttm\n"
        "    name: 'ROE(TTM)'\n"
        "    weight: 0.40\n"
        "    direction: positive\n"
        "  - id: ret_60d_vol\n"
        "    name: '60日波动率'\n"
        "    weight: 0.30\n"
        "    direction: negative\n"
        "\n"
        "filters:\n"
        "  - type: percentile_top\n"
        "    count: 50\n"
        "\n"
        "output:\n"
        "  max_stocks: 10\n"
    )


@pytest.fixture
def seeded_db(db_session, sample_stocks, sample_klines, sample_strategy_yaml):
    """
    预填充了股票、K 线和策略的数据库。

    返回 db_session callable, 同时已将示例数据写入临时数据库。
    """
    from app.models import Kline, StockInfo, Strategy

    with db_session() as session:
        for s in sample_stocks:
            session.add(StockInfo(**s))

        for k in sample_klines:
            session.add(Kline(**k))

        strategy_id = uuid.uuid4().hex
        session.add(
            Strategy(
                id=strategy_id,
                name="test_value",
                display_name="测试价值策略",
                description="自动化测试用",
                category="value",
                config=sample_strategy_yaml,
                is_active=True,
                priority=10,
                created_at="2025-05-20T00:00:00",
                updated_at="2025-05-20T00:00:00",
            )
        )
        session.commit()

    return db_session


# --------------------------------------------------------------------
# FastAPI TestClient
# --------------------------------------------------------------------


@pytest.fixture
def fastapi_test_client(db_path: str, monkeypatch):
    """
    FastAPI TestClient, 数据库指向临时文件。

    通过 monkeypatch 覆盖 DB_PATH 环境变量, 确保 API 端点使用测试数据库。
    使用 TestClient 的上下文管理器以触发 app lifespan (调度器初始化等)。
    """
    monkeypatch.setenv("DB_PATH", db_path)
    monkeypatch.setenv("SCHEDULE_ENABLED", "false")

    from app.config import Config
    from app.database import DatabaseManager

    Config.reset_instance()
    DatabaseManager.reset_instance()

    from fastapi.testclient import TestClient

    from app.main import create_app

    app = create_app()
    with TestClient(app, raise_server_exceptions=False) as client:
        yield client

    Config.reset_instance()
    DatabaseManager.reset_instance()
