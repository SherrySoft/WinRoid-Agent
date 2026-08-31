"""
Configuration and environment management for Android Gemini Agent.
Loads configuration from .env and environment variables.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, Optional, Union

from dotenv import load_dotenv
from pydantic import BaseModel, Field, field_validator


class Settings(BaseModel):
    """Configuration settings for Android Gemini Agent."""

    gemini_api_key: str = Field(
        default="",
        description="Google Gemini API key for Gemini 2.5 models",
    )
    gemini_model: str = Field(
        default="gemini-3.5-flash-lite",
        description="Gemini model identifier (default: gemini-3.5-flash-lite)",
    )
    gemini_temperature: float = Field(
        default=0.0,
        ge=0.0,
        le=2.0,
        description="Sampling temperature for Gemini decision engine",
    )
    adb_device_ip: str = Field(
        default="192.168.1.100",
        description="Target Android device IP for wireless ADB",
    )
    adb_device_port: int = Field(
        default=5555,
        ge=1,
        le=65535,
        description="Target Android device connection port",
    )
    adb_timeout_seconds: float = Field(
        default=10.0,
        gt=0.0,
        description="Timeout for ADB network and shell commands in seconds",
    )
    max_agent_steps: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Maximum turns allowed for an agent task",
    )
    action_delay_seconds: float = Field(
        default=1.0,
        ge=0.0,
        description="Delay in seconds between executing actions to avoid UI instability",
    )
    loop_detection_threshold: int = Field(
        default=3,
        ge=2,
        le=10,
        description="Consecutive repetitive action/state threshold triggering loop warnings",
    )
    context_history_max_turns: int = Field(
        default=5,
        ge=1,
        le=30,
        description="Number of past turns retained in compact history",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging verbosity (DEBUG, INFO, WARNING, ERROR)",
    )
    rich_tracebacks: bool = Field(
        default=True,
        description="Enable Rich formatted tracebacks on uncaught exceptions",
    )

    @field_validator("adb_device_ip", mode="before")
    @classmethod
    def clean_ip(cls, v: Any) -> str:
        if v is None:
            return "192.168.1.100"
        return str(v).strip()

    @field_validator("gemini_model", mode="before")
    @classmethod
    def clean_model(cls, v: Any) -> str:
        if not v:
            return "gemini-2.5-flash"
        return str(v).strip()

    @property
    def device_serial(self) -> str:
        """Returns the full ADB target serial (ip:port)."""
        return f"{self.adb_device_ip}:{self.adb_device_port}"

    @property
    def is_gemini_configured(self) -> bool:
        """Checks if a non-placeholder Gemini API key is configured."""
        key = self.gemini_api_key.strip()
        return bool(key and not key.startswith("your_") and key != "dummy_key")

    def to_dict(self) -> Dict[str, Any]:
        """Dumps settings to a standard Python dictionary."""
        return self.model_dump()

    def update_setting(self, key: str, value: Any) -> None:
        """Updates a specific configuration setting by name, casting and validating as necessary."""
        key_norm = key.strip().lower()
        if not hasattr(self, key_norm):
            raise KeyError(f"Unknown configuration key '{key}'. Available keys: {list(self.model_dump().keys())}")

        # Type conversion based on field annotation
        field_info = self.__class__.model_fields.get(key_norm)
        if field_info:
            target_type = field_info.annotation
            if target_type is int:
                val = int(value)
            elif target_type is float:
                val = float(value)
            elif target_type is bool:
                if isinstance(value, str):
                    val = value.strip().lower() in ("true", "1", "yes", "on")
                else:
                    val = bool(value)
            else:
                val = str(value).strip()
        else:
            val = value

        setattr(self, key_norm, val)
        # Re-validate model
        updated = self.__class__.model_validate(self.model_dump())
        for k, v in updated.model_dump().items():
            object.__setattr__(self, k, v)


# Module-level singleton
_CONFIG_SINGLETON: Optional[Settings] = None


def load_config(env_file: Optional[Union[str, Path]] = None) -> Settings:
    """
    Loads configuration settings from environment variables and an optional .env file.
    """
    global _CONFIG_SINGLETON

    if env_file:
        load_dotenv(dotenv_path=Path(env_file), override=True)
    else:
        # Check standard paths: current dir, project root
        cwd_env = Path.cwd() / ".env"
        if cwd_env.exists():
            load_dotenv(dotenv_path=cwd_env, override=False)
        else:
            # Try 2 levels up from current file
            root_env = Path(__file__).resolve().parent.parent.parent / ".env"
            if root_env.exists():
                load_dotenv(dotenv_path=root_env, override=False)
            else:
                load_dotenv(override=False)

    # Extract settings from environment
    data: Dict[str, Any] = {}

    def get_env_val(key: str, default: Any, caster: type = str) -> Any:
        raw = os.environ.get(key.upper()) or os.environ.get(key.lower())
        if raw is None or raw == "":
            return default
        try:
            if caster is bool:
                return raw.strip().lower() in ("true", "1", "yes", "on")
            return caster(raw)
        except (ValueError, TypeError):
            return default

    data["gemini_api_key"] = os.environ.get("GEMINI_API_KEY", "")
    data["gemini_model"] = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    data["gemini_temperature"] = get_env_val("GEMINI_TEMPERATURE", 0.2, float)
    data["adb_device_ip"] = os.environ.get("ADB_DEVICE_IP", "192.168.1.100")
    data["adb_device_port"] = get_env_val("ADB_DEVICE_PORT", 5555, int)
    data["adb_timeout_seconds"] = get_env_val("ADB_TIMEOUT_SECONDS", 10.0, float)
    data["max_agent_steps"] = get_env_val("MAX_AGENT_STEPS", 20, int)
    data["action_delay_seconds"] = get_env_val("ACTION_DELAY_SECONDS", 1.0, float)
    data["loop_detection_threshold"] = get_env_val("LOOP_DETECTION_THRESHOLD", 3, int)
    data["context_history_max_turns"] = get_env_val("CONTEXT_HISTORY_MAX_TURNS", 5, int)
    data["log_level"] = os.environ.get("LOG_LEVEL", "INFO")
    data["rich_tracebacks"] = get_env_val("RICH_TRACEBACKS", True, bool)

    settings = Settings(**data)
    _CONFIG_SINGLETON = settings
    return settings


def get_config() -> Settings:
    """Returns the cached settings instance or loads it if not initialized."""
    global _CONFIG_SINGLETON
    if _CONFIG_SINGLETON is None:
        _CONFIG_SINGLETON = load_config()
    return _CONFIG_SINGLETON


def set_config(new_config: Settings) -> None:
    """Explicitly sets the active singleton configuration."""
    global _CONFIG_SINGLETON
    _CONFIG_SINGLETON = new_config


def reset_config() -> Settings:
    """Resets and re-loads configuration from environment."""
    global _CONFIG_SINGLETON
    _CONFIG_SINGLETON = None
    return get_config()
