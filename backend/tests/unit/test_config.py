"""
Config 模块单元测试

覆盖: parse_env_bool, parse_env_int, parse_env_float, Config 单例, validate()。
测试纯逻辑, 无外部环境依赖, 标记为 @pytest.mark.unit。
"""

import pytest

from app.config import (
    Config,
    ConfigIssue,
    parse_env_bool,
    parse_env_float,
    parse_env_int,
)

pytestmark = pytest.mark.unit


# --------------------------------------------------------------------
# parse_env_bool
# --------------------------------------------------------------------


class TestParseEnvBool:
    def test_none_returns_default(self):
        assert parse_env_bool(None, default=True) is True
        assert parse_env_bool(None, default=False) is False

    def test_empty_string_returns_default(self):
        assert parse_env_bool("", default=True) is True
        assert parse_env_bool("   ", default=False) is False

    def test_falsey_values(self):
        for v in ("0", "false", "False", "FALSE", "no", "No", "off", "OFF"):
            assert parse_env_bool(v) is False

    def test_truthy_values(self):
        for v in ("1", "true", "True", "yes", "on", "any"):
            assert parse_env_bool(v) is True


# --------------------------------------------------------------------
# parse_env_int
# --------------------------------------------------------------------


class TestParseEnvInt:
    def test_valid_integer(self):
        assert parse_env_int("42", default=10, field_name="X") == 42

    def test_none_returns_default(self):
        assert parse_env_int(None, default=7, field_name="X") == 7

    def test_invalid_returns_default(self):
        assert parse_env_int("notanint", default=99, field_name="X") == 99

    def test_clamps_to_minimum(self):
        assert parse_env_int("0", default=10, field_name="X", minimum=5) == 5

    def test_clamps_to_maximum(self):
        assert parse_env_int("100", default=10, field_name="X", maximum=50) == 50

    def test_empty_string_returns_default(self):
        assert parse_env_int("   ", default=3, field_name="X") == 3


# --------------------------------------------------------------------
# parse_env_float
# --------------------------------------------------------------------


class TestParseEnvFloat:
    def test_valid_float(self):
        assert parse_env_float("3.14", default=1.0, field_name="X") == pytest.approx(3.14)

    def test_none_returns_default(self):
        assert parse_env_float(None, default=2.5, field_name="X") == 2.5

    def test_invalid_returns_default(self):
        assert parse_env_float("xyz", default=1.5, field_name="X") == 1.5

    def test_clamps_to_minimum(self):
        assert parse_env_float("0.1", default=1.0, field_name="X", minimum=0.5) == 0.5

    def test_clamps_to_maximum(self):
        assert parse_env_float("9.9", default=1.0, field_name="X", maximum=5.0) == 5.0


# --------------------------------------------------------------------
# ConfigIssue
# --------------------------------------------------------------------


class TestConfigIssue:
    def test_str_returns_message(self):
        issue = ConfigIssue(severity="error", message="broken", field="FOO")
        assert str(issue) == "broken"

    def test_severities(self):
        for sev in ("error", "warning", "info"):
            issue = ConfigIssue(severity=sev, message="x")
            assert issue.severity == sev


# --------------------------------------------------------------------
# Config singleton
# --------------------------------------------------------------------


class TestConfigSingleton:
    def test_get_instance_returns_same_object(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_ENABLED", "false")
        Config.reset_instance()
        a = Config.get_instance()
        b = Config.get_instance()
        assert a is b
        Config.reset_instance()

    def test_reset_creates_new_instance(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_ENABLED", "false")
        Config.reset_instance()
        a = Config.get_instance()
        Config.reset_instance()
        b = Config.get_instance()
        assert a is not b
        Config.reset_instance()

    def test_loads_db_path_from_env(self, monkeypatch):
        monkeypatch.setenv("DB_PATH", "/tmp/my.db")
        monkeypatch.setenv("SCHEDULE_ENABLED", "false")
        Config.reset_instance()
        cfg = Config.get_instance()
        assert cfg.db_path == "/tmp/my.db"
        Config.reset_instance()

    def test_default_stock_list_when_empty(self, monkeypatch):
        monkeypatch.delenv("STOCK_LIST", raising=False)
        monkeypatch.setenv("SCHEDULE_ENABLED", "false")
        Config.reset_instance()
        cfg = Config.get_instance()
        assert cfg.stock_list == ["600519", "000001", "300750"]
        Config.reset_instance()

    def test_custom_stock_list_parsed(self, monkeypatch):
        monkeypatch.setenv("STOCK_LIST", "000001, 601398, 300750")
        monkeypatch.setenv("SCHEDULE_ENABLED", "false")
        Config.reset_instance()
        cfg = Config.get_instance()
        assert cfg.stock_list == ["000001", "601398", "300750"]
        Config.reset_instance()

    def test_cors_origin_list(self, monkeypatch):
        monkeypatch.setenv("CORS_ORIGINS", "http://a.example.com, http://b.example.com")
        monkeypatch.setenv("SCHEDULE_ENABLED", "false")
        Config.reset_instance()
        cfg = Config.get_instance()
        assert cfg.cors_origin_list == [
            "http://a.example.com",
            "http://b.example.com",
        ]
        Config.reset_instance()


# --------------------------------------------------------------------
# Config.validate
# --------------------------------------------------------------------


class TestConfigValidate:
    def test_validate_returns_list(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_ENABLED", "false")
        Config.reset_instance()
        cfg = Config.get_instance()
        issues = cfg.validate()
        assert isinstance(issues, list)
        assert all(isinstance(i, ConfigIssue) for i in issues)
        Config.reset_instance()

    def test_invalid_schedule_time(self, monkeypatch):
        monkeypatch.setenv("SCHEDULE_ENABLED", "true")
        monkeypatch.setenv("SCHEDULE_TIME", "25:99")
        Config.reset_instance()
        cfg = Config.get_instance()
        issues = cfg.validate()
        assert any(i.severity == "error" and "SCHEDULE_TIME" in i.field for i in issues)
        Config.reset_instance()

    def test_invalid_log_level(self, monkeypatch):
        monkeypatch.setenv("LOG_LEVEL", "INVALID_LEVEL")
        monkeypatch.setenv("SCHEDULE_ENABLED", "false")
        Config.reset_instance()
        cfg = Config.get_instance()
        issues = cfg.validate()
        assert any("LOG_LEVEL" in i.field for i in issues)
        Config.reset_instance()

    def test_max_workers_clamped(self, monkeypatch):
        monkeypatch.setenv("MAX_WORKERS", "999")
        monkeypatch.setenv("SCHEDULE_ENABLED", "false")
        Config.reset_instance()
        cfg = Config.get_instance()
        assert cfg.max_workers == 16
        Config.reset_instance()
