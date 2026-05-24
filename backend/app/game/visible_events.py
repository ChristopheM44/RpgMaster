"""Shared helpers for narrative and dialogue WebSocket entries."""
from __future__ import annotations

from typing import Any, Optional

from app.game.event_bus import EventType


def visible_event_type(entry_kind: Optional[str]) -> str:
    """Return the canonical event type for a visible narrative-log entry."""
    return EventType.DIALOGUE if entry_kind == "dialogue" else EventType.NARRATION


async def publish_visible_entry(
    event_bus_instance: Any,
    session_id: str,
    payload: dict[str, Any],
    *,
    source: str,
) -> None:
    """Publish a visible entry using the canonical dialogue/narration split."""
    entry_kind = payload.get("entry_kind")
    await event_bus_instance.publish_to_session(
        session_id,
        visible_event_type(str(entry_kind) if entry_kind is not None else None),
        payload,
        source=source,
    )
