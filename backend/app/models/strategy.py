from sqlmodel import Field, SQLModel


class Strategy(SQLModel, table=True):
    __tablename__ = "strategies"

    id: str = Field(primary_key=True)  # UUID
    name: str | None = None
    display_name: str | None = None
    description: str | None = None
    category: str | None = None  # 'value'/'momentum'/'blended'
    config: str = Field()  # YAML string
    is_active: bool = Field(default=True)
    priority: int = Field(default=50)
    created_at: str | None = None
    updated_at: str | None = None
