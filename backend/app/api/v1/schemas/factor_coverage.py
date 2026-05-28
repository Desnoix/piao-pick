"""
因子覆盖率 API 响应模型。
Factor coverage API response models.
"""

from pydantic import BaseModel, Field


class FactorCoverageResponse(BaseModel):
    """单个策略的因子覆盖率 / Factor coverage for one strategy."""

    strategy_name: str = Field(description="策略名称")
    total_factors: int = Field(description="配置的因子总数")
    available_factors: list[str] = Field(description="可用因子列表")
    stub_factors: list[str] = Field(description="Stub (未实现) 因子列表")
    coverage_rate: float = Field(
        description="覆盖率 0.0-1.0",
        examples=[0.5556],
    )
    configured_weights: dict[str, float] = Field(description="YAML 配置权重 (原始值)")
    effective_weights: dict[str, float] = Field(description="实际生效权重 (归一化后)")
    weight_drift: dict[str, float] = Field(description="权重漂移量 = effective - configured")


class AllCoverageResponse(BaseModel):
    """全部策略的因子覆盖率 / Factor coverage for all strategies."""

    strategies: list[FactorCoverageResponse]
    global_stub_factors: list[str] = Field(description="全局 stub 因子清单")
