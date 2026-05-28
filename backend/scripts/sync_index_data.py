"""
沪深 300 指数数据同步脚本

从 AKShare 拉取沪深 300 (000300) 日线数据，存入 kline_daily 表。
幂等设计 — 可安全重复执行。

用法:
    cd backend
    python scripts/sync_index_data.py
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

logger = logging.getLogger("sync_index_data")

INDEX_CODE = "000300"  # 沪深 300 在 kline_daily.ts_code 中的值
DEFAULT_START = "2018-01-01"


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    from app.config import get_config
    from app.database import get_db

    get_config()  # noqa: F841 - ensure config is valid
    db = get_db()
    db.init_db()

    _sync_index(db, INDEX_CODE, DEFAULT_START)


def _sync_index(db, index_code: str, start_date: str):
    """拉取指数历史数据并写入 kline_daily (通过 DataFetcherManager, 支持故障转移)"""
    from sqlmodel import select

    from app.models.kline import Kline
    from data_provider.base import DataFetcherManager, DataFetchError

    # 查询数据库中已有的最新日期，实现断点续传
    with db.get_session() as session:
        max_date = session.exec(
            select(Kline.trade_date).where(Kline.ts_code == index_code).order_by(Kline.trade_date.desc()).limit(1)
        ).first()

    effective_start = start_date
    if max_date:
        # 从已有数据次日开始续传
        next_day = (datetime.strptime(max_date, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        effective_start = next_day
        logger.info(f"数据库中已有 {index_code} 数据至 {max_date}，从 {next_day} 续传")
    else:
        logger.info(f"数据库中无 {index_code} 数据，从 {start_date} 全量拉取")

    end_date = datetime.now().strftime("%Y-%m-%d")

    if effective_start >= end_date:
        logger.info("数据已是最新，无需同步")
        return

    logger.info(f"拉取 {index_code}: {effective_start} ~ {end_date}")

    manager = DataFetcherManager()
    try:
        df, source = manager.get_index_daily_data(index_code, effective_start, end_date)
    except DataFetchError as e:
        logger.error(f"所有数据源均失败: {e}")
        return

    if df is None or df.empty:
        logger.warning("未返回数据")
        return

    logger.info(f"数据源: {source}, 返回 {len(df)} 行")

    # Detect column names (akshare uses Chinese, tushare uses English)
    date_col = "日期" if "日期" in df.columns else "trade_date"
    open_col = "开盘" if "开盘" in df.columns else "open"
    high_col = "最高" if "最高" in df.columns else "high"
    low_col = "最低" if "最低" in df.columns else "low"
    close_col = "收盘" if "收盘" in df.columns else "close"
    vol_col = "成交量" if "成交量" in df.columns else "vol"
    amount_col = "成交额" if "成交额" in df.columns else "amount"

    # 转换并写入
    klines = []
    for _, row in df.iterrows():
        trade_date = str(row[date_col])
        # Normalize Tushare trade_date format (YYYYMMDD -> YYYY-MM-DD)
        if len(trade_date) == 8 and trade_date.isdigit():
            trade_date = f"{trade_date[:4]}-{trade_date[4:6]}-{trade_date[6:8]}"
        try:
            volume_raw = row[vol_col]
            # Tushare vol is in lots (手), convert to shares
            volume = int(volume_raw) if source != "TushareFetcher" else int(float(volume_raw) * 100)
            kline = Kline(
                ts_code=index_code,
                trade_date=trade_date,
                open=float(row[open_col]),
                high=float(row[high_col]),
                low=float(row[low_col]),
                close=float(row[close_col]),
                volume=volume,
                amount=float(row.get(amount_col, 0)),
                close_adj=float(row[close_col]),  # 指数无复权，close_adj = close
                data_source=f"{source.lower()}_index",
            )
            klines.append(kline)
        except (ValueError, TypeError) as e:
            logger.debug(f"跳过无效行 {trade_date}: {e}")

    # 批量 upsert
    saved = 0
    with db.get_session() as session:
        for k in klines:
            existing = session.get(Kline, (k.ts_code, k.trade_date))
            if existing:
                session.merge(k)
            else:
                session.add(k)
            saved += 1
        session.commit()

    logger.info(f"写入 {saved} 条 {index_code} K线数据")


if __name__ == "__main__":
    main()
