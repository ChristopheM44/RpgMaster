"""Tests offline pour RealtimeSession (bridge WebSocket OpenAI Realtime).

Le WebSocket OpenAI est mocké via un fake context manager qui capture les
messages envoyés et fournit des messages de réponse simulés.
"""
from __future__ import annotations

import base64
import json
from typing import Any
from unittest.mock import AsyncMock

import pytest
from websockets.exceptions import WebSocketException

from app.agents.persona import PersonaVoice
from app.voice.base import VoiceProviderError
from app.voice.realtime_session import RealtimeSession, RealtimeTranscript


class _FakeWebSocket:
    """Simule un WS OpenAI Realtime : capture envois, joue réponses préprogrammées."""

    def __init__(self, replies: list[dict[str, Any]] | None = None) -> None:
        self.sent: list[dict[str, Any]] = []
        self.replies = replies or []
        self.closed = False

    async def send(self, raw: str) -> None:
        self.sent.append(json.loads(raw))

    def __aiter__(self):
        self._index = 0
        return self

    async def __anext__(self) -> str:
        if self._index >= len(self.replies):
            raise StopAsyncIteration
        item = self.replies[self._index]
        self._index += 1
        return json.dumps(item)

    async def close(self) -> None:
        self.closed = True


def _make_session(
    fake_ws: _FakeWebSocket,
    voice: PersonaVoice | None = None,
) -> RealtimeSession:
    async def fake_factory(*args, **kwargs):
        return fake_ws

    return RealtimeSession(
        api_key="sk-test",
        voice=voice or PersonaVoice(gender="female", age_range="elder"),
        ws_factory=fake_factory,
    )


# ---------------------------------------------------------------------------
# RealtimeTranscript
# ---------------------------------------------------------------------------


def test_transcript_accumulates_user_and_assistant_turns() -> None:
    t = RealtimeTranscript()
    t.append_user("Bonjour")
    t.append_user("")  # vide ignoré
    t.append_assistant("Salut, voyageur.")
    payload = t.to_payload()
    assert payload["user_turns"] == ["Bonjour"]
    assert payload["assistant_turns"] == ["Salut, voyageur."]


# ---------------------------------------------------------------------------
# Connect
# ---------------------------------------------------------------------------


async def test_connect_requires_api_key() -> None:
    session = RealtimeSession(api_key="", voice=PersonaVoice())
    with pytest.raises(VoiceProviderError, match="API_KEY"):
        await session.connect("Tu es un PNJ")


async def test_connect_sends_session_update_with_voice_and_instructions() -> None:
    fake = _FakeWebSocket()
    session = _make_session(
        fake, voice=PersonaVoice(gender="female", age_range="ancient", rate="slow")
    )
    await session.connect("Tu es Mère Éline, oracle aveugle.")

    assert len(fake.sent) == 1
    config = fake.sent[0]
    assert config["type"] == "session.update"
    assert config["session"]["voice"] == "nova"  # female + ancient
    instructions = config["session"]["instructions"]
    assert "Mère Éline" in instructions
    assert "DIRECTIVES VOCALES" in instructions
    assert "très âgé" in instructions
    assert "lentement" in instructions
    assert "audio" in config["session"]["modalities"]


async def test_connect_wraps_websocket_failure_in_voice_error() -> None:
    async def failing_factory(*args, **kwargs):
        raise WebSocketException("no route")

    session = RealtimeSession(
        api_key="sk-test",
        voice=PersonaVoice(),
        ws_factory=failing_factory,
    )
    with pytest.raises(VoiceProviderError, match="WS connect failed"):
        await session.connect("Brief")


# ---------------------------------------------------------------------------
# Send audio / commit / cancel
# ---------------------------------------------------------------------------


async def test_send_user_audio_base64_encodes_payload() -> None:
    fake = _FakeWebSocket()
    session = _make_session(fake)
    await session.connect("Brief")
    await session.send_user_audio(b"raw_pcm_bytes")

    # Premier message = session.update, deuxième = input_audio_buffer.append
    assert fake.sent[1]["type"] == "input_audio_buffer.append"
    audio = fake.sent[1]["audio"]
    assert base64.b64decode(audio) == b"raw_pcm_bytes"


async def test_commit_user_audio_triggers_response_create() -> None:
    fake = _FakeWebSocket()
    session = _make_session(fake)
    await session.connect("Brief")
    await session.commit_user_audio()

    types = [m["type"] for m in fake.sent[1:]]
    assert types == ["input_audio_buffer.commit", "response.create"]


async def test_cancel_response_sends_cancel_event() -> None:
    fake = _FakeWebSocket()
    session = _make_session(fake)
    await session.connect("Brief")
    await session.cancel_response()

    assert fake.sent[-1] == {"type": "response.cancel"}


async def test_send_before_connect_raises() -> None:
    session = RealtimeSession(api_key="sk-test", voice=PersonaVoice())
    with pytest.raises(VoiceProviderError, match="non ouverte"):
        await session.send_user_audio(b"x")


# ---------------------------------------------------------------------------
# Iter events / transcript
# ---------------------------------------------------------------------------


async def test_iter_events_yields_replies_and_updates_transcript() -> None:
    fake = _FakeWebSocket(
        replies=[
            {
                "type": "conversation.item.input_audio_transcription.completed",
                "transcript": "Bonjour, qui es-tu ?",
            },
            {"type": "response.audio.delta", "delta": "..."},
            {
                "type": "response.audio_transcript.done",
                "transcript": "Je suis Mère Éline.",
            },
        ]
    )
    session = _make_session(fake)
    await session.connect("Brief")

    events: list[dict[str, Any]] = []
    async for event in session.iter_events():
        events.append(event)

    assert len(events) == 3
    assert session.transcript.user_turns == ["Bonjour, qui es-tu ?"]
    assert session.transcript.assistant_turns == ["Je suis Mère Éline."]


async def test_iter_events_before_connect_raises() -> None:
    session = RealtimeSession(api_key="sk-test", voice=PersonaVoice())
    with pytest.raises(VoiceProviderError, match="non ouverte"):
        async for _ in session.iter_events():
            pass


# ---------------------------------------------------------------------------
# Close
# ---------------------------------------------------------------------------


async def test_close_is_safe_to_call_twice() -> None:
    fake = _FakeWebSocket()
    session = _make_session(fake)
    await session.connect("Brief")
    await session.close()
    await session.close()  # no error
    assert fake.closed is True


async def test_close_without_connect_is_noop() -> None:
    session = RealtimeSession(api_key="sk-test", voice=PersonaVoice())
    await session.close()


# ---------------------------------------------------------------------------
# Persona brief rendering (ws_dialogue helper)
# ---------------------------------------------------------------------------


def test_render_persona_brief_includes_hidden_motivations() -> None:
    """Le brief envoyé à Realtime doit contenir les secrets et motivations cachées."""
    from app.agents.persona import NPCPersona, PersonaMotivations
    from app.api.ws_dialogue import _render_persona_brief

    persona = NPCPersona(
        id="garrik",
        name="Garrik",
        archetype="merchant",
        short_description="Tavernier rude.",
        motivations=PersonaMotivations(
            visible=["vendre sa bière"],
            hidden=["venger sa fille"],
            fears=["la magie noire"],
        ),
        secrets=["sait qui a tué le shérif"],
    )
    brief = _render_persona_brief(persona)
    assert "Garrik" in brief
    assert "venger sa fille" in brief  # hidden inclus pour Realtime
    assert "sait qui a tué le shérif" in brief
    # Mock async on AsyncMock for symmetry — make sure the brief is not empty
    assert len(brief) > 200


def test_render_persona_brief_includes_voice_directives_via_session() -> None:
    """Le brief n'inclut pas directement la directive vocale (c'est RealtimeSession.connect
    qui l'ajoute). On vérifie au moins que le brief ne mentionne PAS l'API ('non révélé')."""
    from app.agents.persona import NPCPersona
    from app.api.ws_dialogue import _render_persona_brief

    persona = NPCPersona(
        id="x", name="X", archetype="x", short_description="x"
    )
    brief = _render_persona_brief(persona)
    assert "OpenAI" not in brief
    assert "API" not in brief


# Helper to silence unused import warning if the test file evolves.
_ = AsyncMock
