"""
设置存储服务 - 数据源 token 等运行时配置的持久化读写。

Singleton pattern: get_settings_store() returns the shared instance.
Stores settings in backend/data/settings.json
"""

import json
import logging
import os
from pathlib import Path
from threading import RLock

logger = logging.getLogger(__name__)

SETTINGS_PATH = Path(__file__).parent.parent.parent / "data" / "settings.json"
DEFAULT_SETTINGS = {
    "jqdata_token": "",
    "jqdata_password": "",
}


class SettingsStore:
    _instance = None
    _lock = RLock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if hasattr(self, "_initialized"):
            return
        self._initialized = True
        self._ensure_file()

    def _ensure_file(self):
        """如果文件不存在则创建默认设置文件。"""
        if not SETTINGS_PATH.exists():
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            self._write(DEFAULT_SETTINGS)

    def _read(self) -> dict:
        try:
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return DEFAULT_SETTINGS.copy()

    def _write(self, data: dict):
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def get_all(self) -> dict:
        with self._lock:
            return self._read()

    def get(self, key: str) -> str:
        with self._lock:
            data = self._read()
            return str(data.get(key, ""))

    def set(self, key: str, value: str):
        with self._lock:
            data = self._read()
            data[key] = value
            self._write(data)

    def update(self, updates: dict):
        with self._lock:
            data = self._read()
            data.update(updates)
            self._write(data)


def get_settings_store() -> SettingsStore:
    return SettingsStore()