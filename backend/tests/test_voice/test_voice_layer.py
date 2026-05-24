"""Tests offline pour le voice layer (LocalProvider, RealtimeProvider, Router).

Aucun appel réseau, aucun subprocess Kokoro : tout est mocké.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.agents.persona import (
    MonsterPersona,
    NPCPersona,
    PersonaImportance,
    PersonaVoice,
)
from app.voice.base import AudioBlob, VoiceProvider, VoiceProviderError
from app.voice.local_provider import (
    LocalVoiceProvider,
    kokoro_speed_for,
    kokoro_voice_for,
)
from app.voice.realtime_provider import (
    RealtimeVoiceProvider,
    format_voice_directive,
    openai_voice_for,
)
from app.voice.router import VoiceRouter

# ---------------------------------------------------------------------------
# Mappings Kokoro
# ---------------------------------------------------------------------------


def test_kokoro_voice_default_french() -> None:
    """Sans override, fr-fr prioritaire → ff_siwis."""
    v = PersonaVoice(gender="male", age_range="elder")
    assert kokoro_voice_for(v) == "ff_siwis"


def test_kokoro_voice_explicit_override_wins() -> None:
    v = PersonaVoice(gender="male", age_range="adult", voice_id_local="am_custom")
    assert kokoro_voice_for(v) == "am_custom"


def test_kokoro_voice_english_mapping() -> None:
    """Sans prefer_french, mapping (gender, age_range) → voix anglaise."""
    v_fa = PersonaVoice(gender="female", age_range="adult")
    v_my = PersonaVoice(gender="male", age_range="young")
    assert kokoro_voice_for(v_fa, prefer_french=False) == "af_sarah"
    assert kokoro_voice_for(v_my, prefer_french=False) == "am_michael"


def test_kokoro_speed_for_age_and_rate() -> None:
    base = PersonaVoice(gender="male", age_range="adult")
    elder = PersonaVoice(gender="male", age_range="elder")
    elder_slow = PersonaVoice(gender="male", age_range="elder", rate="slow")
    child_fast = PersonaVoice(gender="female", age_range="child", rate="fast")

    assert kokoro_speed_for(base) == 1.0
    assert kokoro_speed_for(elder) < 1.0  # elder ralenti
    assert kokoro_speed_for(elder_slow) < kokoro_speed_for(elder)
    assert kokoro_speed_for(child_fast) > kokoro_speed_for(
        PersonaVoice(gender="female", age_range="child")
    )


# ---------------------------------------------------------------------------
# LocalVoiceProvider
# ---------------------------------------------------------------------------


async def test_local_provider_speak_calls_kokoro_with_mapped_voice() -> None:
    kokoro = AsyncMock()
    kokoro.synthesize = AsyncMock(return_value=b"FAKE_WAV_BYTES")
    provider = LocalVoiceProvider(backend="kokoro", kokoro=kokoro)

    voice = PersonaVoice(gender="female", age_range="elder")
    audio = await provider.speak(voice, "Bonjour, voyageur.")

    assert isinstance(audio, AudioBlob)
    assert audio.wav_bytes == b"FAKE_WAV_BYTES"
    kokoro.synthesize.assert_awaited_once()
    args, kwargs = kokoro.synthesize.call_args
    assert kwargs["voice"] == "ff_siwis"  # FR par défaut
    assert "speed" in kwargs


async def test_local_provider_raises_voice_error_on_kokoro_failure() -> None:
    from app.llm.voxtral_client import VoxtralError

    kokoro = AsyncMock()
    kokoro.synthesize = AsyncMock(side_effect=VoxtralError("subprocess died"))
    provider = LocalVoiceProvider(backend="kokoro", kokoro=kokoro)

    with pytest.raises(VoiceProviderError, match="Local TTS failure"):
        await provider.speak(PersonaVoice(), "Test")


async def test_local_provider_vllm_backend_routes_to_vllm() -> None:
    kokoro = AsyncMock()
    vllm = AsyncMock()
    vllm.synthesize = AsyncMock(return_value=b"VLLM_BYTES")
    provider = LocalVoiceProvider(backend="vllm", kokoro=kokoro, vllm=vllm)

    audio = await provider.speak(PersonaVoice(voice_id_local="some_vllm_voice"), "X")

    assert audio.wav_bytes == b"VLLM_BYTES"
    vllm.synthesize.assert_awaited_once()
    kokoro.synthesize.assert_not_called()


# ---------------------------------------------------------------------------
# RealtimeVoiceProvider — TTS API
# ---------------------------------------------------------------------------


def test_openai_voice_mapping_by_gender_age() -> None:
    assert openai_voice_for(PersonaVoice(gender="male", age_range="elder")) == "onyx"
    assert openai_voice_for(PersonaVoice(gender="female", age_range="ancient")) == "nova"
    assert openai_voice_for(PersonaVoice(gender="neutral", age_range="adult")) == "alloy"


def test_openai_voice_explicit_override_wins() -> None:
    v = PersonaVoice(
        gender="male", age_range="adult", voice_id_realtime="custom_voice"
    )
    assert openai_voice_for(v) == "custom_voice"


def test_format_voice_directive_includes_all_dimensions() -> None:
    v = PersonaVoice(
        gender="female",
        age_range="ancient",
        accent="noble",
        speech_register="archaic",
        timbre="raspy",
        rate="slow",
    )
    directive = format_voice_directive(v)
    assert "très âgé" in directive
    assert "archaïque" in directive
    assert "noble" in directive
    assert "rauque" in directive
    assert "lentement" in directive


def test_format_voice_directive_handles_unknown_timbre_gracefully() -> None:
    v = PersonaVoice(gender="male", age_range="adult", timbre="unknown_xyz")
    directive = format_voice_directive(v)
    # Pas de crash, juste pas d'ajout pour le timbre inconnu
    assert "unknown_xyz" not in directive
    assert "adulte" in directive.lower() or "adult" in directive.lower()


async def test_realtime_provider_unavailable_without_api_key() -> None:
    provider = RealtimeVoiceProvider(api_key="")
    assert await provider.is_available() is False


async def test_realtime_provider_speak_requires_api_key() -> None:
    provider = RealtimeVoiceProvider(api_key="")
    with pytest.raises(VoiceProviderError, match="API_KEY"):
        await provider.speak(PersonaVoice(), "Hello")


async def test_realtime_provider_speak_posts_to_openai_tts() -> None:
    fake_response = AsyncMock()
    fake_response.content = b"OPENAI_WAV_BYTES"
    fake_response.raise_for_status = lambda: None

    fake_client = AsyncMock()
    fake_client.post = AsyncMock(return_value=fake_response)

    provider = RealtimeVoiceProvider(api_key="sk-test", http_client=fake_client)
    voice = PersonaVoice(gender="female", age_range="elder", rate="slow")
    audio = await provider.speak(voice, "Bonjour mon enfant.")

    assert audio.wav_bytes == b"OPENAI_WAV_BYTES"
    fake_client.post.assert_awaited_once()
    call_kwargs = fake_client.post.call_args
    payload = call_kwargs.kwargs["json"]
    assert payload["voice"] == "nova"  # female + elder
    assert payload["speed"] == 0.85  # slow
    assert payload["response_format"] == "wav"
    assert payload["input"] == "Bonjour mon enfant."


async def test_realtime_provider_raises_voice_error_on_http_failure() -> None:
    import httpx

    fake_client = AsyncMock()
    fake_client.post = AsyncMock(side_effect=httpx.ConnectError("no network"))

    provider = RealtimeVoiceProvider(api_key="sk-test", http_client=fake_client)
    with pytest.raises(VoiceProviderError, match="OpenAI TTS failure"):
        await provider.speak(PersonaVoice(), "X")


def test_realtime_provider_build_instructions_combines_brief_and_voice() -> None:
    provider = RealtimeVoiceProvider(api_key="sk-test")
    voice = PersonaVoice(
        gender="male", age_range="elder", speech_register="archaic", timbre="grondant"
    )
    instructions = provider.build_realtime_instructions(
        persona_brief="Tu es Vermithrax, dragon antique.",
        voice=voice,
    )
    assert "Vermithrax" in instructions
    assert "archaïque" in instructions
    assert "gronde" in instructions
    assert "DIRECTIVES VOCALES" in instructions


# ---------------------------------------------------------------------------
# VoiceRouter
# ---------------------------------------------------------------------------


class _FakeProvider(VoiceProvider):
    name = "fake"

    def __init__(self, name: str, *, fail: bool = False) -> None:
        self.name = name
        self._fail = fail
        self.calls: list[str] = []

    async def speak(self, voice: PersonaVoice, text: str) -> AudioBlob:
        self.calls.append(text)
        if self._fail:
            raise VoiceProviderError(f"{self.name} forced failure")
        return AudioBlob(wav_bytes=f"AUDIO_{self.name}".encode())

    async def is_available(self) -> bool:
        return True


def _make_persona(importance: PersonaImportance = "standard") -> NPCPersona:
    return NPCPersona(
        id="x",
        name="X",
        archetype="x",
        short_description="x",
        importance=importance,
    )


async def test_router_local_mode_always_uses_local(monkeypatch) -> None:
    monkeypatch.setattr("app.voice.router.settings.voice_provider", "local")
    local = _FakeProvider("local")
    realtime = _FakeProvider("realtime")
    router = VoiceRouter(local=local, realtime=realtime)

    await router.speak_for_persona(_make_persona("rich"), "X")
    await router.speak_for_persona(_make_persona("light"), "X")

    assert len(local.calls) == 2
    assert len(realtime.calls) == 0


async def test_router_realtime_mode_uses_realtime(monkeypatch) -> None:
    monkeypatch.setattr("app.voice.router.settings.voice_provider", "realtime")
    local = _FakeProvider("local")
    realtime = _FakeProvider("realtime")
    router = VoiceRouter(local=local, realtime=realtime)

    await router.speak_for_persona(_make_persona("light"), "X")
    assert len(realtime.calls) == 1
    assert len(local.calls) == 0


async def test_router_realtime_falls_back_to_local_if_realtime_missing(
    monkeypatch,
) -> None:
    monkeypatch.setattr("app.voice.router.settings.voice_provider", "realtime")
    local = _FakeProvider("local")
    router = VoiceRouter(local=local, realtime=None)

    await router.speak_for_persona(_make_persona("rich"), "X")
    assert len(local.calls) == 1


async def test_router_hybrid_mode_routes_by_importance(monkeypatch) -> None:
    monkeypatch.setattr("app.voice.router.settings.voice_provider", "hybrid")
    local = _FakeProvider("local")
    realtime = _FakeProvider("realtime")
    router = VoiceRouter(local=local, realtime=realtime)

    await router.speak_for_persona(_make_persona("rich"), "X")
    await router.speak_for_persona(_make_persona("light"), "X")
    await router.speak_for_persona(_make_persona("standard"), "X")

    assert len(realtime.calls) == 1  # uniquement rich
    assert len(local.calls) == 2  # light + standard


async def test_router_falls_back_to_local_on_realtime_failure(monkeypatch) -> None:
    monkeypatch.setattr("app.voice.router.settings.voice_provider", "realtime")
    local = _FakeProvider("local")
    realtime = _FakeProvider("realtime", fail=True)
    router = VoiceRouter(local=local, realtime=realtime)

    audio = await router.speak_for_persona(_make_persona("rich"), "X")
    assert audio.wav_bytes == b"AUDIO_local"
    assert len(realtime.calls) == 1  # tenté
    assert len(local.calls) == 1  # fallback


async def test_router_local_failure_is_not_caught(monkeypatch) -> None:
    """Si Local échoue (dernier recours), l'erreur remonte au caller."""
    monkeypatch.setattr("app.voice.router.settings.voice_provider", "local")
    local = _FakeProvider("local", fail=True)
    router = VoiceRouter(local=local)

    with pytest.raises(VoiceProviderError, match="local forced failure"):
        await router.speak_for_persona(_make_persona("rich"), "X")


async def test_router_works_with_monster_persona(monkeypatch) -> None:
    """Le router doit accepter n'importe quelle BasePersona, pas que NPC."""
    monkeypatch.setattr("app.voice.router.settings.voice_provider", "hybrid")
    local = _FakeProvider("local")
    realtime = _FakeProvider("realtime")
    router = VoiceRouter(local=local, realtime=realtime)

    monster = MonsterPersona(
        id="dragon",
        name="Vermithrax",
        archetype="ancient_tyrant",
        short_description="X",
        monster_srd_id="ancient_red_dragon",
        behavior_pattern="cunning",
        importance="rich",
    )
    await router.speak_for_persona(monster, "Vous osez ?")
    assert len(realtime.calls) == 1
