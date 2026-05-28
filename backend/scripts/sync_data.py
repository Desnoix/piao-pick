"""
手动数据同步脚本

触发数据同步流程，从数据源获取最新行情数据写入数据库。

用法:
    cd backend
    python scripts/sync_data.py                    # 同步最新交易日所有股票
    python scripts/sync_data.py --date 2024-01-15  # 同步指定日期
    python scripts/sync_data.py --codes 000001.SZ,600519.SH  # 同步指定股票
"""

import argparse
import logging
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))


def main():
    parser = argparse.ArgumentParser(description="手动数据同步")
    parser.add_argument("--date", type=str, default=None, help="交易日期 YYYY-MM-DD")
    parser.add_argument("--codes", type=str, default=None, help="股票代码列表，逗号分隔")
    parser.add_argument("--verbose", "-v", action="store_true", help="详细输出")
    args = parser.parse_args()

    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    logger = logging.getLogger("sync_data")

    # 初始化配置
    from app.config import get_config

    config = get_config()
    logger.info(f"DB path: {config.db_path}")

    # 解析股票代码
    stock_codes = None
    if args.codes:
        stock_codes = [c.strip() for c in args.codes.split(",") if c.strip()]
        logger.info(f"Target stocks: {stock_codes}")

    # 执行同步
    from app.services.data_service import DataSyncService

    service = DataSyncService()
    result = service.sync_daily_data(
        trade_date=args.date,
        stock_codes=stock_codes,
    )

    # 输出结果
    logger.info("=" * 50)
    logger.info(f"Trade date: {result.get('trade_date', 'N/A')}")
    logger.info(f"Synced: {result.get('synced', 0)}")
    logger.info(f"Failed: {result.get('failed', 0)}")

    errors = result.get("errors", [])
    if errors:
        logger.warning(f"Errors ({len(errors)}):")
        for err in errors[:10]:
            logger.warning(f"  - {err}")
        if len(errors) > 10:
            logger.warning(f"  ... and {len(errors) - 10} more")


if __name__ == "__main__":
    main()
