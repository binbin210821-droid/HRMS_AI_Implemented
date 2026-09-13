import logging

import pytest

from app.events.event_bus import EventBus


@pytest.mark.asyncio
async def test_publish_isolates_handler_failure_and_runs_other_handlers(caplog) -> None:
    bus = EventBus()
    completed: list[str] = []

    async def failing_handler(_payload) -> None:
        raise RuntimeError("handler failure")

    async def successful_handler(payload) -> None:
        completed.append(payload)

    bus.subscribe("test", failing_handler)
    bus.subscribe("test", successful_handler)

    with caplog.at_level(logging.ERROR, logger="app.events.event_bus"):
        await bus.publish("test", "payload")

    assert completed == ["payload"]
    assert "event_handler_failed" in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.asyncio
async def test_subscribe_is_idempotent_and_unsubscribe_removes_handler() -> None:
    bus = EventBus()
    calls: list[str] = []

    async def handler(_payload) -> None:
        calls.append("called")

    bus.subscribe("test", handler)
    bus.subscribe("test", handler)
    await bus.publish("test", None)

    assert calls == ["called"]

    bus.unsubscribe("test", handler)
    await bus.publish("test", None)
    assert calls == ["called"]
