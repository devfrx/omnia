"""O.M.N.I.A. — Async event bus for inter-component communication."""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any, Callable, Coroutine

from loguru import logger

# ---------------------------------------------------------------------------
# Well-known event names
# ---------------------------------------------------------------------------

EVENT_LLM_RESPONSE: str = "llm.response"
EVENT_STT_RESULT: str = "stt.result"
EVENT_TTS_START: str = "tts.start"
EVENT_PLUGIN_LOADED: str = "plugin.loaded"
EVENT_TOOL_CALLED: str = "tool.called"
EVENT_ERROR: str = "error"

# Type alias for async handlers
AsyncHandler = Callable[..., Coroutine[Any, Any, None]]


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class EventBus:
    """A lightweight async event bus.

    Handlers are async callables. When an event is emitted every registered
    handler for that event is called concurrently via ``asyncio.gather``.
    """

    def __init__(self) -> None:
        self._handlers: dict[str, list[AsyncHandler]] = defaultdict(list)

    # -- public API ---------------------------------------------------------

    def subscribe(self, event_name: str, handler: AsyncHandler) -> None:
        """Register *handler* for *event_name*.

        Args:
            event_name: The event to listen for.
            handler: An async callable to invoke when the event fires.
        """
        self._handlers[event_name].append(handler)
        logger.debug(
            "Subscribed {} to '{}'", handler.__qualname__, event_name
        )

    def unsubscribe(self, event_name: str, handler: AsyncHandler) -> None:
        """Remove *handler* from *event_name*.

        Args:
            event_name: The event to stop listening for.
            handler: The handler previously registered via ``subscribe``.
        """
        try:
            self._handlers[event_name].remove(handler)
            logger.debug(
                "Unsubscribed {} from '{}'",
                handler.__qualname__,
                event_name,
            )
        except ValueError:
            logger.warning(
                "Handler {} was not subscribed to '{}'",
                handler.__qualname__,
                event_name,
            )

    def once(self, event_name: str, handler: AsyncHandler) -> None:
        """Register *handler* so it fires exactly once then auto-unsubscribes.

        Args:
            event_name: The event to listen for.
            handler: An async callable invoked a single time.
        """

        async def _wrapper(**kwargs: Any) -> None:
            self.unsubscribe(event_name, _wrapper)
            await handler(**kwargs)

        # Preserve qualname for logging
        _wrapper.__qualname__ = f"{handler.__qualname__}[once]"
        self.subscribe(event_name, _wrapper)

    async def emit(self, event_name: str, **kwargs: Any) -> None:
        """Fire *event_name*, calling all registered handlers concurrently.

        Args:
            event_name: The event to fire.
            **kwargs: Keyword arguments forwarded to every handler.
        """
        handlers = list(self._handlers.get(event_name, []))
        if not handlers:
            logger.debug("Event '{}' fired — no handlers", event_name)
            return

        logger.debug(
            "Event '{}' fired — {} handler(s)",
            event_name,
            len(handlers),
        )

        results = await asyncio.gather(
            *(h(**kwargs) for h in handlers),
            return_exceptions=True,
        )

        for result in results:
            if isinstance(result, BaseException):
                logger.error(
                    "Handler error on '{}': {}", event_name, result
                )
