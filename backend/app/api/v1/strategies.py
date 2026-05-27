# -*- coding: utf-8 -*-
"""
策略管理 API 端点

- GET    /       列出所有策略
- POST   /       创建策略
- GET    /{id}   获取策略详情
- PUT    /{id}   更新策略
- DELETE /{id}   删除策略
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_db
from app.repositories import StrategyRepository
from app.schemas.strategy import StrategySchema, StrategyDetailSchema

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_repo() -> StrategyRepository:
    return StrategyRepository(get_db())


# -- Request models --


class StrategyCreateRequest(BaseModel):
    name: str
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    config: str  # YAML string
    is_active: bool = True
    priority: int = 50


class StrategyUpdateRequest(BaseModel):
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    config: Optional[str] = None
    is_active: Optional[bool] = None
    priority: Optional[int] = None


# -- Endpoints --


@router.get("/", summary="列出所有策略")
async def list_strategies():
    """获取所有策略列表"""
    repo = _get_repo()
    strategies = repo.get_all()
    return [StrategySchema.model_validate(s, from_attributes=True).model_dump() for s in strategies]


@router.post("/", summary="创建策略")
async def create_strategy(req: StrategyCreateRequest):
    """创建新策略"""
    from app.models import Strategy

    repo = _get_repo()
    now = datetime.now().isoformat()
    strategy = Strategy(
        id=str(uuid.uuid4()),
        name=req.name,
        display_name=req.display_name or req.name,
        description=req.description,
        category=req.category,
        config=req.config,
        is_active=req.is_active,
        priority=req.priority,
        created_at=now,
        updated_at=now,
    )
    repo.create(strategy)
    return StrategyDetailSchema.model_validate(strategy, from_attributes=True).model_dump()


@router.get("/{strategy_id}", summary="获取策略详情")
async def get_strategy(strategy_id: str):
    """获取单个策略详情（含配置）"""
    repo = _get_repo()
    strategy = repo.get_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    return StrategyDetailSchema.model_validate(strategy, from_attributes=True).model_dump()


@router.put("/{strategy_id}", summary="更新策略")
async def update_strategy(strategy_id: str, req: StrategyUpdateRequest):
    """更新策略"""
    repo = _get_repo()
    strategy = repo.get_by_id(strategy_id)
    if not strategy:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")

    updates = req.model_dump(exclude_unset=True)
    for key, value in updates.items():
        setattr(strategy, key, value)
    strategy.updated_at = datetime.now().isoformat()
    repo.update(strategy)
    return StrategyDetailSchema.model_validate(strategy, from_attributes=True).model_dump()


@router.delete("/{strategy_id}", summary="删除策略")
async def delete_strategy(strategy_id: str):
    """删除策略"""
    repo = _get_repo()
    deleted = repo.delete(strategy_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Strategy {strategy_id} not found")
    return {"success": True, "message": f"Strategy {strategy_id} deleted"}
