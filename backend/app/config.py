"""
===================================
piao-pick Configuration Module
===================================

Responsibilities:
1. Singleton pattern for global configuration management
2. Load sensitive config from .env file
3. Provide type-safe configuration access
"""

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

from dotenv import load_dotenv

logger = logging.getLogger(__name__)


@dataclass
class ConfigIssue:
    """Structured configuration validation issue with a severity level.

    Attributes:
        severity: One of "error", "warning", or "info".
        message: Human-readable description of the issue.
        field: The environment variable / config field name most relevant to
               this issue (empty string when not applicable).
    """

    severity: Literal["error", "warning", "info"]
    message: str
    field: str = ""

    def __str__(self) -> str:
        return self.message


_FALSEY_ENV_VALUES = {"0", "false", "no", "off"}


def parse_env_bool(value: str | None, default: bool = False) -> bool:
    """Parse common truthy/falsey environment-style values."""
    if value is None:
        return default
    normalized = value.strip().lower()
    if not normalized:
        return default
    return normalized not in _FALSEY_ENV_VALUES


def parse_env_int(
    value: str | None,
    default: int,
    *,
    field_name: str,
    minimum: int | None = None,
    maximum: int | None = None,
) -> int:
    """Parse an integer env value with warning + fallback semantics."""
    raw_value = value
    if raw_value is None or not str(raw_value).strip():
        parsed = int(default)
    else:
        try:
            parsed = int(str(raw_value).strip())
        except (TypeError, ValueError):
            logger.warning(
                "%s=%r is not a valid integer; falling back to %s",
                field_name,
                raw_value,
                default,
            )
            parsed = int(default)

    if minimum is not None and parsed < minimum:
        logger.warning(
            "%s=%r is below minimum %s; clamping to %s",
            field_name,
            parsed,
            minimum,
            minimum,
        )
        parsed = minimum
    if maximum is not None and parsed > maximum:
        logger.warning(
            "%s=%r is above maximum %s; clamping to %s",
            field_name,
            parsed,
            maximum,
            maximum,
        )
        parsed = maximum
    return parsed


def parse_env_float(
    value: str | None,
    default: float,
    *,
    field_name: str,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    """Parse a float env value with warning + fallback semantics."""
    raw_value = value
    if raw_value is None or not str(raw_value).strip():
        parsed = float(default)
    else:
        try:
            parsed = float(str(raw_value).strip())
        except (TypeError, ValueError):
            logger.warning(
                "%s=%r is not a valid number; falling back to %s",
                field_name,
                raw_value,
                default,
            )
            parsed = float(default)

    if minimum is not None and parsed < minimum:
        logger.warning(
            "%s=%r is below minimum %s; clamping to %s",
            field_name,
            parsed,
            minimum,
            minimum,
        )
        parsed = minimum
    if maximum is not None and parsed > maximum:
        logger.warning(
            "%s=%r is above maximum %s; clamping to %s",
            field_name,
            parsed,
            maximum,
            maximum,
        )
        parsed = maximum
    return parsed


def setup_env(override: bool = False) -> None:
    """
    Initialize environment variables from .env file.

    Args:
        override: If True, overwrite existing environment variables with values
                  from .env file.
    """
    env_file = os.getenv("ENV_FILE")
    if env_file:
        env_path = Path(env_file)
    else:
        # backend/app/config.py -> backend/ -> project root
        env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=override)
    else:
        logger.debug(f"No .env file found at {env_path}")


@dataclass
class Config:
    """
    System configuration - Singleton pattern.

    Design:
    - Uses dataclass for concise property definitions
    - All config items loaded from environment variables with defaults
    - Class method get_instance() for singleton access
    """

    # === Database ===
    db_path: str = "./data/piao_pick.db"

    # === Data source API tokens ===
    tushare_token: str | None = None

    # === Scheduling ===
    schedule_enabled: bool = False
    schedule_time: str = "18:00"

    # === Concurrency ===
    max_workers: int = 3

    # === Selection ===
    selection_max_stocks: int = 10

    # === Strategy directory ===
    strategies_dir: str = "./strategies"

    # === Logging ===
    log_dir: str = "./logs"
    log_level: str = "INFO"

    # === Stock list (watchlist) ===
    stock_list: list[str] = field(default_factory=list)

    # === CORS (WebUI) ===
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    # === Data Quality Monitor ===
    dq_enabled: bool = True
    dq_webhook_url: str | None = None
    dq_webhook_type: str = "generic"  # "generic" | "slack" | "wechat"

    # === Cache ===
    cache_l1_enabled: bool = True
    cache_l2_enabled: bool = True
    cache_l3_enabled: bool = False
    cache_l2_dir: str = "./cache"
    cache_redis_url: str = "redis://localhost:6379/0"
    cache_l1_maxsize: int = 500
    cache_l1_ttl_seconds: int = 300  # 5min
    cache_l1_config_ttl_seconds: int = 3600  # 1h
    cache_l2_ttl_hours: int = 24

    # Singleton instance
    _instance: Optional["Config"] = None

    @property
    def cors_origin_list(self) -> list[str]:
        """Parse CORS origins into a list."""
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @classmethod
    def get_instance(cls) -> "Config":
        """
        Get configuration singleton instance.

        Singleton pattern ensures:
        1. Only one global config instance exists
        2. Config is loaded from env variables only once
        3. All modules share the same config
        """
        if cls._instance is None:
            cls._instance = cls._load_from_env()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None

    @classmethod
    def _load_from_env(cls) -> "Config":
        """Load configuration from .env file and environment variables."""
        # Ensure environment variables are loaded
        setup_env()

        # Parse stock list (comma-separated)
        stock_list_str = os.getenv("STOCK_LIST", "")
        stock_list = [(c or "").strip().upper() for c in stock_list_str.split(",") if (c or "").strip()]

        # If no stocks configured, use defaults
        if not stock_list:
            stock_list = ["600519", "000001", "300750"]

        # Parse all config values
        config = cls(
            db_path=os.getenv("DB_PATH", "./data/piao_pick.db"),
            tushare_token=os.getenv("TUSHARE_TOKEN", "").strip() or None,
            schedule_enabled=parse_env_bool(os.getenv("SCHEDULE_ENABLED"), default=False),
            schedule_time=os.getenv("SCHEDULE_TIME", "18:00"),
            max_workers=parse_env_int(
                os.getenv("MAX_WORKERS"),
                default=3,
                field_name="MAX_WORKERS",
                minimum=1,
                maximum=16,
            ),
            selection_max_stocks=parse_env_int(
                os.getenv("SELECTION_MAX_STOCKS"),
                default=10,
                field_name="SELECTION_MAX_STOCKS",
                minimum=1,
                maximum=100,
            ),
            strategies_dir=os.getenv("STRATEGIES_DIR", "./strategies"),
            log_dir=os.getenv("LOG_DIR", "./logs"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            stock_list=stock_list,
            cors_origins=os.getenv(
                "CORS_ORIGINS",
                "http://localhost:5173,http://localhost:3000",
            ),
            dq_enabled=parse_env_bool(os.getenv("DQ_ENABLED"), default=True),
            dq_webhook_url=os.getenv("DQ_WEBHOOK_URL", "").strip() or None,
            dq_webhook_type=os.getenv("DQ_WEBHOOK_TYPE", "generic").strip().lower(),
            cache_l1_enabled=parse_env_bool(os.getenv("CACHE_L1_ENABLED"), default=True),
            cache_l2_enabled=parse_env_bool(os.getenv("CACHE_L2_ENABLED"), default=True),
            cache_l3_enabled=parse_env_bool(os.getenv("CACHE_L3_ENABLED"), default=False),
            cache_l2_dir=os.getenv("CACHE_L2_DIR", "./cache"),
            cache_redis_url=os.getenv("CACHE_REDIS_URL", "redis://localhost:6379/0"),
            cache_l1_maxsize=parse_env_int(
                os.getenv("CACHE_L1_MAXSIZE"),
                default=500,
                field_name="CACHE_L1_MAXSIZE",
                minimum=10,
                maximum=5000,
            ),
            cache_l1_ttl_seconds=parse_env_int(
                os.getenv("CACHE_L1_TTL_SECONDS"),
                default=300,
                field_name="CACHE_L1_TTL_SECONDS",
                minimum=10,
                maximum=3600,
            ),
            cache_l1_config_ttl_seconds=parse_env_int(
                os.getenv("CACHE_L1_CONFIG_TTL_SECONDS"),
                default=3600,
                field_name="CACHE_L1_CONFIG_TTL_SECONDS",
                minimum=60,
                maximum=86400,
            ),
            cache_l2_ttl_hours=parse_env_int(
                os.getenv("CACHE_L2_TTL_HOURS"),
                default=24,
                field_name="CACHE_L2_TTL_HOURS",
                minimum=1,
                maximum=168,
            ),
        )

        return config

    def validate(self) -> list[ConfigIssue]:
        """
        Validate configuration and return list of issues.

        Returns:
            List of ConfigIssue objects describing validation problems
        """
        issues: list[ConfigIssue] = []

        # Check stock list
        if not self.stock_list:
            issues.append(
                ConfigIssue(
                    severity="warning",
                    message="No stocks configured in STOCK_LIST. Using defaults.",
                    field="STOCK_LIST",
                )
            )

        # Check schedule time format
        if self.schedule_enabled:
            try:
                parts = self.schedule_time.split(":")
                if len(parts) != 2:
                    raise ValueError("Invalid format")
                hour, minute = int(parts[0]), int(parts[1])
                if not (0 <= hour <= 23 and 0 <= minute <= 59):
                    raise ValueError("Out of range")
            except (ValueError, IndexError):
                issues.append(
                    ConfigIssue(
                        severity="error",
                        message=f"Invalid SCHEDULE_TIME format: {self.schedule_time}. Expected HH:MM.",
                        field="SCHEDULE_TIME",
                    )
                )

        # Check log level
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if self.log_level.upper() not in valid_levels:
            issues.append(
                ConfigIssue(
                    severity="warning",
                    message=f"Invalid LOG_LEVEL: {self.log_level}. Expected one of {valid_levels}.",
                    field="LOG_LEVEL",
                )
            )

        # Check database path
        db_dir = os.path.dirname(self.db_path)
        if db_dir and not os.path.exists(db_dir):
            issues.append(
                ConfigIssue(
                    severity="warning",
                    message=f"Database directory does not exist: {db_dir}. Will be created on first use.",
                    field="DB_PATH",
                )
            )

        # Check strategies directory
        if not os.path.exists(self.strategies_dir):
            issues.append(
                ConfigIssue(
                    severity="info",
                    message=f"Strategies directory does not exist: {self.strategies_dir}. Will be created on first use.",
                    field="STRATEGIES_DIR",
                )
            )

        # Tushare token is optional
        if not self.tushare_token:
            issues.append(
                ConfigIssue(
                    severity="info",
                    message="TUSHARE_TOKEN not configured. TushareFetcher will be disabled.",
                    field="TUSHARE_TOKEN",
                )
            )

        return issues


def get_config() -> Config:
    """Get the global configuration instance."""
    return Config.get_instance()
