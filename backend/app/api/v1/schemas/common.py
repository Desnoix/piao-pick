# -*- coding: utf-8 -*-
"""
通用响应模型

定义 HealthResponse、ErrorResponse、SuccessResponse 等通用 schema。
"""

from typing import Optional, Any, List
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """健康检查响应"""

    status: str = Field(..., description="服务状态", examples=["ok"])
    timestamp: str = Field(..., description="时间戳", examples=["2024-01-01T12:00:00"])


class ErrorResponse(BaseModel):
    """错误响应"""

    error: str = Field(..., description="错误类型", examples=["not_found"])
    message: str = Field(..., description="错误详情", examples=["资源不存在"])
    detail: Optional[Any] = Field(None, description="附加错误信息")


class SuccessResponse(BaseModel):
    """通用成功响应"""

    success: bool = Field(True, description="是否成功")
    message: Optional[str] = Field(None, description="成功消息")
    data: Optional[Any] = Field(None, description="响应数据")


class PaginatedResponse(BaseModel):
    """分页响应"""

    total: int = Field(..., description="总数")
    offset: int = Field(..., description="偏移量")
    limit: int = Field(..., description="每页数量")
    items: List[Any] = Field(default_factory=list, description="数据列表")


class DataStatusResponse(BaseModel):
    """数据状态响应"""

    db_path: str = Field(..., description="数据库路径")
    db_size_mb: Optional[float] = Field(None, description="数据库大小 (MB)")
    stock_count: int = Field(0, description="股票数量")
    latest_kline_date: Optional[str] = Field(None, description="最新K线日期")
    latest_factor_date: Optional[str] = Field(None, description="最新因子日期")
