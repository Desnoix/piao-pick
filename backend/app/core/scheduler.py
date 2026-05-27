# -*- coding: utf-8 -*-
"""
定时任务调度器

使用 APScheduler 设置每日自动选股任务。
"""

import logging
from typing import Optional

from apscheduler.schedulers.background import BackgroundScheduler

from app.config import get_config

logger = logging.getLogger(__name__)


class SelectionScheduler:
    """
    选股任务调度器。

    根据配置文件中的 schedule_enabled / schedule_time 设置定时任务：
    - 每日定时执行数据同步
    - 每日定时执行选股（所有激活策略）
    """

    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.config = get_config()
        self._started = False

    def start(self):
        """启动调度器"""
        if not self.config.schedule_enabled:
            logger.info("Scheduler disabled by config (SCHEDULE_ENABLED=false)")
            return

        if self._started:
            logger.warning("Scheduler already started")
            return

        # 解析调度时间
        hour, minute = self._parse_schedule_time()

        # 数据同步任务（选股前30分钟执行）
        sync_hour = hour
        sync_minute = max(0, minute - 30)
        if sync_minute < 0:
            sync_hour = max(0, hour - 1)
            sync_minute = 60 + sync_minute

        self.scheduler.add_job(
            self._sync_data_task,
            "cron",
            hour=sync_hour,
            minute=sync_minute,
            id="daily_data_sync",
            replace_existing=True,
        )

        # 选股任务
        self.scheduler.add_job(
            self._selection_task,
            "cron",
            hour=hour,
            minute=minute,
            id="daily_selection",
            replace_existing=True,
        )

        self.scheduler.start()
        self._started = True
        logger.info(
            f"Scheduler started: data sync at {sync_hour:02d}:{sync_minute:02d}, "
            f"selection at {hour:02d}:{minute:02d}"
        )

    def stop(self):
        """停止调度器"""
        if self._started:
            self.scheduler.shutdown(wait=False)
            self._started = False
            logger.info("Scheduler stopped")

    def _parse_schedule_time(self) -> tuple[int, int]:
        """解析调度时间 HH:MM"""
        try:
            parts = self.config.schedule_time.split(":")
            hour = int(parts[0])
            minute = int(parts[1]) if len(parts) > 1 else 0
            return hour, minute
        except (ValueError, IndexError):
            logger.warning(
                f"Invalid SCHEDULE_TIME '{self.config.schedule_time}', using 15:30"
            )
            return 15, 30

    def _sync_data_task(self):
        """每日数据同步任务"""
        logger.info("Scheduled task: data sync started")
        try:
            from app.services.data_service import DataSyncService

            service = DataSyncService()
            result = service.sync_daily_data()
            logger.info(f"Scheduled data sync completed: {result}")
        except Exception as e:
            logger.error(f"Scheduled data sync failed: {e}", exc_info=True)

    def _selection_task(self):
        """每日选股任务"""
        logger.info("Scheduled task: selection started")
        try:
            from app.core.pipeline import SelectionPipeline

            pipeline = SelectionPipeline()
            result = pipeline.run()
            logger.info(f"Scheduled selection completed: {result}")
        except NotImplementedError:
            logger.info("SelectionPipeline not yet implemented, skipping")
        except Exception as e:
            logger.error(f"Scheduled selection failed: {e}", exc_info=True)
