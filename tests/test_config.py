"""
Unit tests for Android Gemini Agent configuration loader and Settings model.
"""

from __future__ import annotations

import os
from pathlib import Path
import pytest
from pydantic import ValidationError

from android_gemini_agent.config import (
    Settings,
    get_config,
    load_config,
    reset_config,
    set_config,
)


class TestConfigSettings:
    """Validates configuration defaults, environment overrides, and runtime updates."""

    def test_default_settings(self):
        """Verifies canonical defaults when initialized without custom environment."""
        cfg = Settings()
        assert cfg.gemini_model == "gemini-3.5-flash-lite"
        assert cfg.gemini_temperature == 0.0
        assert cfg.adb_device_ip == "192.168.1.100"
        assert cfg.adb_device_port == 5555
        assert cfg.adb_timeout_seconds == 10.0
        assert cfg.max_agent_steps == 20
        assert cfg.action_delay_seconds == 1.0
        assert cfg.loop_detection_threshold == 3
        assert cfg.context_history_max_turns == 5
        assert cfg.log_level == "INFO"
        assert cfg.rich_tracebacks is True
        assert cfg.device_serial == "192.168.1.100:5555"

    def test_is_gemini_configured_detection(self):
        """Tests detection of configured vs placeholder Gemini API keys."""
        assert Settings(gemini_api_key="").is_gemini_configured is False
        assert Settings(gemini_api_key="your_gemini_api_key_here").is_gemini_configured is False
        assert Settings(gemini_api_key="dummy_key").is_gemini_configured is False
        assert Settings(gemini_api_key="valid_production_gemini_api_key_string").is_gemini_configured is True

    def test_load_from_custom_env_file(self, tmp_path: Path):
        """Loads configuration from a designated custom .env file."""
        env_content = (
            "GEMINI_API_KEY=custom_test_key_12345\n"
            "GEMINI_MODEL=gemini-2.5-pro\n"
            "GEMINI_TEMPERATURE=0.7\n"
            "ADB_DEVICE_IP=10.0.0.42\n"
            "ADB_DEVICE_PORT=4555\n"
            "ADB_TIMEOUT_SECONDS=15.0\n"
            "MAX_AGENT_STEPS=30\n"
            "ACTION_DELAY_SECONDS=2.5\n"
            "LOOP_DETECTION_THRESHOLD=4\n"
            "CONTEXT_HISTORY_MAX_TURNS=8\n"
            "LOG_LEVEL=DEBUG\n"
            "RICH_TRACEBACKS=False\n"
        )
        custom_env = tmp_path / "custom.env"
        custom_env.write_text(env_content, encoding="utf-8")

        loaded = load_config(custom_env)
        assert loaded.gemini_api_key == "custom_test_key_12345"
        assert loaded.gemini_model == "gemini-2.5-pro"
        assert loaded.gemini_temperature == 0.7
        assert loaded.adb_device_ip == "10.0.0.42"
        assert loaded.adb_device_port == 4555
        assert loaded.adb_timeout_seconds == 15.0
        assert loaded.max_agent_steps == 30
        assert loaded.action_delay_seconds == 2.5
        assert loaded.loop_detection_threshold == 4
        assert loaded.context_history_max_turns == 8
        assert loaded.log_level == "DEBUG"
        assert loaded.rich_tracebacks is False
        assert loaded.device_serial == "10.0.0.42:4555"

    def test_load_from_os_environment(self, monkeypatch):
        """Validates that environment variables override defaults."""
        monkeypatch.setenv("GEMINI_API_KEY", "env_override_key_999")
        monkeypatch.setenv("GEMINI_MODEL", "gemini-2.5-flash-test")
        monkeypatch.setenv("ADB_DEVICE_IP", "172.16.0.5")
        monkeypatch.setenv("ADB_DEVICE_PORT", "6555")
        monkeypatch.setenv("MAX_AGENT_STEPS", "15")
        monkeypatch.setenv("ACTION_DELAY_SECONDS", "0.5")

        cfg = load_config()
        assert cfg.gemini_api_key == "env_override_key_999"
        assert cfg.gemini_model == "gemini-2.5-flash-test"
        assert cfg.adb_device_ip == "172.16.0.5"
        assert cfg.adb_device_port == 6555
        assert cfg.max_agent_steps == 15
        assert cfg.action_delay_seconds == 0.5

    def test_update_setting_types_and_values(self):
        """Tests updating individual settings dynamically with type coercion."""
        cfg = Settings()
        cfg.update_setting("max_agent_steps", "40")
        assert cfg.max_agent_steps == 40

        cfg.update_setting("action_delay_seconds", "3.2")
        assert cfg.action_delay_seconds == 3.2

        cfg.update_setting("rich_tracebacks", "false")
        assert cfg.rich_tracebacks is False

        cfg.update_setting("gemini_model", "gemini-2.5-flash")
        assert cfg.gemini_model == "gemini-2.5-flash"

        cfg.update_setting("adb_device_ip", "192.168.0.200")
        assert cfg.adb_device_ip == "192.168.0.200"
        assert cfg.device_serial == "192.168.0.200:5555"

    def test_update_setting_unknown_key_raises(self):
        """Updating an unknown setting must raise KeyError."""
        cfg = Settings()
        with pytest.raises(KeyError, match="Unknown configuration key"):
            cfg.update_setting("non_existent_key", "value")

    def test_numeric_bounds_validation(self):
        """Validates numeric boundary limits."""
        with pytest.raises(ValidationError):
            Settings(adb_device_port=70000)  # > 65535

        with pytest.raises(ValidationError):
            Settings(adb_device_port=0)  # < 1

        with pytest.raises(ValidationError):
            Settings(gemini_temperature=2.5)  # > 2.0

        with pytest.raises(ValidationError):
            Settings(gemini_temperature=-0.1)  # < 0.0

        with pytest.raises(ValidationError):
            Settings(max_agent_steps=0)  # < 1

        with pytest.raises(ValidationError):
            Settings(loop_detection_threshold=1)  # < 2

    def test_singleton_get_and_set_config(self):
        """Tests get_config, set_config, and reset_config singleton behavior."""
        custom_cfg = Settings(adb_device_ip="192.168.10.10", adb_device_port=8888)
        set_config(custom_cfg)

        assert get_config() is custom_cfg
        assert get_config().device_serial == "192.168.10.10:8888"

        reset = reset_config()
        assert reset is not None
