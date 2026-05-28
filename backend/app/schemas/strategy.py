from pydantic import BaseModel


class StrategySchema(BaseModel):
    id: str
    name: str | None = None
    display_name: str | None = None
    description: str | None = None
    category: str | None = None
    is_active: bool = True
    priority: int = 50


class StrategyDetailSchema(StrategySchema):
    config: str  # YAML string
