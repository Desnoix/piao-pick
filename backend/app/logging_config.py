# -*- coding: utf-8 -*-
"""
===================================
Logging Configuration Module
===================================

Responsibilities:
1. Provide unified log format and configuration
2. Support console + file (rotating) dual-layer output
3. Automatically lower third-party library log levels
"""

import logging
import sys
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import List, Optional


LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(pathname)s:%(lineno)d | %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

_ALLOWED_LOG_LEVELS = {
    'DEBUG': logging.DEBUG,
    'INFO': logging.INFO,
    'WARNING': logging.WARNING,
    'ERROR': logging.ERROR,
    'CRITICAL': logging.CRITICAL,
}


class RelativePathFormatter(logging.Formatter):
    """Custom Formatter that outputs relative paths instead of absolute paths."""

    def __init__(self, fmt=None, datefmt=None, relative_to=None):
        super().__init__(fmt, datefmt)
        self.relative_to = Path(relative_to) if relative_to else Path.cwd()

    def format(self, record):
        try:
            record.pathname = str(Path(record.pathname).relative_to(self.relative_to))
        except ValueError:
            pass
        return super().format(record)


# Default third-party loggers to quiet
DEFAULT_QUIET_LOGGERS = [
    'urllib3',
    'sqlalchemy',
    'google',
    'httpx',
]


def setup_logging(
    log_prefix: str = "app",
    log_dir: str = "./logs",
    debug: bool = False,
    console_level: Optional[int] = None,
    extra_quiet_loggers: Optional[List[str]] = None,
) -> None:
    """
    Initialize unified logging system.

    Configures dual-layer log output:
    1. Console: Level based on debug parameter or console_level
    2. File (rotating): INFO level, 10MB rotation, 5 backups

    Args:
        log_prefix: Log file name prefix (e.g. "app" -> app_20240101.log)
        log_dir: Log file directory, default ./logs
        debug: Enable debug mode (console outputs DEBUG level)
        console_level: Console log level (optional, overrides debug parameter)
        extra_quiet_loggers: Additional third-party loggers to quiet
    """
    # Determine console log level
    if console_level is not None:
        level = console_level
    else:
        level = logging.DEBUG if debug else logging.INFO

    # Create log directory
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    # Log file paths (by date)
    today_str = datetime.now().strftime('%Y%m%d')
    log_file = log_path / f"{log_prefix}_{today_str}.log"

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Root set to DEBUG, handlers control output level

    # Clear existing handlers to avoid duplicates
    if root_logger.handlers:
        root_logger.handlers.clear()

    # Create relative path Formatter
    project_root = Path.cwd()
    rel_formatter = RelativePathFormatter(
        LOG_FORMAT, LOG_DATE_FORMAT, relative_to=project_root
    )

    # Handler 1: Console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(rel_formatter)
    root_logger.addHandler(console_handler)

    # Handler 2: Log file (INFO level, 10MB rotation)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding='utf-8',
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(rel_formatter)
    root_logger.addHandler(file_handler)

    # Lower third-party library log levels
    quiet_loggers = DEFAULT_QUIET_LOGGERS.copy()
    if extra_quiet_loggers:
        quiet_loggers.extend(extra_quiet_loggers)

    for logger_name in quiet_loggers:
        logging.getLogger(logger_name).setLevel(logging.WARNING)

    # Output initialization complete message
    try:
        rel_log_path = log_path.resolve().relative_to(project_root)
    except ValueError:
        rel_log_path = log_path

    try:
        rel_log_file = log_file.resolve().relative_to(project_root)
    except ValueError:
        rel_log_file = log_file

    logging.info(f"Logging system initialized, log dir: {rel_log_path}")
    logging.info(f"Log file: {rel_log_file}")
