# -*- coding: utf-8 -*-
"""历史数据同步任务记录模型"""
from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime
import uuid


class HistorySyncTask(SQLModel, table=True):
    """历史数据同步任务状态记录"""
    
    __tablename__ = "history_sync_tasks"
    
    # 主键
    task_id: str = Field(primary_key=True, default_factory=lambda: str(uuid.uuid4()))
    
    # 任务参数
    start_date: str  # 开始日期 YYYY-MM-DD
    end_date: str  # 结束日期 YYYY-MM-DD
    adjust_type: str = Field(default="qfq")  # 复权类型: qfq(前复权), hfq(后复权), null(不复权)
    
    # 进度统计
    total_stocks: int = Field(default=0)
    completed_stocks: int = Field(default=0)
    failed_stocks: int = Field(default=0)
    total_klines: int = Field(default=0)  # 成功写入的K线数
    
    # 状态
    status: str = Field(default="pending")  # pending, running, completed, failed, paused
    current_stock: Optional[str] = None  # 当前正在处理的股票代码
    
    # 错误记录
    error_messages: Optional[str] = None  # JSON array of error messages
    
    # 时间戳
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    def update_progress(self, completed: int, failed: int, total_klines: int, current_stock: Optional[str] = None):
        """更新进度"""
        self.completed_stocks = completed
        self.failed_stocks = failed
        self.total_klines = total_klines
        if current_stock:
            self.current_stock = current_stock
    
    def mark_started(self):
        """标记任务开始"""
        self.status = "running"
        self.started_at = datetime.now().isoformat()
    
    def mark_completed(self):
        """标记任务完成"""
        self.status = "completed"
        self.completed_at = datetime.now().isoformat()
        self.current_stock = None
    
    def mark_failed(self, error: str):
        """标记任务失败"""
        self.status = "failed"
        self.completed_at = datetime.now().isoformat()
        self.current_stock = None
        if self.error_messages:
            import json
            errors = json.loads(self.error_messages)
            errors.append(error)
            self.error_messages = json.dumps(errors, ensure_ascii=False)
        else:
            import json
            self.error_messages = json.dumps([error], ensure_ascii=False)
    
    def get_progress_percent(self) -> float:
        """获取进度百分比"""
        if self.total_stocks == 0:
            return 0.0
        return (self.completed_stocks + self.failed_stocks) / self.total_stocks * 100
    
    def is_active(self) -> bool:
        """任务是否仍在运行"""
        return self.status in ["pending", "running"]
