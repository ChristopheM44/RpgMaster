"""In-process event bus — pub/sub via asyncio.Queue.

Allows any game component (GM agent, turn manager, engine resolver, etc.) to
publish :class:`GameEvent` objects and any number of subscribers (typically
one per active WebSocket connection) to consume them independently.

Design decisions:
- One :class:`asyncio.Queue` per subscriber.  This avoids head-of-line blocking:
  a slow consumer cannot stall others.
- All queues for a session receive every event published to that session.
- Phase 1 (solo): in-process only.  Phase 2+: swap out for Redis pub/sub
  without touching the rest of the codebase.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from enum import auto
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Event types
# ---------------------------------------------------------------------------


class EventType(str):
    """All event types that can flow through the bus.

    Using plain string constants (not Enum) keeps JSON serialisation trivial
    and lets new types be added without touching this file.
    """

    # Narrative flow
    NARRATION = "narration"
    DIALOGUE = "dialogue"

    # Mechanical results
    ROLL_RESULT = "roll_result"
    DAMAGE_APPLIED = "damage_applied"
    CONDITION_CHANGED = "condition_changed"
    HP_CHANGED = "hp_changed"

    # Turn / combat lifecycle
    TURN_START = "turn_start"
    TURN_END = "turn_end"
    ROUND_START = "round_start"
    COMBAT_START = "combat_start"
    COMBAT_END = "combat_end"

    # Session lifecycle
    PHASE_CHANGE = "phase_change"
    SESSION_STATE = "session_state"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"

    # Audio TTS
    AUDIO = "audio"

    # Errors
    ERROR = "error"


# ---------------------------------------------------------------------------
# GameEvent
# ---------------------------------------------------------------------------


class GameEvent(BaseModel):
    """A single event flowing through the bus.

    Attributes:
        event_type: One of the :class:`EventType` string constants.
        session_id: The session this event belongs to.
        payload: Arbitrary data; structure depends on *event_type*.
        timestamp: UTC creation time (auto-set on instantiation).
        source: Optional identifier of the component that produced the event.
    """

    event_type: str
    session_id: str
    payload: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: Optional[str] = None

    model_config = {"ser_json_timedelta": "iso8601"}


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class EventBus:
    """In-process pub/sub broker for :class:`GameEvent` objects.

    Usage::

        bus = EventBus()

        # Subscriber (e.g. WebSocket handler)
        queue = bus.subscribe("session-abc")
        event = await queue.get()          # blocks until an event arrives

        # Publisher (e.g. GM agent)
        await bus.publish(GameEvent(
            event_type=EventType.NARRATION,
            session_id="session-abc",
            payload={"text": "You enter a dark forest."},
        ))

        # Cleanup
        bus.unsubscribe("session-abc", queue)
    """

    def __init__(self) -> None:
        # session_id -> list of subscriber queues
        self._subscribers: Dict[str, List[asyncio.Queue]] = {}

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(self, session_id: str, maxsize: int = 0) -> asyncio.Queue:
        """Register a new subscriber for *session_id*.

        Args:
            session_id: The session to subscribe to.
            maxsize: Maximum queue depth (0 = unlimited).  Pass a small
                     positive integer to apply back-pressure on slow consumers.

        Returns:
            A new :class:`asyncio.Queue` that will receive all subsequent
            events published to *session_id*.
        """
        queue: asyncio.Queue = asyncio.Queue(maxsize=maxsize)
        self._subscribers.setdefault(session_id, []).append(queue)
        logger.debug(
            "EventBus: new subscriber for session %s (%d total).",
            session_id,
            len(self._subscribers[session_id]),
        )
        return queue

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        """Remove a subscriber queue.

        Safe to call even if the queue is not registered.
        """
        subscribers = self._subscribers.get(session_id, [])
        try:
            subscribers.remove(queue)
        except ValueError:
            pass
        if not subscribers:
            self._subscribers.pop(session_id, None)
        logger.debug("EventBus: subscriber removed for session %s.", session_id)

    def subscriber_count(self, session_id: str) -> int:
        """Return the number of active subscribers for *session_id*."""
        return len(self._subscribers.get(session_id, []))

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(self, event: GameEvent) -> None:
        """Deliver *event* to all subscribers of ``event.session_id``.

        Drops the event silently if there are no subscribers.
        Drops onto a specific subscriber's queue silently if that queue is
        full (avoids blocking the publisher on a slow consumer).
        """
        subscribers = self._subscribers.get(event.session_id, [])
        if not subscribers:
            logger.debug(
                "EventBus: no subscribers for session %s, dropping %s.",
                event.session_id,
                event.event_type,
            )
            return

        for queue in list(subscribers):  # snapshot to avoid mutation during iteration
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                logger.warning(
                    "EventBus: queue full for session %s subscriber, dropping %s.",
                    event.session_id,
                    event.event_type,
                )

        logger.debug(
            "EventBus: published %s to %d subscriber(s) for session %s.",
            event.event_type,
            len(subscribers),
            event.session_id,
        )

    async def publish_to_session(
        self,
        session_id: str,
        event_type: str,
        payload: Dict[str, Any],
        source: Optional[str] = None,
    ) -> None:
        """Convenience wrapper to build and publish a :class:`GameEvent`.

        Args:
            session_id: Target session.
            event_type: One of the :class:`EventType` constants.
            payload: Event data.
            source: Optional originator tag.
        """
        event = GameEvent(
            event_type=event_type,
            session_id=session_id,
            payload=payload,
            source=source,
        )
        await self.publish(event)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

#: Shared event bus instance — import and use directly.
event_bus = EventBus()
