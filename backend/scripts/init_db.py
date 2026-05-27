# -*- coding: utf-8 -*-
"""
数据库初始化脚本

创建所有数据库表和初始数据。

用法:
    cd backend
    python scripts/init_db.py
"""

import sys
import logging
from pathlib import Path

# 确保项目根目录在 sys.path 中
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))


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
                session.execute(text(
                    "ALTER TABLE kline_daily ADD COLUMN turnover_rate REAL"
                ))
                session.commit()
                logger.info("✓ Added turnover_rate column")
            else:
                logger.info("✓ turnover_rate column already present")
    except Exception as e:
        logger.warning(f"Migration check failed (non-fatal): {e}")

    # 加载策略到数据库（可选）
    try:
        from app.core.strategy.loader import StrategyLoader
        from app.repositories import StrategyRepository
        from app.models import Strategy
        import uuid
        from datetime import datetime

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

    logger.info("Database initialization complete!")


if __name__ == "__main__":
    main()
