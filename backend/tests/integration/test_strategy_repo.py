"""
StrategyRepository 集成测试

覆盖: CRUD 操作、按名称/ID 查询、激活/停用状态切换、数据库隔离验证。
使用真实 SQLite 临时文件, 标记为 @pytest.mark.integration。
"""

import uuid
from datetime import datetime

import pytest

from app.models import Strategy
from app.repositories.strategy_repo import StrategyRepository

pytestmark = pytest.mark.integration


def _make_strategy(
    name: str = "test_strat",
    display_name: str = "测试策略",
    is_active: bool = True,
    priority: int = 50,
    config: str = "name: test\nfactors: []\n",
) -> Strategy:
    """辅助: 构造一个 Strategy 实例 (id 自动生成)。"""
    now = datetime.now().isoformat()
    return Strategy(
        id=uuid.uuid4().hex,
        name=name,
        display_name=display_name,
        description="集成测试自动生成",
        category="value",
        config=config,
        is_active=is_active,
        priority=priority,
        created_at=now,
        updated_at=now,
    )


class TestStrategyRepoCRUD:
    """CRUD 基础操作"""

    def test_create_and_get_by_id(self, db_manager):
        repo = StrategyRepository(db_manager)
        s = _make_strategy(name="create_test")
        repo.create(s)
        fetched = repo.get_by_id(s.id)
        assert fetched is not None
        assert fetched.name == "create_test"
        assert fetched.id == s.id

    def test_get_all_returns_created(self, db_manager):
        repo = StrategyRepository(db_manager)
        for i in range(3):
            repo.create(_make_strategy(name=f"list_{i}", priority=i * 10))
        all_strats = repo.get_all()
        assert len(all_strats) >= 3

    def test_get_by_name(self, db_manager):
        repo = StrategyRepository(db_manager)
        s = _make_strategy(name="unique_name_xyz")
        repo.create(s)
        found = repo.get_by_name("unique_name_xyz")
        assert found is not None
        assert found.display_name == "测试策略"

    def test_get_nonexistent_returns_none(self, db_manager):
        repo = StrategyRepository(db_manager)
        assert repo.get_by_id("nonexistent_id_abc") is None
        assert repo.get_by_name("nonexistent_name_xyz") is None

    def test_update_strategy(self, db_manager):
        repo = StrategyRepository(db_manager)
        s = _make_strategy(name="update_test")
        repo.create(s)
        s.display_name = "更新后的名称"
        repo.update(s)
        fetched = repo.get_by_id(s.id)
        assert fetched.display_name == "更新后的名称"

    def test_delete_strategy(self, db_manager):
        repo = StrategyRepository(db_manager)
        s = _make_strategy(name="delete_test")
        repo.create(s)
        deleted = repo.delete(s.id)
        assert deleted is True
        assert repo.get_by_id(s.id) is None

    def test_delete_nonexistent_returns_false(self, db_manager):
        repo = StrategyRepository(db_manager)
        assert repo.delete("fake_id") is False


class TestStrategyRepoActivation:
    """激活状态管理"""

    def test_get_active_filters_inactive(self, db_manager):
        repo = StrategyRepository(db_manager)
        active = _make_strategy(name="active_one", is_active=True, priority=1)
        inactive = _make_strategy(name="inactive_one", is_active=False, priority=2)
        repo.create(active)
        repo.create(inactive)
        actives = repo.get_active()
        names = [s.name for s in actives]
        assert "active_one" in names
        assert "inactive_one" not in names

    def test_set_active_true(self, db_manager):
        repo = StrategyRepository(db_manager)
        s = _make_strategy(name="toggle_test", is_active=False)
        repo.create(s)
        result = repo.set_active(s.id, True)
        assert result is True
        fetched = repo.get_by_id(s.id)
        assert fetched.is_active is True

    def test_set_active_nonexistent_returns_false(self, db_manager):
        repo = StrategyRepository(db_manager)
        assert repo.set_active("fake_id", True) is False


class TestStrategyRepoIsolation:
    """数据库隔离验证: 不同测试函数使用不同数据库文件"""

    def test_isolation_write(self, db_manager):
        repo = StrategyRepository(db_manager)
        repo.create(_make_strategy(name="isolation_a"))
        all_strats = repo.get_all()
        names = [s.name for s in all_strats]
        assert "isolation_a" in names
        assert "isolation_b" not in names, "isolation_b 应在另一个测试中, 这里不应存在"

    def test_isolation_verify_empty(self, db_manager):
        repo = StrategyRepository(db_manager)
        all_strats = repo.get_all()
        names = [s.name for s in all_strats]
        assert "isolation_a" not in names, "isolation_a 不应泄漏到此测试中"


class TestStrategyRepoOrdering:
    """优先级排序"""

    def test_get_all_sorted_by_priority(self, db_manager):
        repo = StrategyRepository(db_manager)
        repo.create(_make_strategy(name="low_prio", priority=100))
        repo.create(_make_strategy(name="high_prio", priority=1))
        repo.create(_make_strategy(name="mid_prio", priority=50))
        all_strats = repo.get_all()
        names = [s.name for s in all_strats]
        assert names.index("high_prio") < names.index("mid_prio")
        assert names.index("mid_prio") < names.index("low_prio")


class TestDatabaseExecuteWithRetry:
    """DatabaseManager.execute_with_retry 锁重试机制"""

    def test_successful_function_runs(self, db_manager):
        def ok_func():
            return 42

        result = db_manager.execute_with_retry(ok_func)
        assert result == 42

    def test_non_lock_error_propagates(self, db_manager):
        from sqlalchemy.exc import OperationalError

        def fail_func():
            # 模拟非锁错误
            raise OperationalError("stmt", {}, Exception("not a lock"))

        with pytest.raises(OperationalError):
            db_manager.execute_with_retry(fail_func)

    def test_with_retry_decorator_works(self, db_manager):
        @db_manager.with_retry(base_delay=0.01, max_retries=0)
        def decorated(a, b):
            return a + b

        assert decorated(1, 2) == 3
