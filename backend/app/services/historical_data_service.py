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

logger = logging.getLogger(__name__)


class HistoricalDataService:
    """历史数据同步服务"""

    def __init__(self):
        self.db = get_db()
        self.stock_repo = StockRepository(self.db)
        self.sync_repo = HistorySyncRepository(self.db)
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._current_future = None

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

        Returns:
            成功写入的K线数量
        """
        try:
            import akshare as ak

            # 尝试东方财富接口
            df = ak.stock_zh_a_hist(
                symbol=ts_code,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
                adjust=adjust_type,
            )

            if df is None or df.empty:
                logger.debug(f"{ts_code}: No data returned")
                return 0

            # 标准化列名
            df = self._normalize_columns(df, ts_code)

            # 保存到数据库
            klines = self._dataframe_to_klines(df, ts_code, source="eastmoney")
            saved_count = self.stock_repo.upsert_kline_batch(klines)

            # 失效缓存
            if saved_count > 0:
                cm = get_cache_manager()
                cm.invalidate_stock_cache(ts_code)

            return saved_count

        except Exception as e:
            # 东方财富失败，尝试新浪
            logger.debug(f"{ts_code}: Eastmoney failed ({e}), trying Sina")
            return self._fetch_from_sina(ts_code, start_date, end_date, adjust_type)

    def _fetch_from_sina(
        self,
        ts_code: str,
        start_date: str,
        end_date: str,
        adjust_type: str,
    ) -> int:
        """备用数据源：新浪财经"""
        try:
            import akshare as ak

            df = ak.stock_zh_a_daily(
                symbol=f"sh{ts_code}" if ts_code.startswith("6") else f"sz{ts_code}",
                adjust=adjust_type,
            )

            if df is None or df.empty:
                return 0

            # 过滤日期范围
            df["date"] = pd.to_datetime(df["date"])
            start_dt = pd.to_datetime(start_date)
            end_dt = pd.to_datetime(end_date)
            df = df[(df["date"] >= start_dt) & (df["date"] <= end_dt)]

            # 标准化
            df = self._normalize_columns(df, ts_code, source="sina")

            # 保存
            klines = self._dataframe_to_klines(df, ts_code, source="sina")
            saved_count = self.stock_repo.upsert_kline_batch(klines)

            return saved_count

        except Exception as e:
            logger.warning(f"{ts_code}: Both sources failed, Sina error: {e}")
            raise

    def _normalize_columns(self, df: pd.DataFrame, ts_code: str, source: str = "eastmoney") -> pd.DataFrame:
        """标准化 DataFrame 列名"""
        df = df.copy()

        if source == "eastmoney":
            # 东方财富列名映射
            column_mapping = {
                "日期": "date",
                "开盘": "open",
                "收盘": "close",
                "最高": "high",
                "最低": "low",
                "成交量": "volume",
                "成交额": "amount",
                "振幅": "amplitude",
                "涨跌幅": "pct_change",
                "涨跌额": "change",
                "换手率": "turnover",
            }
            df = df.rename(columns=column_mapping)

        elif source == "sina":
            # 新浪列名已经是英文/拼音，直接映射
            column_mapping = {
                "date": "date",
                "open": "open",
                "close": "close",
                "high": "high",
                "low": "low",
                "volume": "volume",
            }
            df = df.rename(columns=column_mapping)

        # 确保必需的列存在
        required_cols = ["date", "open", "close", "high", "low", "volume"]
        for col in required_cols:
            if col not in df.columns:
                df[col] = None

        # 转换日期格式
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")

        # 选择需要的列
        keep_cols = ["date", "open", "high", "low", "close", "volume"]
        optional_cols = ["amount", "pct_change", "turnover"]
        for col in optional_cols:
            if col in df.columns:
                keep_cols.append(col)

        df = df[keep_cols]

        return df

    def _dataframe_to_klines(
        self,
        df: pd.DataFrame,
        ts_code: str,
        source: str,
    ) -> list[Kline]:
        """将 DataFrame 转换为 Kline 对象列表"""
        klines = []

        for _, row in df.iterrows():
            try:
                kline = Kline(
                    ts_code=ts_code,
                    trade_date=row["date"],
                    open=float(row["open"]) if pd.notna(row["open"]) else None,
                    high=float(row["high"]) if pd.notna(row["high"]) else None,
                    low=float(row["low"]) if pd.notna(row["low"]) else None,
                    close=float(row["close"]) if pd.notna(row["close"]) else None,
                    volume=int(row["volume"]) if pd.notna(row["volume"]) else None,
                    amount=float(row["amount"]) if "amount" in row and pd.notna(row["amount"]) else None,
                    close_adj=float(row["close"]) if pd.notna(row["close"]) else None,  # 已复权
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
