"""
数据库初始化脚本

创建所有数据库表和初始数据。

用法:
    cd backend
    python scripts/init_db.py
"""

import logging
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))


def _perform_index_migrations(db, logger):
    """创建性能优化索引 (幂等, 使用 IF NOT EXISTS)。"""
    import logging as _logging
    from sqlalchemy import text

    # 查询频繁模式的覆盖索引
    indexes: dict[str, str] = {
        # kline_daily: 按日期查询全市场行情 (data_status, backtest, factor_compute)
        "idx_kline_trade_date": "CREATE INDEX IF NOT EXISTS idx_kline_trade_date ON kline_daily(trade_date)",
        # factor_daily: 按日期查询全市场因子 (selection, backtest, data_status)
        "idx_factor_trade_date": "CREATE INDEX IF NOT EXISTS idx_factor_trade_date ON factor_daily(trade_date)",
        # stock_info: 关键词模糊搜索 (list_stocks)
        "idx_stock_name": "CREATE INDEX IF NOT EXISTS idx_stock_name ON stock_info(name)",
        # selection_results: 按策略+日期联合查询 (selection results 端点)
        "idx_selection_strategy_date": (
            "CREATE INDEX IF NOT EXISTS idx_selection_strategy_date "
            "ON selection_results(strategy_id, trade_date)"
        ),
        # history_sync_tasks: 按状态查询 (history_sync 轮询)
        "idx_history_sync_status": (
            "CREATE INDEX IF NOT EXISTS idx_history_sync_status "
            "ON history_sync_tasks(status)"
        ),
    }

    try:
        with db.get_session() as session:
            existing = {row[0] for row in session.execute(text(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )).fetchall()}
    except Exception as e:
        logger.warning(f"Failed to query existing indexes: {e}")
        existing = set()

    created = 0
    for name, ddl in indexes.items():
        if name in existing:
            logger.debug(f"✓ Index {name} already exists")
            continue
        try:
            with db.get_session() as session:
                session.execute(text(ddl))
                session.commit()
            created += 1
            logger.info(f"✓ Created index: {name}")
        except Exception as e:
            logger.warning(f"Failed to create index {name}: {e}")

    if created > 0:
        logger.info(f"Created {created} new index(es)")
    else:
        logger.info("All performance indexes already present")


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("init_db")

    # 初始化配置
    from app.config import get_config

    config = get_config()
    logger.info(f"DB path: {config.db_path}")
    logger.info(f"Strategies dir: {config.strategies_dir}")

    # 初始化数据库
    from app.database import get_db

    db = get_db()
    db.init_db()
    logger.info("Database tables created successfully")

    # 运行 schema migrations (幂等 - 安全重复执行)
    try:
        from sqlalchemy import inspect, text

        with db.get_session() as session:
            inspector = inspect(session.bind)
            table = "kline_daily"
            columns = [col["name"] for col in inspector.get_columns(table)]

            if "turnover_rate" not in columns:
                logger.info("Applying migration: add turnover_rate column...")
                session.execute(text("ALTER TABLE kline_daily ADD COLUMN turnover_rate REAL"))
                session.commit()
                logger.info("✓ Added turnover_rate column")
            else:
                logger.info("✓ turnover_rate column already present")
    except Exception as e:
        logger.warning(f"Migration check failed (non-fatal): {e}")

    # 创建性能索引 (幂等 - IF NOT EXISTS)
    _perform_index_migrations(db, logger)

    # 加载策略到数据库（可选）
    try:
        import uuid
        from datetime import datetime

        from app.core.strategy.loader import StrategyLoader
        from app.models import Strategy
        from app.repositories import StrategyRepository

        loader = StrategyLoader(config.strategies_dir)
        configs = loader.load_all()

        if configs:
            repo = StrategyRepository(db)
            for cfg in configs:
                # Check if strategy already exists by name
                existing = repo.get_by_name(cfg.name)
                if existing:
                    logger.info(f"Strategy '{cfg.name}' already exists, skipping")
                    continue

                import yaml

                strategy = Strategy(
                    id=str(uuid.uuid4()),
                    name=cfg.name,
                    display_name=cfg.display_name,
                    description=cfg.description,
                    category=cfg.category,
                    config=yaml.dump(cfg.raw, allow_unicode=True),
                    is_active=cfg.default_active,
                    priority=cfg.default_priority,
                    created_at=datetime.now().isoformat(),
                    updated_at=datetime.now().isoformat(),
                )
                repo.create(strategy)
                logger.info(f"Loaded strategy: {cfg.name}")

            logger.info(f"Loaded {len(configs)} strategies from {config.strategies_dir}")
        else:
            logger.info("No strategy YAML files found to load")
    except Exception as e:
        logger.warning(f"Strategy loading failed (non-fatal): {e}")

    # 同步沪深 300 指数数据 (用于回测基准对比)
    try:
        from scripts.sync_index_data import _sync_index

        _sync_index(db, "000300", "2018-01-01")
    except Exception as e:
        logger.warning(f"Index data sync failed (non-fatal): {e}")

    logger.info("Database initialization complete!")


if __name__ == "__main__":
    main()
