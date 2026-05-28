"""数据库管理模块 — DatabaseManager 单例 + 锁重试机制。"""

import logging
import os
import time
from collections.abc import Callable
from typing import Optional, TypeVar

from sqlalchemy import event
from sqlalchemy.exc import OperationalError
from sqlmodel import Session, SQLModel, create_engine

logger = logging.getLogger(__name__)

T = TypeVar("T")

# 重试相关常量 (模块级, 避免类作用域在方法签名默认参数中不可见)
_DEFAULT_BASE_DELAY = 0.1  # 首次退避 100ms
_DEFAULT_MAX_RETRIES = 3  # 最多重试 3 次
_DEFAULT_BUSY_TIMEOUT_SEC = 5.0  # SQLite 引擎层等待 5s


class DatabaseManager:
    """SQLite 连接管理器 (单例)。

    职责:
    - 创建引擎并启用 WAL 模式 + busy_timeout
    - 提供 get_session() 会话工厂
    - 提供 execute_with_retry() 对写操作的指数退避重试
    """

    _instance: Optional["DatabaseManager"] = None

    def __init__(self, db_path: str = "data/piao_pick.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        # connect_args 仅在 SQLite 生效, 设置 timeout (busy_timeout) 让引擎层自动等待锁
        self.engine = create_engine(
            f"sqlite:///{db_path}",
            echo=False,
            connect_args={
                "check_same_thread": False,
                "timeout": _DEFAULT_BUSY_TIMEOUT_SEC,
            },
            pool_pre_ping=True,
            pool_recycle=1800,
        )
        self._register_sqlite_pragmas()
        self._init_tables()

    def _register_sqlite_pragmas(self):
        """通过 SQLAlchemy 引擎事件在每次物理连接建立时执行 PRAGMA。

        为什么用 event 而不是单次执行: SQLite 连接池可能复用旧连接,
        注册到 'connect' 事件保证每个连接 (包括重建的) 都拿到一致的 PRAGMA。
        """
        engine = self.engine

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            # WAL: 读写并发 (读者不阻塞写者)
            cursor.execute("PRAGMA journal_mode=WAL")
            # synchronous=NORMAL 在 WAL 模式下安全, 写入性能提升 2-3x
            cursor.execute("PRAGMA synchronous=NORMAL")
            # 8MB 用户空间缓存 (默认 2MB)
            cursor.execute("PRAGMA cache_size=-8000")
            # 30s 锁等待 (覆盖 connect_args timeout, PRAGMA 级别更可靠)
            cursor.execute("PRAGMA busy_timeout=30000")
            cursor.close()

        logger.info(f"SQLite pragmas registered (WAL + NORMAL) for: {self.db_path}")

    def _init_tables(self):
        from app.models import Factor, Kline, SelectionResult, StockInfo, Strategy  # noqa: F401

        SQLModel.metadata.create_all(self.engine)
        logger.info(f"Database initialized: {self.db_path}")

    def get_session(self) -> Session:
        return Session(self.engine)

    def init_db(self):
        from app.models import Factor, Kline, SelectionResult, StockInfo, Strategy  # noqa: F401

        SQLModel.metadata.create_all(self.engine)
        logger.info(f"Database tables created: {self.db_path}")

    # ------------------------------------------------------------------
    # Lock-retry helper
    # ------------------------------------------------------------------
    def execute_with_retry(
        self,
        func: Callable[[], T],
        *,
        base_delay: float = _DEFAULT_BASE_DELAY,
        max_retries: int = _DEFAULT_MAX_RETRIES,
        op_name: str = "",
    ) -> T:
        """执行一个可能触发 SQLite 锁的函数, 失败时指数退避重试。

        Args:
            func: 无参可调用对象 (lambda 或 bound method), 内部完成全部写操作。
            base_delay: 首次退避秒数, 之后每次翻倍 (0.1 -> 0.2 -> 0.4)。
            max_retries: 最大重试次数 (不含首次执行, 0 表示不重试)。
            op_name: 用于日志的操作名, 缺省取 func 的字符串表示。

        Returns:
            func 的返回值。

        Raises:
            OperationalError: 重试耗尽后仍锁。
        """
        label = op_name or getattr(func, "__name__", str(func))
        last_exc: BaseException | None = None
        delay = base_delay

        for attempt in range(max_retries + 1):
            try:
                return func()
            except OperationalError as e:
                last_exc = e
                msg = str(e).lower()
                # 仅对锁相关错误重试, 其他 OperationalError (如语法) 直接抛
                if "locked" not in msg and "busy" not in msg:
                    raise
                if attempt == max_retries:
                    logger.error(f"[DB] {label} 重试 {max_retries} 次仍失败: {e}")
                    raise
                logger.warning(f"[DB] {label} 触发锁, {delay:.2f}s 后重试 (attempt {attempt + 1}/{max_retries}): {e}")
                time.sleep(delay)
                delay *= 2

        # 不可达, 显式 raise 满足类型检查
        raise last_exc  # type: ignore[misc]

    def with_retry(
        self,
        base_delay: float = _DEFAULT_BASE_DELAY,
        max_retries: int = _DEFAULT_MAX_RETRIES,
    ):
        """装饰器工厂: 将 execute_with_retry 包装到方法上。

        用法:
            @db.with_retry(base_delay=0.2, max_retries=5)
            def heavy_write(self):
                with self.db.get_session() as s:
                    ...
                    s.commit()
        """

        def decorator(func: Callable) -> Callable:
            def wrapper(*args, **kwargs):

                def bound():
                    return func(*args, **kwargs)

                return self.execute_with_retry(
                    bound,
                    base_delay=base_delay,
                    max_retries=max_retries,
                    op_name=func.__name__,
                )

            wrapper.__name__ = func.__name__
            wrapper.__doc__ = func.__doc__
            return wrapper

        return decorator

    # ------------------------------------------------------------------
    # Singleton management
    # ------------------------------------------------------------------
    @classmethod
    def get_instance(cls, db_path: str = None) -> "DatabaseManager":
        if cls._instance is None:
            if db_path is None:
                try:
                    from app.config import get_config

                    db_path = get_config().db_path
                except (ImportError, AttributeError):
                    db_path = "data/piao_pick.db"
            cls._instance = cls(db_path)
        return cls._instance

    @classmethod
    def reset_instance(cls):
        cls._instance = None


def get_db() -> DatabaseManager:
    return DatabaseManager.get_instance()
