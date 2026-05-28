"""
因子覆盖率 API 端点。
Factor coverage API endpoints.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.api.v1.schemas.factor_coverage import (
    AllCoverageResponse,
    FactorCoverageResponse,
)
from app.services.factor_coverage_service import STUB_FACTORS, FactorCoverageService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get(
    "/factor-coverage-all",
    response_model=AllCoverageResponse,
    summary="获取全部策略因子覆盖率",
)
def get_all_factor_coverage() -> AllCoverageResponse:
    """返回所有策略的因子覆盖率汇总。"""
    from app.database import get_db
    from app.repositories import StrategyRepository

    db = get_db()
    repo = StrategyRepository(db)
    strategies = repo.get_all()

    service = FactorCoverageService()
    results = []
    for s in strategies:
        if s.name:
            r = service.get_coverage(s.name)
            if "error" not in r:
                results.append(FactorCoverageResponse(**r))

    return AllCoverageResponse(
        strategies=results,
        global_stub_factors=sorted(STUB_FACTORS),
    )


@router.get(
    "/{name}/factor-coverage",
    response_model=FactorCoverageResponse,
    summary="获取策略因子覆盖率",
)
def get_factor_coverage(name: str) -> FactorCoverageResponse:
    """
    返回指定策略的因子覆盖率，包括可用/stub 因子清单、
    配置权重与实际生效权重的对比。
    """
    service = FactorCoverageService()
    result = service.get_coverage(name)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return FactorCoverageResponse(**result)
