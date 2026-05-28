"""
数据准备任务状态跟踪 (进程内)

线程安全的状态字典, 记录当前进行中的数据准备任务。
仅用于短期状态查询, 不做持久化。
"""

import threading
import time

_lock = threading.Lock()
_tasks: dict[str, dict] = {}


def set_preparing(trade_date: str) -> None:
    """标记某日期数据正在准备中"""
    with _lock:
        _tasks[trade_date] = {
            "status": "preparing",
            "started_at": time.time(),
            "error": None,
        }


def set_done(trade_date: str, result: dict) -> None:
    """标记某日期数据准备完成"""
    with _lock:
        _tasks[trade_date] = {
            "status": "done",
            "started_at": _tasks.get(trade_date, {}).get("started_at"),
            "finished_at": time.time(),
            "result": result,
            "error": None,
        }


def set_failed(trade_date: str, error: str) -> None:
    """标记某日期数据准备失败"""
    with _lock:
        _tasks[trade_date] = {
            "status": "failed",
            "started_at": _tasks.get(trade_date, {}).get("started_at"),
            "finished_at": time.time(),
            "result": None,
            "error": error,
        }


def get_status(trade_date: str) -> dict | None:
    """获取某日期数据准备状态, 无记录返回 None"""
    with _lock:
        task = _tasks.get(trade_date)
        if task is None:
            return None
        return dict(task)


def is_preparing(trade_date: str) -> bool:
    """检查某日期是否正在准备中"""
    with _lock:
        task = _tasks.get(trade_date)
        return task is not None and task.get("status") == "preparing"


def cleanup_old(max_age_seconds: float = 600.0) -> None:
    """清理超过指定时间的记录, 防止内存泄漏"""
    now = time.time()
    with _lock:
        expired = [k for k, v in _tasks.items() if v.get("finished_at") and (now - v["finished_at"]) > max_age_seconds]
        for k in expired:
            del _tasks[k]
