"""Tests for game/event_bus.py."""
from __future__ import annotations

import asyncio

import pytest

from app.game.event_bus import EventBus, EventType, GameEvent


@pytest.fixture
def bus() -> EventBus:
    return EventBus()


# ---------------------------------------------------------------------------
# subscribe / unsubscribe
# ---------------------------------------------------------------------------


class TestSubscription:
    async def test_subscribe_returns_queue(self, bus: EventBus) -> None:
        q = bus.subscribe("session-1")
        assert isinstance(q, asyncio.Queue)

    async def test_subscriber_count(self, bus: EventBus) -> None:
        bus.subscribe("session-1")
        bus.subscribe("session-1")
        assert bus.subscriber_count("session-1") == 2

    async def test_unsubscribe_reduces_count(self, bus: EventBus) -> None:
        q = bus.subscribe("session-1")
        bus.unsubscribe("session-1", q)
        assert bus.subscriber_count("session-1") == 0

    async def test_unsubscribe_unknown_queue_is_noop(self, bus: EventBus) -> None:
        other_queue: asyncio.Queue = asyncio.Queue()
        bus.unsubscribe("session-1", other_queue)  # should not raise

    async def test_unsubscribe_last_removes_session_key(self, bus: EventBus) -> None:
        q = bus.subscribe("session-1")
        bus.unsubscribe("session-1", q)
        assert bus.subscriber_count("session-1") == 0


# ---------------------------------------------------------------------------
# publish
# ---------------------------------------------------------------------------


class TestPublish:
    async def test_published_event_received_by_subscriber(self, bus: EventBus) -> None:
        q = bus.subscribe("session-1")
        event = GameEvent(
            event_type=EventType.NARRATION,
            session_id="session-1",
            payload={"text": "Hello"},
        )
        await bus.publish(event)
        received = q.get_nowait()
        assert received is event

    async def test_all_subscribers_receive_event(self, bus: EventBus) -> None:
        q1 = bus.subscribe("session-1")
        q2 = bus.subscribe("session-1")
        event = GameEvent(event_type=EventType.TURN_START, session_id="session-1", payload={})
        await bus.publish(event)
        assert q1.get_nowait() is event
        assert q2.get_nowait() is event

    async def test_publish_to_different_session_not_received(self, bus: EventBus) -> None:
        q = bus.subscribe("session-A")
        event = GameEvent(event_type=EventType.NARRATION, session_id="session-B", payload={})
        await bus.publish(event)
        assert q.empty()

    async def test_publish_no_subscribers_does_not_raise(self, bus: EventBus) -> None:
        event = GameEvent(
            event_type=EventType.NARRATION, session_id="ghost-session", payload={}
        )
        await bus.publish(event)  # should not raise

    async def test_full_queue_drops_event_silently(self, bus: EventBus) -> None:
        q = bus.subscribe("session-1", maxsize=1)
        event = GameEvent(event_type=EventType.NARRATION, session_id="session-1", payload={})
        await bus.publish(event)  # fills the queue
        await bus.publish(event)  # should be dropped silently, not raise
        assert q.qsize() == 1  # still only one item


# ---------------------------------------------------------------------------
# publish_to_session (convenience wrapper)
# ---------------------------------------------------------------------------


class TestPublishToSession:
    async def test_convenience_wrapper_delivers_event(self, bus: EventBus) -> None:
        q = bus.subscribe("session-1")
        await bus.publish_to_session(
            "session-1",
            EventType.PHASE_CHANGE,
            {"phase": "combat"},
            source="test",
        )
        event: GameEvent = q.get_nowait()
        assert event.event_type == EventType.PHASE_CHANGE
        assert event.session_id == "session-1"
        assert event.payload["phase"] == "combat"
        assert event.source == "test"

    async def test_timestamp_is_set(self, bus: EventBus) -> None:
        q = bus.subscribe("session-1")
        await bus.publish_to_session("session-1", EventType.NARRATION, {})
        event: GameEvent = q.get_nowait()
        assert event.timestamp is not None


# ---------------------------------------------------------------------------
# GameEvent serialisation
# ---------------------------------------------------------------------------


class TestGameEventModel:
    def test_model_dump_is_json_serialisable(self) -> None:
        import json

        event = GameEvent(
            event_type=EventType.ROLL_RESULT,
            session_id="s1",
            payload={"dice": "2d6", "total": 9},
        )
        dumped = event.model_dump(mode="json")
        # Should not raise
        json.dumps(dumped)
        assert dumped["event_type"] == EventType.ROLL_RESULT
        assert dumped["payload"]["total"] == 9
