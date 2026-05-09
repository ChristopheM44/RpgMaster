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
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Protocol

from pydantic import BaseModel, Field

from app.config import settings

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
    COMBAT_ACTION = "combat_action"
    COMBATANT_MOVED = "combatant_moved"
    COMBATANT_STATUS_CHANGED = "combatant_status_changed"
    COMBATANT_REMOVED = "combatant_removed"

    # Session lifecycle
    PHASE_CHANGE = "phase_change"
    SESSION_STATE = "session_state"
    PLAYER_JOINED = "player_joined"
    PLAYER_LEFT = "player_left"

    # Audio TTS
    AUDIO = "audio"

    # Agent activity
    AI_THINKING = "ai_thinking"

    # Character updates
    SPELL_SLOT_UPDATED = "spell_slot_updated"
    EQUIPMENT_UPDATED = "equipment_updated"
    HIT_DICE_UPDATED = "hit_dice_updated"
    DEATH_SAVE_UPDATED = "death_save_updated"

    # World state (journal, quests, chronicle)
    JOURNAL_UPDATED = "journal_updated"
    QUEST_UPDATED = "quest_updated"
    CHRONICLE_UPDATED = "chronicle_updated"
    SCENE_LAYOUT_CHANGED = "scene_layout_changed"

    # Errors
    ERROR = "error"


BACKPRESSURE_ERROR_CODE = "backpressure"


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
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    source: Optional[str] = None

    model_config = {"ser_json_timedelta": "iso8601"}


# ---------------------------------------------------------------------------
# EventBus
# ---------------------------------------------------------------------------


class EventBusProtocol(Protocol):
    def subscribe(self, session_id: str, maxsize: Optional[int] = None) -> asyncio.Queue:
        ...

    def unsubscribe(self, session_id: str, queue: asyncio.Queue) -> None:
        ...

    def subscriber_count(self, session_id: str) -> int:
        ...

    async def publish(self, event: GameEvent) -> None:
        ...

    async def publish_to_session(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
        source: Optional[str] = None,
    ) -> None:
        ...


class InProcessEventBus:
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

    def __init__(self, default_maxsize: int = 256) -> None:
        # session_id -> list of subscriber queues
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._default_maxsize = max(0, int(default_maxsize))
        self._dropped_events: dict[str, int] = {}
        self._max_queue_size: dict[str, int] = {}

    # ------------------------------------------------------------------
    # Subscription management
    # ------------------------------------------------------------------

    def subscribe(self, session_id: str, maxsize: Optional[int] = None) -> asyncio.Queue:
        """Register a new subscriber for *session_id*.

        Args:
            session_id: The session to subscribe to.
            maxsize: Maximum queue depth. None uses the bus default.

        Returns:
            A new :class:`asyncio.Queue` that will receive all subsequent
            events published to *session_id*.
        """
        effective_maxsize = self._default_maxsize if maxsize is None else max(0, int(maxsize))
        queue: asyncio.Queue = asyncio.Queue(maxsize=effective_maxsize)
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

    def dropped_event_count(self, session_id: Optional[str] = None) -> int:
        """Return dropped events for one session, or total dropped events."""
        if session_id is not None:
            return self._dropped_events.get(session_id, 0)
        return sum(self._dropped_events.values())

    def max_queue_size_observed(self, session_id: Optional[str] = None) -> int:
        """Return the maximum queue depth observed."""
        if session_id is not None:
            return self._max_queue_size.get(session_id, 0)
        return max(self._max_queue_size.values(), default=0)

    def stats(self, session_id: Optional[str] = None) -> dict[str, int]:
        """Small in-process metrics snapshot for tests and diagnostics."""
        if session_id is not None:
            return {
                "subscribers": self.subscriber_count(session_id),
                "dropped_events": self.dropped_event_count(session_id),
                "max_queue_size": self.max_queue_size_observed(session_id),
            }
        return {
            "subscribers": sum(len(items) for items in self._subscribers.values()),
            "dropped_events": self.dropped_event_count(),
            "max_queue_size": self.max_queue_size_observed(),
        }

    # ------------------------------------------------------------------
    # Publishing
    # ------------------------------------------------------------------

    async def publish(self, event: GameEvent) -> None:
        """Deliver *event* to all subscribers of ``event.session_id``.

        Drops the event silently if there are no subscribers.
        A full subscriber queue receives a terminal backpressure error after
        its stale backlog is discarded. The WebSocket relay then closes it.
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
                self._max_queue_size[event.session_id] = max(
                    self._max_queue_size.get(event.session_id, 0),
                    queue.qsize(),
                )
            except asyncio.QueueFull:
                self._dropped_events[event.session_id] = (
                    self._dropped_events.get(event.session_id, 0) + 1
                )
                logger.warning(
                    "EventBus: queue full for session %s subscriber, dropping %s.",
                    event.session_id,
                    event.event_type,
                )
                self._replace_backlog_with_backpressure_error(queue, event.session_id)

        logger.debug(
            "EventBus: published %s to %d subscriber(s) for session %s.",
            event.event_type,
            len(subscribers),
            event.session_id,
        )

    def _replace_backlog_with_backpressure_error(
        self,
        queue: asyncio.Queue,
        session_id: str,
    ) -> None:
        while True:
            try:
                queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        try:
            queue.put_nowait(
                GameEvent(
                    event_type=EventType.ERROR,
                    session_id=session_id,
                    payload={
                        "message": "Client WebSocket trop lent; reconnexion requise.",
                        "code": BACKPRESSURE_ERROR_CODE,
                    },
                    source="event_bus",
                )
            )
        except asyncio.QueueFull:
            logger.error(
                "EventBus: unable to enqueue backpressure error for session %s.",
                session_id,
            )

    async def publish_to_session(
        self,
        session_id: str,
        event_type: str,
        payload: dict[str, Any],
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
event_bus = InProcessEventBus(default_maxsize=settings.ws_event_queue_size)

# Backward-compatible alias used by existing tests and callers.
EventBus = InProcessEventBus
