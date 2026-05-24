"""Shared helpers for narrative and dialogue WebSocket entries."""
from __future__ import annotations

import re
from typing import Any, Optional

from app.game.event_bus import EventType


def visible_event_type(entry_kind: Optional[str]) -> str:
    """Return the canonical event type for a visible narrative-log entry."""
    return EventType.DIALOGUE if entry_kind == "dialogue" else EventType.NARRATION


def strip_visible_speaker_prefix(text: str, speaker: Optional[str]) -> str:
    """Remove redundant leading speaker names from visible dialogue text.

    The UI already renders the speaker label. LLMs often start a line with
    "Syndra ..." or "Syndra Silvane: ...", which reads as a duplicate once the
    speaker metadata is present.
    """
    cleaned = str(text or "").lstrip()
    speaker_name = str(speaker or "").strip()
    if not cleaned or not speaker_name:
        return text

    names = [speaker_name]
    first_name = speaker_name.split()[0] if speaker_name.split() else ""
    if first_name and first_name != speaker_name:
        names.append(first_name)

    for name in sorted(names, key=len, reverse=True):
        match = re.match(
            rf"^{re.escape(name)}\s*(?:[:：,\-–—]\s*|\s+)(.+)$",
            cleaned,
            flags=re.IGNORECASE | re.DOTALL,
        )
        if match:
            return match.group(1)
    return text


async def publish_visible_entry(
    event_bus_instance: Any,
    session_id: str,
    payload: dict[str, Any],
    *,
    source: str,
) -> None:
    """Publish a visible entry using the canonical dialogue/narration split."""
    payload = dict(payload)
    entry_kind = payload.get("entry_kind")
    if entry_kind == "dialogue" and isinstance(payload.get("text"), str):
        payload["text"] = strip_visible_speaker_prefix(
            payload["text"],
            str(payload.get("speaker") or ""),
        )
    await event_bus_instance.publish_to_session(
        session_id,
        visible_event_type(str(entry_kind) if entry_kind is not None else None),
        payload,
        source=source,
    )
