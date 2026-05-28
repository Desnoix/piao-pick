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

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import get_db
from app.repositories import StrategyRepository
from app.schemas.strategy import StrategyDetailSchema, StrategySchema

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_repo() -> StrategyRepository:
    return StrategyRepository(get_db())


def _validate_config_yaml(config_str: str) -> list[dict]:
    """内部校验，仅返回 error 级别问题 / Internal validation, returns error-level issues only"""
    import yaml as pyyaml

    try:
        doc = pyyaml.safe_load(config_str)
    except pyyaml.YAMLError as e:
        return [{"message": str(e).split("\n")[0]}]
    if not isinstance(doc, dict):
        return [{"message": "YAML 根节点必须是映射"}]
    errors = []
    if "name" not in doc:
        errors.append({"message": '缺少必填字段 "name"'})
    if "factors" not in doc:
        errors.append({"message": '缺少必填字段 "factors"'})
    elif not isinstance(doc["factors"], list):
        errors.append({"message": '"factors" 必须是数组'})
    else:
        for i, f in enumerate(doc["factors"]):
            if not isinstance(f, dict):
                continue
            w = f.get("weight")
            if w is not None and not isinstance(w, (int, float)):
                errors.append({"message": f"factors[{i}].weight 必须是数字"})
    return errors


# -- Request models --


class StrategyCreateRequest(BaseModel):
    name: str
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    config: str  # YAML string
    is_active: bool = True
    priority: int = 50


class StrategyUpdateRequest(BaseModel):
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    config: str | None = None
    is_active: bool | None = None
    priority: int | None = None


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
    errs = _validate_config_yaml(req.config)
    if errs:
        raise HTTPException(status_code=422, detail=f"YAML 校验失败: {errs[0]['message']}")

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


@router.post("/validate", summary="校验策略 YAML")
async def validate_strategy_yaml(req: StrategyCreateRequest):
    """校验策略 YAML 配置，返回校验结果"""
    import yaml as pyyaml

    errors = []
    try:
        doc = pyyaml.safe_load(req.config)
    except pyyaml.YAMLError as e:
        pm = getattr(e, "problem_mark", None)
        return {
            "valid": False,
            "errors": [
                {
                    "layer": 1,
                    "severity": "error",
                    "message": str(e).split("\n")[0],
                    "line": pm.line + 1 if pm else None,
                }
            ],
        }
    if not isinstance(doc, dict):
        return {
            "valid": False,
            "errors": [{"layer": 1, "severity": "error", "message": "YAML 根节点必须是映射"}],
        }

    for field in ("name", "factors"):
        if field not in doc:
            errors.append({"layer": 2, "severity": "error", "message": f'缺少 "{field}"', "field": field})

    factors_list = doc.get("factors", [])
    if not isinstance(factors_list, list):
        errors.append({"layer": 2, "severity": "error", "message": '"factors" 必须是数组'})
    else:
        for i, f in enumerate(factors_list):
            if not isinstance(f, dict):
                continue
            if "id" not in f:
                errors.append({"layer": 2, "severity": "error", "message": f"factors[{i}].id 缺失"})
            w = f.get("weight")
            if w is not None and not isinstance(w, (int, float)):
                errors.append(
                    {
                        "layer": 2,
                        "severity": "error",
                        "message": f"factors[{i}].weight 必须是数字",
                    }
                )

        ws = [
            f.get("weight") for f in factors_list if isinstance(f, dict) and isinstance(f.get("weight"), (int, float))
        ]
        if ws:
            mx = max(abs(w) for w in ws)
            norm = ws if mx <= 1 else [w / 100 for w in ws]
            s = sum(norm)
            if abs(s - 1) > 0.02:
                errors.append(
                    {
                        "layer": 3,
                        "severity": "warning",
                        "message": f"权重和 = {s:.3f}",
                        "field": "factors",
                    }
                )

    has_hard = any(e["severity"] == "error" for e in errors)
    return {"valid": not has_hard, "errors": errors}


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

    if req.config is not None:
        errs = _validate_config_yaml(req.config)
        if errs:
            raise HTTPException(status_code=422, detail=f"YAML 校验失败: {errs[0]['message']}")

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
