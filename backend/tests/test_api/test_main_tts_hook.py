from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.agents.persona import PersonaVoice
from app.game.event_bus import EventType, GameEvent
from app.main import (
    _is_gm_narration_payload,
    _is_npc_dialogue_payload,
    _queue_tts_for_visible_event,
    _synthesize_npc_dialogue,
)


def test_is_gm_narration_payload_accepts_gm_speaker_kind() -> None:
    assert _is_gm_narration_payload({"speaker_kind": "gm"}) is True


def test_is_gm_narration_payload_accepts_legacy_gm_speaker() -> None:
    assert _is_gm_narration_payload({"speaker": "Maître du Jeu"}) is True


def test_is_gm_narration_payload_rejects_system_entries() -> None:
    assert _is_gm_narration_payload({"speaker_kind": "system"}) is False
    assert _is_gm_narration_payload({"speaker": "Système"}) is False


def test_is_npc_dialogue_payload_accepts_only_npc_kind() -> None:
    assert _is_npc_dialogue_payload({"speaker_kind": "npc"}) is True
    assert _is_npc_dialogue_payload({"speaker_kind": "companion"}) is False


def test_queue_tts_for_gm_narration(monkeypatch) -> None:
    synthesize = AsyncMock()
    captured: dict[str, object] = {}

    def fake_create_logged_task(coro, name: str):
        captured["name"] = name
        coro.close()
        return None

    monkeypatch.setattr("app.main.tts_router.synthesize_and_broadcast", synthesize)
    monkeypatch.setattr(
        "app.main.tts_router._runtime",
        {
            "tts_enabled": True,
            "tts_backend": "kokoro",
            "gm_voice": {
                "preset_id": "am_michael",
                "voice_id_local": "am_michael",
                "lang": "fr-fr",
                "speed": 0.85,
            },
        },
    )
    monkeypatch.setattr("app.main.create_logged_task", fake_create_logged_task)

    event = GameEvent(
        event_type=EventType.NARRATION,
        session_id="session-1",
        event_id="event-1",
        payload={
            "text": "La torche tremble.",
            "speaker_kind": "gm",
            "narration_id": "narration-1",
        },
    )

    _queue_tts_for_visible_event(event)

    synthesize.assert_called_once_with(
        "La torche tremble.",
        "session-1",
        "narration-1",
        voice="am_michael",
        lang="fr-fr",
        speed=0.85,
    )
    assert captured["name"] == "tts.gm_narration"


def test_queue_tts_skips_system_narration(monkeypatch) -> None:
    synthesize = AsyncMock()
    monkeypatch.setattr("app.main.tts_router.synthesize_and_broadcast", synthesize)

    event = GameEvent(
        event_type=EventType.NARRATION,
        session_id="session-1",
        payload={
            "text": "Service IA indisponible.",
            "speaker_kind": "system",
        },
    )

    _queue_tts_for_visible_event(event)

    synthesize.assert_not_called()


def test_queue_tts_skips_companion_dialogue(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_logged_task(coro, name: str):
        captured["name"] = name
        coro.close()
        return None

    monkeypatch.setattr("app.main.create_logged_task", fake_create_logged_task)

    event = GameEvent(
        event_type=EventType.DIALOGUE,
        session_id="session-1",
        payload={
            "text": "Je couvre vos arrières.",
            "speaker_kind": "companion",
        },
    )

    _queue_tts_for_visible_event(event)

    assert captured == {}


class _FakeSessionFactory:
    def __call__(self):
        return self

    async def __aenter__(self):
        return object()

    async def __aexit__(self, exc_type, exc, tb):
        return None


@pytest.mark.asyncio
async def test_npc_dialogue_uses_persona_voice(monkeypatch) -> None:
    synthesize = AsyncMock()
    persona = SimpleNamespace(voice=PersonaVoice(gender="male", age_range="elder"))

    monkeypatch.setattr("app.main.tts_router.synthesize_and_broadcast", synthesize)
    monkeypatch.setattr(
        "app.main.tts_router._runtime",
        {"tts_enabled": True, "npc_voice_enabled": True},
    )
    monkeypatch.setattr(
        "app.main.campaign_dossier_service.campaign_for_session",
        AsyncMock(return_value=SimpleNamespace(id="campaign-1")),
    )
    monkeypatch.setattr(
        "app.main.campaign_dossier_service.get_npc_persona",
        AsyncMock(return_value=persona),
    )

    event = GameEvent(
        event_type=EventType.DIALOGUE,
        session_id="session-1",
        payload={"speaker_id": "azaka", "speaker_kind": "npc"},
    )

    await _synthesize_npc_dialogue(
        event,
        "Azaka baisse la voix.",
        "dialogue-1",
        db_session_factory=_FakeSessionFactory(),
    )

    synthesize.assert_awaited_once_with(
        "Azaka baisse la voix.",
        "session-1",
        "dialogue-1",
        voice="am_michael",
        lang="fr-fr",
        speed=0.92,
    )


@pytest.mark.asyncio
async def test_npc_dialogue_falls_back_without_persona(monkeypatch) -> None:
    synthesize = AsyncMock()
    monkeypatch.setattr("app.main.tts_router.synthesize_and_broadcast", synthesize)
    monkeypatch.setattr(
        "app.main.tts_router._runtime",
        {"tts_enabled": True, "npc_voice_enabled": True},
    )

    event = GameEvent(
        event_type=EventType.DIALOGUE,
        session_id="session-1",
        payload={"speaker_kind": "npc"},
    )

    await _synthesize_npc_dialogue(event, "Un marchand soupire.", "dialogue-2")

    synthesize.assert_awaited_once_with(
        "Un marchand soupire.",
        "session-1",
        "dialogue-2",
        voice="ff_siwis",
        lang="fr-fr",
        speed=0.95,
    )
