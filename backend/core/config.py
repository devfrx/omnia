"""O.M.N.I.A. — Configuration system.

Loads configuration from ``config/default.yaml`` with environment-variable
overrides (prefix ``OMNIA_``, nested via double-underscore).  Uses Pydantic
Settings v2 for validation and env parsing.
"""

from __future__ import annotations

import functools
from pathlib import Path
from typing import Any

import yaml
from loguru import logger
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
"""Absolute path to the OMNIA project root (two levels up from core/)."""

DEFAULT_CONFIG_PATH: Path = PROJECT_ROOT / "config" / "default.yaml"


def _load_yaml(path: Path) -> dict[str, Any]:
    """Read a YAML file and return its contents as a dict."""
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return data if isinstance(data, dict) else {}


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ServerConfig(BaseSettings):
    """HTTP server configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_SERVER__")

    host: str = "0.0.0.0"
    port: int = 8000
    reload: bool = True
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://localhost:3000",
        ]
    )


class LLMConfig(BaseSettings):
    """LLM provider configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_LLM__")

    provider: str = "openai-compatible"
    base_url: str = "http://localhost:1234"
    model: str = "qwen2.5-14b-instruct"
    temperature: float = 0.7
    max_tokens: int = 4096
    system_prompt_file: str = "config/system_prompt.md"


class STTConfig(BaseSettings):
    """Speech-to-text configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_STT__")

    engine: str = "faster-whisper"
    model: str = "large-v3"
    language: str = "it"
    device: str = "cuda"
    compute_type: str = "float16"
    vad_filter: bool = True
    vad_threshold: float = 0.5


class TTSConfig(BaseSettings):
    """Text-to-speech configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_TTS__")

    engine: str = "piper"
    voice: str = "it_IT-riccardo-x_low"
    sample_rate: int = 22050


class DatabaseConfig(BaseSettings):
    """Database configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_DATABASE__")

    url: str = "sqlite+aiosqlite:///data/omnia.db"


class PluginsConfig(BaseSettings):
    """Plugin configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_PLUGINS__")

    enabled: list[str] = Field(
        default_factory=lambda: [
            "system_info",
            "pc_automation",
            "web_search",
            "calendar",
        ]
    )


class HomeAssistantConfig(BaseSettings):
    """Home Assistant integration configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_HOME_ASSISTANT__")

    url: str = "http://homeassistant.local:8123"
    token: str = ""


class MQTTConfig(BaseSettings):
    """MQTT broker configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_MQTT__")

    broker: str = "localhost"
    port: int = 1883
    username: str = ""
    password: str = ""


class VoiceConfig(BaseSettings):
    """Voice interaction configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_VOICE__")

    wake_word: str = "omnia"
    activation_mode: str = "push_to_talk"
    silence_timeout_ms: int = 1500


class UIConfig(BaseSettings):
    """UI configuration."""

    model_config = SettingsConfigDict(env_prefix="OMNIA_UI__")

    theme: str = "dark"
    global_hotkey: str = "Ctrl+Shift+O"
    language: str = "it"


# ---------------------------------------------------------------------------
# Top-level config
# ---------------------------------------------------------------------------


class OmniaConfig(BaseSettings):
    """Root configuration aggregating every sub-section."""

    model_config = SettingsConfigDict(
        env_prefix="OMNIA_",
        env_nested_delimiter="__",
    )

    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    stt: STTConfig = Field(default_factory=STTConfig)
    tts: TTSConfig = Field(default_factory=TTSConfig)
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    plugins: PluginsConfig = Field(default_factory=PluginsConfig)
    home_assistant: HomeAssistantConfig = Field(
        default_factory=HomeAssistantConfig
    )
    mqtt: MQTTConfig = Field(default_factory=MQTTConfig)
    voice: VoiceConfig = Field(default_factory=VoiceConfig)
    ui: UIConfig = Field(default_factory=UIConfig)

    @model_validator(mode="after")
    def _resolve_system_prompt_path(self) -> "OmniaConfig":
        """Resolve ``system_prompt_file`` relative to the project root."""
        raw = self.llm.system_prompt_file
        resolved = PROJECT_ROOT / raw
        object.__setattr__(self.llm, "system_prompt_file", str(resolved))
        return self


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_config(path: Path | None = None) -> OmniaConfig:
    """Load configuration from a YAML file and apply env-var overrides.

    Args:
        path: Path to the YAML config file.  Defaults to
              ``config/default.yaml`` relative to the project root.

    Returns:
        A fully validated ``OmniaConfig`` instance.
    """
    config_path = path or DEFAULT_CONFIG_PATH

    if config_path.exists():
        raw = _load_yaml(config_path)
        logger.debug("Loaded config from {}", config_path)
    else:
        raw = {}
        logger.warning(
            "Config file {} not found — using defaults + env vars",
            config_path,
        )

    return OmniaConfig(**raw)


@functools.lru_cache(maxsize=1)
def get_config() -> OmniaConfig:
    """Return a cached singleton of the default configuration.

    The config is loaded once (from the default YAML path) and then reused
    for subsequent calls.
    """
    return load_config()
