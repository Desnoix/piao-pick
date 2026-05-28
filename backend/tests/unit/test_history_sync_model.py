"""
HistorySyncTask 模型单元测试

覆盖: update_progress, mark_started, mark_completed, mark_failed,
get_progress_percent, is_active。
纯模型方法, 无数据库, 标记为 @pytest.mark.unit。
"""

import json

import pytest

from app.models.history_sync_task import HistorySyncTask

pytestmark = pytest.mark.unit


def _make_task(**kwargs) -> HistorySyncTask:
    defaults = {
        "task_id": "test-task-123",
        "start_date": "2025-01-01",
        "end_date": "2025-01-31",
        "total_stocks": 100,
        "completed_stocks": 0,
        "failed_stocks": 0,
        "total_klines": 0,
        "status": "pending",
    }
    defaults.update(kwargs)
    return HistorySyncTask(**defaults)


class TestHistorySyncTask:
    def test_default_factory_task_id(self):
        t = HistorySyncTask(start_date="2025-01-01", end_date="2025-01-31")
        assert t.task_id  # 自动生成 UUID
        assert len(t.task_id) > 0

    def test_update_progress(self):
        t = _make_task()
        t.update_progress(completed=10, failed=2, total_klines=500, current_stock="600519")
        assert t.completed_stocks == 10
        assert t.failed_stocks == 2
        assert t.total_klines == 500
        assert t.current_stock == "600519"

    def test_update_progress_without_stock(self):
        t = _make_task(current_stock="old")
        t.update_progress(completed=5, failed=0, total_klines=200)
        assert t.current_stock == "old"  # 不传 current_stock 不覆盖

    def test_mark_started(self):
        t = _make_task()
        t.mark_started()
        assert t.status == "running"
        assert t.started_at is not None

    def test_mark_completed(self):
        t = _make_task()
        t.mark_started()
        t.mark_completed()
        assert t.status == "completed"
        assert t.completed_at is not None
        assert t.current_stock is None

    def test_mark_failed_first_time(self):
        t = _make_task()
        t.mark_failed("Connection timeout")
        assert t.status == "failed"
        assert t.completed_at is not None
        errors = json.loads(t.error_messages)
        assert errors == ["Connection timeout"]

    def test_mark_failed_appends_errors(self):
        t = _make_task()
        t.mark_failed("Error 1")
        t.mark_failed("Error 2")
        errors = json.loads(t.error_messages)
        assert len(errors) == 2
        assert errors == ["Error 1", "Error 2"]

    def test_get_progress_percent_zero_total(self):
        t = _make_task(total_stocks=0)
        assert t.get_progress_percent() == 0.0

    def test_get_progress_percent_normal(self):
        t = _make_task(total_stocks=100, completed_stocks=50, failed_stocks=10)
        assert t.get_progress_percent() == 60.0

    def test_get_progress_percent_complete(self):
        t = _make_task(total_stocks=50, completed_stocks=48, failed_stocks=2)
        assert t.get_progress_percent() == 100.0

    def test_is_active_pending(self):
        t = _make_task(status="pending")
        assert t.is_active() is True

    def test_is_active_running(self):
        t = _make_task(status="running")
        assert t.is_active() is True

    def test_is_active_completed(self):
        t = _make_task(status="completed")
        assert t.is_active() is False

    def test_is_active_failed(self):
        t = _make_task(status="failed")
        assert t.is_active() is False

    def test_is_active_paused(self):
        t = _make_task(status="paused")
        assert t.is_active() is False
