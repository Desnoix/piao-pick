# -*- coding: utf-8 -*-
"""
Migration: Add turnover_rate column to kline_daily table

问题背景:
  Kline model 新增了 turnover_rate 字段，但 SQLite 表在字段添加前已创建。
  SQLite 不会自动同步 model schema 变更，需要手动 ALTER TABLE。

用法:
    cd backend
    python scripts/migrate_add_turnover_rate.py
"""

import sys
import logging
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("migrate_turnover_rate")

    from app.config import get_config
    config = get_config()
    logger.info(f"DB path: {config.db_path}")

    from app.database import get_db
    db = get_db()

    # Check if column exists
    from sqlalchemy import inspect, text
    with db.get_session() as session:
        inspector = inspect(session.bind)
        table = "kline_daily"
        columns = [col["name"] for col in inspector.get_columns(table)]
        logger.info(f"Current columns in {table}: {columns}")

        if "turnover_rate" in columns:
            logger.info("✓ turnover_rate column already exists, skip migration")
            return

        logger.info("Adding turnover_rate column...")
        session.execute(text(
            "ALTER TABLE kline_daily ADD COLUMN turnover_rate REAL"
        ))
        session.commit()
        logger.info("✓ turnover_rate column added successfully")


if __name__ == "__main__":
    main()
