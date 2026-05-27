# -*- coding: utf-8 -*-
from pydantic import BaseModel
from typing import Optional


class StrategySchema(BaseModel):
    id: str
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    is_active: bool = True
    priority: int = 50


class StrategyDetailSchema(StrategySchema):
    config: str  # YAML string
