# -*- coding: utf-8 -*-
"""
SelectionRepository + HistorySyncRepository 集成测试

覆盖: 选股结果 CRUD、按策略/日期/股票查询、历史查询。
标记为 @pytest.mark.integration。
"""

import pytest

from app.models import SelectionResult, HistorySyncTask
from app.repositories.selection_repo import SelectionRepository
from app.repositories.history_sync_repo import HistorySyncRepository


pytestmark = pytest.mark.integration


def _make_result(sid: str = "strat-1", code: str = "600519", date: str = "2025-05-20", **kwargs) -> SelectionResult:
    defaults = {
        "strategy_id": sid,
        "ts_code": code,
        "trade_date": date,
        "rank": 1,
        "composite_score": 0.5,
        "status": "OK",
    }
    defaults.update(kwargs)
    return SelectionResult(**defaults)


class TestSelectionRepoBasic:
    """SelectionRepository 基本查询"""

    def test_upsert_batch_and_get(self, db_manager):
        repo = SelectionRepository(db_manager)
        results = [
            _make_result(code="600519", rank=1, composite_score=2.0),
            _make_result(code="000001", rank=2, composite_score=1.0),
            _make_result(code="300750", rank=3, composite_score=0.5),
        ]
        count = repo.upsert_batch(results)
        assert count == 3

        out = repo.get_by_strategy_date("strat-1", "2025-05-20")
        assert len(out) == 3
        # 按 rank 升序
        assert out[0].ts_code == "600519"
        assert out[2].ts_code == "300750"

    def test_upsert_updates_existing(self, db_manager):
        repo = SelectionRepository(db_manager)
        repo.upsert_batch([_make_result(rank=1, composite_score=1.0)])
        repo.upsert_batch([_make_result(rank=1, composite_score=99.0)])
        out = repo.get_by_strategy_date("strat-1", "2025-05-20")
        assert len(out) == 1
        assert out[0].composite_score == 99.0

    def test_empty_query(self, db_manager):
        repo = SelectionRepository(db_manager)
        assert repo.get_by_strategy_date("none", "2025-05-20") == []


class TestSelectionRepoByCode:
    """按股票查询"""

    def test_get_by_code_date(self, db_manager):
        repo = SelectionRepository(db_manager)
        repo.upsert_batch([
            _make_result(code="600519", date="2025-05-20"),
            _make_result(code="600519", date="2025-05-21"),
            _make_result(code="000001", date="2025-05-20"),
        ])
        result = repo.get_by_code_date("600519", "2025-05-20")
        assert len(result) == 1
        assert result[0].ts_code == "600519"

    def test_get_by_code_date_empty(self, db_manager):
        repo = SelectionRepository(db_manager)
        assert repo.get_by_code_date("999999", "2025-05-20") == []


class TestSelectionRepoLatestDate:
    """最新日期查询"""

    def test_get_latest_date(self, db_manager):
        repo = SelectionRepository(db_manager)
        repo.upsert_batch([
            _make_result(sid="s1", date="2025-05-10"),
            _make_result(sid="s1", date="2025-05-20"),
            _make_result(sid="s1", date="2025-05-15"),
        ])
        latest = repo.get_latest_date("s1")
        assert latest == "2025-05-20"

    def test_get_latest_date_empty(self, db_manager):
        repo = SelectionRepository(db_manager)
        assert repo.get_latest_date("nonexistent") is None


class TestSelectionRepoHistory:
    """历史查询 (按策略+股票)"""

    def test_get_history(self, db_manager):
        repo = SelectionRepository(db_manager)
        repo.upsert_batch([
            _make_result(sid="s1", code="600519", date="2025-05-10", rank=1),
            _make_result(sid="s1", code="600519", date="2025-05-20", rank=2),
            _make_result(sid="s1", code="000001", date="2025-05-20", rank=1),
        ])
        history = repo.get_history("s1", "600519")
        assert len(history) == 2
        # 按 date DESC
        assert history[0].trade_date == "2025-05-20"
        assert history[1].trade_date == "2025-05-10"


class TestSelectionRepoDelete:
    """按策略+日期删除"""

    def test_delete_by_strategy_date(self, db_manager):
        repo = SelectionRepository(db_manager)
        repo.upsert_batch([
            _make_result(sid="s1", code="600519", date="2025-05-20"),
            _make_result(sid="s1", code="000001", date="2025-05-20"),
            _make_result(sid="s1", code="600519", date="2025-05-21"),
        ])
        count = repo.delete_by_strategy_date("s1", "2025-05-20")
        assert count == 2
        out = repo.get_by_strategy_date("s1", "2025-05-20")
        assert len(out) == 0
        out2 = repo.get_by_strategy_date("s1", "2025-05-21")
        assert len(out2) == 1

    def test_delete_by_strategy_date_empty(self, db_manager):
        repo = SelectionRepository(db_manager)
        count = repo.delete_by_strategy_date("none", "2025-05-20")
        assert count == 0


class TestHistorySyncRepo:
    """HistorySyncRepository 测试"""

    def test_create_and_get_task(self, db_manager):
        repo = HistorySyncRepository(db_manager)
        task = repo.create_task(HistorySyncTask(
            task_id="task-1",
            start_date="2025-01-01",
            end_date="2025-01-31",
        ))
        assert task.task_id == "task-1"
        fetched = repo.get_task("task-1")
        assert fetched is not None
        assert fetched.start_date == "2025-01-01"
        assert fetched.status == "pending"

    def test_get_task_not_found(self, db_manager):
        repo = HistorySyncRepository(db_manager)
        assert repo.get_task("nonexistent") is None

    def test_list_tasks(self, db_manager):
        repo = HistorySyncRepository(db_manager)
        repo.create_task(HistorySyncTask(task_id="t1", start_date="2025-01-01", end_date="2025-01-15"))
        repo.create_task(HistorySyncTask(task_id="t2", start_date="2025-02-01", end_date="2025-02-15"))
        tasks = repo.list_tasks(limit=10)
        assert len(tasks) >= 2

    def test_update_task(self, db_manager):
        repo = HistorySyncRepository(db_manager)
        task = repo.create_task(HistorySyncTask(
            task_id="upd-1", start_date="2025-01-01", end_date="2025-01-31",
        ))
        task.mark_started()
        repo.update_task(task)
        fetched = repo.get_task("upd-1")
        assert fetched.status == "running"

    def test_get_latest_task(self, db_manager):
        repo = HistorySyncRepository(db_manager)
        repo.create_task(HistorySyncTask(task_id="lt-1", start_date="2025-01-01", end_date="2025-01-15"))
        repo.create_task(HistorySyncTask(task_id="lt-2", start_date="2025-02-01", end_date="2025-02-15"))
        latest = repo.get_latest_task()
        assert latest is not None

    def test_count_tasks(self, db_manager):
        repo = HistorySyncRepository(db_manager)
        repo.create_task(HistorySyncTask(task_id="ct-1", start_date="2025-01-01", end_date="2025-01-15"))
        count = repo.count_tasks()
        assert count >= 1
        count_pending = repo.count_tasks(status="pending")
        assert count_pending >= 1

    def test_get_active_task_none(self, db_manager):
        repo = HistorySyncRepository(db_manager)
        active = repo.get_active_task()
        assert active is None  # 无任务时返回 None

