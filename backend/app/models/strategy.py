# -*- coding: utf-8 -*-
from sqlmodel import SQLModel, Field
from typing import Optional


class Strategy(SQLModel, table=True):
    __tablename__ = "strategies"

    id: str = Field(primary_key=True)  # UUID
    name: Optional[str] = None
    display_name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None  # 'value'/'momentum'/'blended'
    config: str = Field()  # YAML string
    is_active: bool = Field(default=True)
    priority: int = Field(default=50)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
