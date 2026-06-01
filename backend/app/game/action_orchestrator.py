from __future__ import annotations

import uuid
from typing import Any

from app.game.event_bus import EventType
from app.game.visible_events import publish_visible_entry


class ActionOrchestrator:
    """Publishes visible action side effects; TTS is handled by the event hook."""

    def __init__(self, event_bus_instance: Any, *, source: str, tts_router: Any) -> None:
        self._event_bus = event_bus_instance
        self._source = source
        self._tts_router = tts_router

    async def publish_ai_thinking(self, session_id: str, thinking: bool) -> None:
        await self._event_bus.publish_to_session(
            session_id,
            EventType.AI_THINKING,
            {"agent_kind": "gm", "thinking": thinking},
            source=self._source,
        )

    async def publish_gm_narration(
        self,
        session_id: str,
        narration_text: str,
        db: Any | None,
    ) -> None:
        narration_id = str(uuid.uuid4())
        await publish_visible_entry(
            self._event_bus,
            session_id,
            {
                "text": narration_text,
                "speaker": "Maître du Jeu",
                "speaker_kind": "gm",
                "entry_kind": "narration",
                "narration_id": narration_id,
            },
            source=self._source,
        )

        if db is not None:
            from app.services.message_service import persist_narration

            await persist_narration(session_id, narration_text, "Maître du Jeu", db)
