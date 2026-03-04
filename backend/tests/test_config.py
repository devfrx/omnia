"""Tests for backend.core.config."""

from __future__ import annotations

from pathlib import Path

from backend.core.config import (
    PROJECT_ROOT,
    OmniaConfig,
    load_config,
)


def test_load_config_returns_omnia_config(config: OmniaConfig) -> None:
    assert isinstance(config, OmniaConfig)


def test_all_sections_exist(config: OmniaConfig) -> None:
    assert config.server is not None
    assert config.llm is not None
    assert config.stt is not None
    assert config.tts is not None
    assert config.database is not None
    assert config.plugins is not None
    assert config.home_assistant is not None
    assert config.mqtt is not None
    assert config.voice is not None
    assert config.ui is not None


def test_server_port(config: OmniaConfig) -> None:
    assert config.server.port == 8000


def test_server_host(config: OmniaConfig) -> None:
    assert config.server.host == "0.0.0.0"


def test_llm_provider(config: OmniaConfig) -> None:
    assert config.llm.provider == "openai-compatible"


def test_llm_base_url(config: OmniaConfig) -> None:
    assert config.llm.base_url == "http://localhost:1234"


def test_llm_model(config: OmniaConfig) -> None:
    assert config.llm.model == "qwen2.5-14b-instruct"


def test_llm_temperature(config: OmniaConfig) -> None:
    assert config.llm.temperature == 0.7


def test_llm_max_tokens(config: OmniaConfig) -> None:
    assert config.llm.max_tokens == 4096


def test_system_prompt_file_is_absolute(config: OmniaConfig) -> None:
    """system_prompt_file should be resolved to an absolute path."""
    prompt_path = Path(config.llm.system_prompt_file)
    assert prompt_path.is_absolute()
    assert str(PROJECT_ROOT) in config.llm.system_prompt_file


def test_database_url(config: OmniaConfig) -> None:
    assert "sqlite+aiosqlite" in config.database.url


def test_plugins_enabled_list(config: OmniaConfig) -> None:
    enabled = config.plugins.enabled
    assert isinstance(enabled, list)
    assert "system_info" in enabled
    assert "pc_automation" in enabled


def test_stt_defaults(config: OmniaConfig) -> None:
    assert config.stt.engine == "faster-whisper"
    assert config.stt.model == "large-v3"
    assert config.stt.language == "it"


def test_tts_defaults(config: OmniaConfig) -> None:
    assert config.tts.engine == "piper"
    assert config.tts.sample_rate == 22050


def test_voice_defaults(config: OmniaConfig) -> None:
    assert config.voice.wake_word == "omnia"
    assert config.voice.activation_mode == "push_to_talk"


def test_ui_defaults(config: OmniaConfig) -> None:
    assert config.ui.theme == "dark"
    assert config.ui.language == "it"


def test_load_config_missing_file_uses_defaults() -> None:
    """When the config file does not exist, defaults + env vars are used."""
    cfg = load_config(Path("/nonexistent/path.yaml"))
    assert isinstance(cfg, OmniaConfig)
    # Defaults should still be valid
    assert cfg.server.port == 8000
