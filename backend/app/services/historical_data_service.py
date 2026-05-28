"""历史数据同步服务

支持批量拉取历史K线数据，带断点续传和限速控制。
"""

import logging
import time
from concurrent.futures import ThreadPoolExecutor

import pandas as pd

from app.database import get_db
from app.models.history_sync_task import HistorySyncTask
from app.models.kline import Kline
from app.repositories.history_sync_repo import HistorySyncRepository
from app.repositories.stock_repo import StockRepository
from app.services.cache import get_cache_manager
from data_provider import DataFetcherManager, DataFetchError

logger = logging.getLogger(__name__)


class HistoricalDataService:
    """历史数据同步服务"""

    _fetcher_manager: DataFetcherManager | None = None

    def __init__(self):
        self.db = get_db()
        self.stock_repo = StockRepository(self.db)
        self.sync_repo = HistorySyncRepository(self.db)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._current_future = None

    @classmethod
    def _get_fetcher_manager(cls) -> DataFetcherManager:
        """Lazily create and cache DataFetcherManager singleton.

        Creating a new DataFetcherManager per stock is expensive (it initializes
        fetchers). Cache at class level so all HistoricalDataService instances
        share the same manager with its configured failover chain.
        """
        if cls._fetcher_manager is None:
            cls._fetcher_manager = DataFetcherManager()
        return cls._fetcher_manager

    def start_sync(
        self,
        start_date: str,
        end_date: str,
        adjust_type: str = "qfq",
        stock_codes: list[str] | None = None,
        use_existing_task: bool = False,
    ) -> HistorySyncTask:
        """
        启动历史数据同步任务（异步执行）

        Args:
            start_date: 开始日期 YYYY-MM-DD
            end_date: 结束日期 YYYY-MM-DD
            adjust_type: 复权类型 (qfq/hfq/null)
            stock_codes: 指定股票代码列表，None 表示全市场
            use_existing_task: 如果存在活跃任务是否复用

        Returns:
            任务记录对象
        """
        # 检查是否已有活跃任务
        active_task = self.sync_repo.get_active_task()
        if active_task and not use_existing_task:
            logger.warning(f"Active task already running: {active_task.task_id}")
            return active_task

        # 创建新任务
        task = HistorySyncTask(
            start_date=start_date,
            end_date=end_date,
            adjust_type=adjust_type,
        )

        # 获取待同步的股票列表
        if stock_codes is None:
            stock_codes = self.stock_repo.get_all_stock_codes()

        task.total_stocks = len(stock_codes)
        self.sync_repo.create_task(task)

        logger.info(f"Starting history sync: {task.task_id}, {start_date} to {end_date}, {len(stock_codes)} stocks")

        # 提交到后台执行
        self._current_future = self._executor.submit(
            self._sync_worker,
            task.task_id,
            stock_codes,
        )

        return task

    def _sync_worker(self, task_id: str, stock_codes: list[str]):
        """后台工作线程：执行历史数据同步"""
        task = self.sync_repo.get_task(task_id)
        if not task:
            logger.error(f"Task not found: {task_id}")
            return

        task.mark_started()
        self.sync_repo.update_task(task)

        completed = 0
        failed = 0
        total_klines = 0
        errors = []

        logger.info(f"[{task_id}] Worker started, processing {len(stock_codes)} stocks")

        for idx, ts_code in enumerate(stock_codes, 1):
            try:
                # 更新当前正在处理的股票
                task.current_stock = ts_code
                self.sync_repo.update_task(task)

                # 拉取历史数据
                klines_count = self._fetch_and_save_history(
                    ts_code=ts_code,
                    start_date=task.start_date,
                    end_date=task.end_date,
                    adjust_type=task.adjust_type,
                )

                total_klines += klines_count
                completed += 1

                # 每处理 10 只股票记录一次进度
                if idx % 10 == 0:
                    task.update_progress(completed, failed, total_klines)
                    self.sync_repo.update_task(task)
                    logger.info(
                        f"[{task_id}] Progress: {idx}/{len(stock_codes)} "
                        f"({task.get_progress_percent():.1f}%), "
                        f"completed={completed}, failed={failed}, "
                        f"klines={total_klines}"
                    )

                # 限速：每次请求后休眠
                time.sleep(0.5)  # 500ms

            except Exception as e:
                failed += 1
                error_msg = f"{ts_code}: {str(e)}"
                errors.append(error_msg)
                logger.error(f"[{task_id}] Failed to sync {ts_code}: {e}")

                # 限制错误列表大小
                if len(errors) > 100:
                    errors = errors[-100:]

        # 完成或失败
        if len(errors) > 0:
            task.error_messages = str(errors)

        task.update_progress(completed, failed, total_klines)

        if failed == 0:
            task.mark_completed()
            logger.info(f"[{task_id}] Completed successfully: {completed} stocks, {total_klines} klines")
        else:
            task.mark_failed(f"{failed} stocks failed")
            logger.warning(f"[{task_id}] Completed with errors: {completed} ok, {failed} failed, {total_klines} klines")

        self.sync_repo.update_task(task)

    def _fetch_and_save_history(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        adjust_type: str,
    ) -> int:
        """
        拉取并保存单只股票的历史数据

        Uses DataFetcherManager's automatic failover chain
        (Baostock P0 → Akshare P1 → Tushare P2) instead of raw akshare calls.

        Returns:
            成功写入的K线数量
        """
        try:
            manager = self._get_fetcher_manager()
            df, source_name = manager.get_daily_data(
                ts_code,
                start_date=start_date,
                end_date=end_date,
            )

            if df is None or df.empty:
                logger.debug(f"{ts_code}: No data returned from any source")
                return 0

            # df already has standardized columns from DataFetcherManager:
            # code, date, open, high, low, close, volume, amount,
            # pct_chg, ma5, ma10, ma20, volume_ratio
            klines = self._dataframe_to_klines(df, ts_code, source=source_name)
            saved_count = self.stock_repo.upsert_kline_batch(klines)

            # 失效缓存
            if saved_count > 0:
                cm = get_cache_manager()
                cm.invalidate_stock_cache(ts_code)

            return saved_count

        except DataFetchError as e:
            logger.warning(f"{ts_code}: All data sources failed: {e}")
            raise

    def _dataframe_to_klines(
        self,
        df: pd.DataFrame,
        ts_code: str,
        source: str,
    ) -> list[Kline]:
        """将标准化 DataFrame 转换为 Kline 对象列表

        Expects DataFetcherManager output columns:
        code, date, open, high, low, close, volume, amount,
        pct_chg, ma5, ma10, ma20, volume_ratio
        """
        klines = []

        for _, row in df.iterrows():
            try:
                trade_date = row["date"].strftime("%Y-%m-%d")

                kline = Kline(
                    ts_code=ts_code,
                    trade_date=trade_date,
                    open=float(row["open"]) if pd.notna(row["open"]) else None,
                    high=float(row["high"]) if pd.notna(row["high"]) else None,
                    low=float(row["low"]) if pd.notna(row["low"]) else None,
                    close=float(row["close"]) if pd.notna(row["close"]) else None,
                    volume=int(row["volume"]) if pd.notna(row["volume"]) else None,
                    amount=float(row["amount"]) if "amount" in row and pd.notna(row["amount"]) else None,
                    close_adj=float(row["close"]) if pd.notna(row["close"]) else None,  # 已复权
                    ma5=float(row["ma5"]) if "ma5" in row and pd.notna(row["ma5"]) else None,
                    ma10=float(row["ma10"]) if "ma10" in row and pd.notna(row["ma10"]) else None,
                    ma20=float(row["ma20"]) if "ma20" in row and pd.notna(row["ma20"]) else None,
                    volume_ratio=float(row["volume_ratio"]) if "volume_ratio" in row and pd.notna(row["volume_ratio"]) else None,
                    data_source=source,
                )
                klines.append(kline)
            except (ValueError, TypeError) as e:
                logger.debug(f"{ts_code} {row.get('date', 'unknown')}: Invalid data row - {e}")
                continue

        return klines

    def get_task_status(self, task_id: str | None = None) -> dict | None:
        """获取任务状态"""
        if task_id:
            task = self.sync_repo.get_task(task_id)
        else:
            task = self.sync_repo.get_latest_task()

        if not task:
            return None

        return {
            "task_id": task.task_id,
            "status": task.status,
            "start_date": task.start_date,
            "end_date": task.end_date,
            "progress": {
                "total": task.total_stocks,
                "completed": task.completed_stocks,
                "failed": task.failed_stocks,
                "total_klines": task.total_klines,
                "percent": task.get_progress_percent(),
                "current_stock": task.current_stock,
            },
            "created_at": task.created_at,
            "started_at": task.started_at,
            "completed_at": task.completed_at,
            "error_messages": task.error_messages,
        }

    def list_tasks(self, limit: int = 10) -> list[dict]:
        """列出历史同步任务"""
        tasks = self.sync_repo.list_tasks(limit=limit)
        return [self.get_task_status(task.task_id) for task in tasks]
