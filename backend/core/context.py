"""O.M.N.I.A. — Application context (lightweight DI container).

The ``AppContext`` holds references to every shared service so they can be
injected where needed without relying on module-level globals.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import async_sessionmaker

from backend.core.config import OmniaConfig
from backend.core.event_bus import EventBus


@dataclass
class AppContext:
    """Typed container for all shared runtime services.

    Created once during application startup via :func:`create_context` and
    stored on ``app.state.context``.
    """

    config: OmniaConfig
    event_bus: EventBus
    db: async_sessionmaker | None = None

    # TODO: Replace ``Any`` with concrete types once services are implemented.
    plugin_manager: Any = None  # TODO: type as PluginManager
    llm_service: Any = None     # TODO: type as LLMService
    stt_service: Any = None     # TODO: type as STTService
    tts_service: Any = None     # TODO: type as TTSService


def create_context(config: OmniaConfig) -> AppContext:
    """Create a fresh application context.

    Args:
        config: The validated OMNIA configuration.

    Returns:
        An ``AppContext`` wired with the config and a new ``EventBus``.
    """
    return AppContext(
        config=config,
        event_bus=EventBus(),
    )
