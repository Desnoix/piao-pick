# -*- coding: utf-8 -*-
"""历史同步任务状态管理"""
from sqlmodel import select, desc
from app.models.history_sync_task import HistorySyncTask
from typing import Optional, List
from app.database import DatabaseManager


class HistorySyncRepository:
    """历史同步任务仓库"""
    
    def __init__(self, db: DatabaseManager):
        self.db = db
    
    def create_task(self, task: HistorySyncTask) -> HistorySyncTask:
        """创建新任务"""
        with self.db.get_session() as session:
            session.add(task)
            session.commit()
            session.refresh(task)
            return task
    
    def get_task(self, task_id: str) -> Optional[HistorySyncTask]:
        """获取任务"""
        with self.db.get_session() as session:
            return session.get(HistorySyncTask, task_id)
    
    def update_task(self, task: HistorySyncTask) -> HistorySyncTask:
        """更新任务"""
        with self.db.get_session() as session:
            session.merge(task)
            session.commit()
            return task
    
    def get_latest_task(self, status: Optional[str] = None) -> Optional[HistorySyncTask]:
        """获取最新的任务（按创建时间倒序）"""
        with self.db.get_session() as session:
            statement = select(HistorySyncTask).order_by(desc(HistorySyncTask.created_at))
            if status:
                statement = statement.where(HistorySyncTask.status == status)
            return session.exec(statement).first()
    
    def get_active_task(self) -> Optional[HistorySyncTask]:
        """获取正在运行的任务（pending 或 running）"""
        with self.db.get_session() as session:
            statement = (
                select(HistorySyncTask)
                .where(HistorySyncTask.status.in_(["pending", "running"]))
                .order_by(desc(HistorySyncTask.created_at))
            )
            return session.exec(statement).first()
    
    def list_tasks(self, limit: int = 10, offset: int = 0) -> List[HistorySyncTask]:
        """列出任务历史"""
        with self.db.get_session() as session:
            statement = (
                select(HistorySyncTask)
                .order_by(desc(HistorySyncTask.created_at))
                .offset(offset)
                .limit(limit)
            )
            return list(session.exec(statement).all())
    
    def count_tasks(self, status: Optional[str] = None) -> int:
        """统计任务数量"""
        from sqlmodel import func
        with self.db.get_session() as session:
            statement = select(func.count()).select_from(HistorySyncTask)
            if status:
                statement = statement.where(HistorySyncTask.status == status)
            return session.exec(statement).one()
