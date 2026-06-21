"""C1 — la narration TTS des PNJ passe par VoiceRouter en mode hybrid/realtime.

Vérifie que ``app.main._synthesize_npc_dialogue`` route bien la synthèse via
``voice_router.speak_for_persona`` (activation hybrid/realtime + broadcast AUDIO)
quand une persona est résolue, et qu'en mode ``local`` (défaut) le chemin direct
``tts_router.synthesize_and_broadcast`` est conservé inchangé.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app import main as app_main
from app.agents.persona import PersonaVoice
from app.game.event_bus import EventType
from app.voice.base import AudioBlob


class _FakeSession:
    async def __aenter__(self):
        return SimpleNamespace(name="db")

    async def __aexit__(self, *exc):
        return False


def _fake_factory():
    return _FakeSession()


def _npc_event():
    return SimpleNamespace(
        session_id="sess-1",
        payload={
            "speaker": "Brom",
            "speaker_id": "brom",
            "speaker_kind": "npc",
            "text": "Bienvenue, aventurier.",
        },
    )


async def test_npc_narration_routes_through_voice_router_in_hybrid(monkeypatch) -> None:
    monkeypatch.setattr(
        app_main,
        "tts_router",
        SimpleNamespace(tts_enabled=True, npc_voice_enabled=True),
    )
    persona = SimpleNamespace(
        id="brom",
        importance="rich",
        voice=PersonaVoice(gender="male", age_range="adult"),
    )
    monkeypatch.setattr(
        app_main.campaign_dossier_service,
        "campaign_for_session",
        AsyncMock(return_value=SimpleNamespace(id="camp-1")),
    )
    monkeypatch.setattr(
        app_main.campaign_dossier_service,
        "get_npc_persona",
        AsyncMock(return_value=persona),
    )
    speak = AsyncMock(return_value=AudioBlob(wav_bytes=b"RIFFfakewav"))
    monkeypatch.setattr(
        app_main,
        "voice_router",
        SimpleNamespace(mode="hybrid", speak_for_persona=speak),
    )
    publish = AsyncMock()
    monkeypatch.setattr(app_main.event_bus, "publish_to_session", publish)

    await app_main._synthesize_npc_dialogue(
        _npc_event(),
        "Bienvenue, aventurier.",
        "narr-1",
        db_session_factory=_fake_factory,
    )

    # Routé par le VoiceRouter avec la persona résolue.
    speak.assert_awaited_once()
    assert speak.await_args.args[0] is persona
    assert speak.await_args.args[1] == "Bienvenue, aventurier."

    # L'audio produit est diffusé via un event AUDIO "ready" portant l'audio_b64.
    audio_calls = [c for c in publish.await_args_list if c.args[1] == EventType.AUDIO]
    assert any(
        c.args[2].get("status") == "ready" and c.args[2].get("audio_b64") for c in audio_calls
    ), "aucun event AUDIO 'ready' avec audio_b64 diffusé"


async def test_npc_narration_local_mode_keeps_direct_path(monkeypatch) -> None:
    synth = AsyncMock()
    monkeypatch.setattr(
        app_main,
        "tts_router",
        SimpleNamespace(
            tts_enabled=True,
            npc_voice_enabled=True,
            synthesize_and_broadcast=synth,
        ),
    )
    persona = SimpleNamespace(
        id="brom",
        importance="standard",
        voice=PersonaVoice(gender="male", age_range="adult"),
    )
    monkeypatch.setattr(
        app_main.campaign_dossier_service,
        "campaign_for_session",
        AsyncMock(return_value=SimpleNamespace(id="camp-1")),
    )
    monkeypatch.setattr(
        app_main.campaign_dossier_service,
        "get_npc_persona",
        AsyncMock(return_value=persona),
    )
    speak = AsyncMock(return_value=AudioBlob(wav_bytes=b"RIFFfakewav"))
    monkeypatch.setattr(
        app_main,
        "voice_router",
        SimpleNamespace(mode="local", speak_for_persona=speak),
    )

    await app_main._synthesize_npc_dialogue(
        _npc_event(),
        "Bienvenue, aventurier.",
        "narr-1",
        db_session_factory=_fake_factory,
    )

    # Mode local : on ne passe PAS par le VoiceRouter, le chemin direct est conservé.
    speak.assert_not_awaited()
    synth.assert_awaited_once()
