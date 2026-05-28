# -*- coding: utf-8 -*-
"""
_prepare_state 单元测试

覆盖: set_preparing, set_done, set_failed, get_status, is_preparing, cleanup_old。
纯内存状态管理, 无数据库/网络, 标记为 @pytest.mark.unit。
"""

import time

import pytest

from app.services import _prepare_state as ps


pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _clear():
    """每个测试前后清空内部状态, 保证隔离。"""
    ps._tasks.clear()
    yield
    ps._tasks.clear()


class TestPrepareState:
    def test_set_preparing_and_get_status(self):
        ps.set_preparing("2025-05-20")
        s = ps.get_status("2025-05-20")
        assert s is not None
        assert s["status"] == "preparing"
        assert "started_at" in s

    def test_set_done_preserves_started_at(self):
        ps.set_preparing("2025-05-20")
        before = ps.get_status("2025-05-20")["started_at"]
        ps.set_done("2025-05-20", {"stocks": 100})
        after = ps.get_status("2025-05-20")
        assert after["status"] == "done"
        assert after["started_at"] == before
        assert after["result"] == {"stocks": 100}
        assert after["error"] is None

    def test_set_failed_records_error(self):
        ps.set_preparing("2025-05-21")
        ps.set_failed("2025-05-21", "network error")
        s = ps.get_status("2025-05-21")
        assert s["status"] == "failed"
        assert s["error"] == "network error"

    def test_get_status_unknown_returns_none(self):
        assert ps.get_status("1999-01-01") is None

    def test_is_preparing_true(self):
        ps.set_preparing("2025-05-20")
        assert ps.is_preparing("2025-05-20") is True

    def test_is_preparing_false_after_done(self):
        ps.set_preparing("2025-05-20")
        ps.set_done("2025-05-20", {})
        assert ps.is_preparing("2025-05-20") is False

    def test_is_preparing_unknown(self):
        assert ps.is_preparing("2099-01-01") is False

    def test_cleanup_old(self):
        ps.set_done("2025-01-01", {})
        # 手动把 finished_at 设到很久以前
        ps._tasks["2025-01-01"]["finished_at"] = time.time() - 3600
        ps.set_preparing("2025-05-20")
        ps.cleanup_old(max_age_seconds=300)
        assert ps.get_status("2025-01-01") is None
        assert ps.get_status("2025-05-20") is not None
