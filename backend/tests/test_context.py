"""Tests for backend.core.context."""

from __future__ import annotations

from backend.core.config import OmniaConfig
from backend.core.context import AppContext, create_context
from backend.core.event_bus import EventBus


def test_create_context_returns_app_context(config: OmniaConfig) -> None:
    ctx = create_context(config)
    assert isinstance(ctx, AppContext)


def test_create_context_has_config_and_event_bus(config: OmniaConfig) -> None:
    ctx = create_context(config)
    assert ctx.config is config
    assert isinstance(ctx.event_bus, EventBus)


def test_optional_fields_default_to_none(config: OmniaConfig) -> None:
    ctx = create_context(config)
    assert ctx.db is None
    assert ctx.plugin_manager is None
    assert ctx.llm_service is None
    assert ctx.stt_service is None
    assert ctx.tts_service is None
