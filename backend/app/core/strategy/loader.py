"""
策略加载器（Phase 2 实现）

从 YAML 文件加载策略配置，解析为策略对象。
"""

import logging
import uuid
from datetime import datetime
from pathlib import Path

import yaml

from app.config import get_config
from app.database import get_db

logger = logging.getLogger(__name__)


class StrategyConfig:
    """策略配置数据类"""

    def __init__(self, raw: dict):
        self.raw = raw
        self.name: str = raw.get("name", "")
        self.display_name: str = raw.get("display_name", self.name)
        self.description: str = raw.get("description", "")
        self.category: str = raw.get("category", "blended")
        self.version: str = raw.get("version", "1.0")
        self.default_active: bool = raw.get("default_active", True)
        self.default_priority: int = raw.get("default_priority", 50)
        self.universe: dict = raw.get("universe", {})
        self.factors: list[dict] = raw.get("factors", [])
        self.neutralization: dict = raw.get("neutralization", {})
        self.filters: list[dict] = raw.get("filters", [])
        self.output: dict = raw.get("output", {})
        self.factor_pipeline: dict = raw.get("factor_pipeline", {})

        # 因子合成配置 (composite method: fixed | icir | equal)
        composite_raw = raw.get("composite", {})
        self.composite_method: str = composite_raw.get("method", "fixed")
        self.icir_lookback: int = composite_raw.get("icir_lookback", 12)
        self.icir_min_periods: int = composite_raw.get("icir_min_periods", 6)
        self.max_single_weight: float = composite_raw.get("max_single_weight", 0.40)


class StrategyLoader:
    """
    策略加载器。

    Phase 2 将实现：
    - 从 strategies/ 目录扫描 YAML 文件
    - 解析为 StrategyConfig 对象
    - 同步到数据库 strategies 表
    - 支持热更新策略配置
    """

    def __init__(self, strategies_dir: str | None = None):
        config = get_config()
        self.strategies_dir = Path(strategies_dir or config.strategies_dir)
        logger.info(f"StrategyLoader initialized: {self.strategies_dir}")

    def load_all(self) -> list[StrategyConfig]:
        """
        加载所有策略 YAML 文件。

        Returns:
            StrategyConfig 列表
        """
        if not self.strategies_dir.exists():
            logger.warning(f"Strategies directory not found: {self.strategies_dir}")
            return []

        configs = []
        for yaml_file in sorted(self.strategies_dir.glob("*.yaml")):
            try:
                config = self._load_file(yaml_file)
                if config:
                    configs.append(config)
                    logger.info(f"Loaded strategy: {config.name} from {yaml_file.name}")
            except Exception as e:
                logger.error(f"Failed to load strategy from {yaml_file}: {e}")

        return configs

    def load_by_name(self, name: str) -> StrategyConfig | None:
        """加载指定名称的策略"""
        yaml_file = self.strategies_dir / f"{name}.yaml"
        if not yaml_file.exists():
            return None
        return self._load_file(yaml_file)

    def _load_file(self, path: Path) -> StrategyConfig | None:
        """从 YAML 文件加载策略配置"""
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
        if not raw or not isinstance(raw, dict):
            return None
        return StrategyConfig(raw)

    def sync_to_db(self) -> int:
        """
        将加载的 YAML 策略同步到数据库 strategies 表。

        - 已存在的策略（按 name 匹配）: 更新 display_name, description, category, config
        - 不存在的策略: 新增
        - 数据库中多出的策略: 不删除（保留手动添加的策略）

        Returns:
            同步的策略数量
        """
        from app.models import Strategy
        from app.repositories.strategy_repo import StrategyRepository

        configs = self.load_all()
        if not configs:
            logger.warning("No strategies to sync")
            return 0

        db = get_db()
        strategy_repo = StrategyRepository(db)
        now = datetime.now().isoformat()
        synced = 0

        for cfg in configs:
            yaml_str = yaml.dump(cfg.raw, allow_unicode=True, default_flow_style=False)
            existing = strategy_repo.get_by_name(cfg.name)

            if existing:
                existing.display_name = cfg.display_name
                existing.description = cfg.description
                existing.category = cfg.category
                existing.config = yaml_str
                existing.is_active = cfg.default_active
                existing.priority = cfg.default_priority
                existing.updated_at = now
                strategy_repo.update(existing)
                logger.info(f"Updated strategy in DB: {cfg.name}")
            else:
                strategy = Strategy(
                    id=str(uuid.uuid4()),
                    name=cfg.name,
                    display_name=cfg.display_name,
                    description=cfg.description,
                    category=cfg.category,
                    config=yaml_str,
                    is_active=cfg.default_active,
                    priority=cfg.default_priority,
                    created_at=now,
                    updated_at=now,
                )
                strategy_repo.create(strategy)
                logger.info(f"Created strategy in DB: {cfg.name}")

            synced += 1

        logger.info(f"Synced {synced} strategies to database")
        return synced
