"""Tests for backend.core.event_bus."""

from __future__ import annotations

import pytest

from backend.core.event_bus import EventBus


async def test_subscribe_and_emit(event_bus: EventBus) -> None:
    received: list[dict] = []

    async def handler(**kwargs):
        received.append(kwargs)

    event_bus.subscribe("test.event", handler)
    await event_bus.emit("test.event", data="hello")

    assert len(received) == 1
    assert received[0]["data"] == "hello"


async def test_emit_calls_multiple_handlers(event_bus: EventBus) -> None:
    calls: list[str] = []

    async def handler_a(**kwargs):
        calls.append("a")

    async def handler_b(**kwargs):
        calls.append("b")

    event_bus.subscribe("multi", handler_a)
    event_bus.subscribe("multi", handler_b)
    await event_bus.emit("multi")

    assert sorted(calls) == ["a", "b"]


async def test_unsubscribe_removes_handler(event_bus: EventBus) -> None:
    calls: list[int] = []

    async def handler(**kwargs):
        calls.append(1)

    event_bus.subscribe("unsub.test", handler)
    await event_bus.emit("unsub.test")
    assert len(calls) == 1

    event_bus.unsubscribe("unsub.test", handler)
    await event_bus.emit("unsub.test")
    assert len(calls) == 1  # no new call


async def test_once_fires_only_once(event_bus: EventBus) -> None:
    calls: list[int] = []

    async def handler(**kwargs):
        calls.append(1)

    event_bus.once("once.event", handler)

    await event_bus.emit("once.event")
    await event_bus.emit("once.event")

    assert len(calls) == 1


async def test_emit_no_handlers_does_not_error(event_bus: EventBus) -> None:
    # Should complete without raising
    await event_bus.emit("no.handlers.here")


async def test_handler_exception_is_caught(event_bus: EventBus) -> None:
    """A handler that raises should not crash emit; error is logged."""

    async def bad_handler(**kwargs):
        raise ValueError("boom")

    async def good_handler(**kwargs):
        pass

    event_bus.subscribe("error.event", bad_handler)
    event_bus.subscribe("error.event", good_handler)

    # Should not raise even though bad_handler explodes
    await event_bus.emit("error.event")


async def test_emit_passes_kwargs(event_bus: EventBus) -> None:
    received: list[dict] = []

    async def handler(**kwargs):
        received.append(kwargs)

    event_bus.subscribe("kwargs.test", handler)
    await event_bus.emit("kwargs.test", x=1, y="two", z=[3])

    assert received[0] == {"x": 1, "y": "two", "z": [3]}


async def test_unsubscribe_nonexistent_handler(event_bus: EventBus) -> None:
    """Unsubscribing a handler that was never subscribed emits a warning, no crash."""

    async def handler(**kwargs):
        pass

    # Should not raise
    event_bus.unsubscribe("nope", handler)
