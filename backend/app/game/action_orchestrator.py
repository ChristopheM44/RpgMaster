from __future__ import annotations

import uuid
from typing import Any, Optional

from app.game.async_tasks import create_logged_task
from app.game.event_bus import EventType


class ActionOrchestrator:
    """Publishes visible action side effects: events, persistence, and TTS."""

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
        db: Optional[Any],
    ) -> None:
        narration_id = str(uuid.uuid4())
        await self._event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
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

        create_logged_task(
            self._tts_router.synthesize_and_broadcast(
                narration_text,
                session_id,
                narration_id,
            ),
            "action_pipeline.tts_narration",
        )
