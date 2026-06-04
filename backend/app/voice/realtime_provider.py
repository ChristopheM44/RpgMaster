"""Provider voix OpenAI — TTS API pour speak(), Realtime WS pour dialogue bidi.

Deux modes :

- ``speak(voice, text)`` : utilise ``POST /v1/audio/speech`` (synthèse synchrone).
  Sert pour les narrations PNJ/monstre rich quand on veut une voix premium sans
  ouvrir de WebSocket bidi.

- ``open_realtime_session()`` : ouvre une connexion ``wss://api.openai.com/v1/realtime``
  pour les dialogues bidi voix-à-voix. Méthode séparée, consommée par l'endpoint
  ``/ws/dialogue/{session_id}/{persona_id}`` (cf. branche C4).

L'instructions système Realtime est dérivée de PersonaVoice via
``_format_voice_directive`` — accent + register + timbre + age sont sérialisés en
consignes textuelles pour guider l'IA Realtime.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.agents.persona import PersonaVoice
from app.config import settings
from app.voice.base import AudioBlob, VoiceProvider, VoiceProviderError

logger = logging.getLogger(__name__)


# Mapping (gender, age_range) → voix OpenAI standard. Les voix OpenAI sont
# multilingues — un consigne d'accent dans les instructions guide la prononciation.
_OPENAI_VOICES: dict[tuple[str, str], str] = {
    ("male", "child"): "echo",
    ("male", "young"): "echo",
    ("male", "adult"): "onyx",
    ("male", "elder"): "onyx",
    ("male", "ancient"): "onyx",
    ("female", "child"): "shimmer",
    ("female", "young"): "shimmer",
    ("female", "adult"): "nova",
    ("female", "elder"): "nova",
    ("female", "ancient"): "nova",
    ("neutral", "child"): "alloy",
    ("neutral", "young"): "alloy",
    ("neutral", "adult"): "alloy",
    ("neutral", "elder"): "alloy",
    ("neutral", "ancient"): "alloy",
}


def openai_voice_for(voice: PersonaVoice) -> str:
    """Retourne l'ID de voix OpenAI (TTS et Realtime utilisent le même set)."""
    if voice.voice_id_realtime:
        return voice.voice_id_realtime
    return _OPENAI_VOICES.get((voice.gender, voice.age_range), "alloy")


# Tableaux de traduction accent / timbre / register → consigne textuelle FR.
_REGISTER_HINTS: dict[str, str] = {
    "formal": "Parle avec un registre soutenu et respectueux.",
    "casual": "Parle avec un registre courant et naturel.",
    "archaic": "Parle avec un registre archaïque, évite tout terme moderne.",
    "vulgar": "Parle avec un registre familier, voire grossier.",
}

_RATE_HINTS: dict[str, str] = {
    "slow": "Parle lentement, en pesant tes mots.",
    "normal": "",
    "fast": "Parle rapidement, sans hésitation.",
}

_TIMBRE_HINTS: dict[str, str] = {
    "raspy": "Ta voix est rauque, comme abimée.",
    "rauque": "Ta voix est rauque, comme abimée.",
    "warm": "Ta voix est chaleureuse et enveloppante.",
    "chaleureux": "Ta voix est chaleureuse et enveloppante.",
    "metallic": "Ta voix résonne, presque métallique.",
    "métallique": "Ta voix résonne, presque métallique.",
    "grondant": "Ta voix gronde dans le grave, presque animale.",
    "sifflant": "Ta voix siffle, glissante et inquiétante.",
    "résonnant": "Ta voix résonne profondément, comme dans une caverne.",
}

_AGE_HINTS: dict[str, str] = {
    "child": "Tu es un enfant, voix aiguë et excitée.",
    "young": "Tu es jeune, voix vive.",
    "adult": "Tu es adulte.",
    "elder": "Tu es âgé, voix posée et expérimentée.",
    "ancient": "Tu es très âgé, voix grave et chargée d'autorité ancienne.",
}


def format_voice_directive(voice: PersonaVoice) -> str:
    """Sérialise PersonaVoice en bloc d'instructions pour Realtime / TTS.

    Combine genre, âge, accent, registre, timbre et débit en consignes FR
    courtes que l'IA Realtime peut suivre.
    """
    parts: list[str] = []
    age_hint = _AGE_HINTS.get(voice.age_range)
    if age_hint:
        parts.append(age_hint)
    register_hint = _REGISTER_HINTS.get(voice.speech_register)
    if register_hint:
        parts.append(register_hint)
    if voice.accent:
        parts.append(f"Tu parles avec un accent {voice.accent}.")
    timbre_hint = _TIMBRE_HINTS.get((voice.timbre or "").lower())
    if timbre_hint:
        parts.append(timbre_hint)
    rate_hint = _RATE_HINTS.get(voice.rate)
    if rate_hint:
        parts.append(rate_hint)
    return " ".join(parts)


class RealtimeVoiceProvider(VoiceProvider):
    """Provider OpenAI — TTS API pour speak(), Realtime API pour dialogue bidi."""

    name = "realtime"

    def __init__(
        self,
        api_key: str | None = None,
        tts_model: str = "tts-1",
        realtime_model: str | None = None,
        realtime_base_url: str | None = None,
        tts_base_url: str = "https://api.openai.com/v1",
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._api_key = api_key or settings.openai_realtime_api_key
        self._tts_model = tts_model
        self._realtime_model = realtime_model or settings.openai_realtime_model
        self._realtime_base_url = realtime_base_url or settings.openai_realtime_base_url
        self._tts_base_url = tts_base_url.rstrip("/")
        self._http_client = http_client

    @property
    def realtime_url(self) -> str:
        return f"{self._realtime_base_url}?model={self._realtime_model}"

    async def speak(self, voice: PersonaVoice, text: str) -> AudioBlob:
        """Synthèse TTS synchrone via ``POST /v1/audio/speech``."""
        if not self._api_key:
            raise VoiceProviderError("OPENAI_REALTIME_API_KEY non configurée")

        payload: dict[str, Any] = {
            "model": self._tts_model,
            "voice": openai_voice_for(voice),
            "input": text,
            "response_format": "wav",
            "speed": _SPEED_MAP.get(voice.rate, 1.0),
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self._tts_base_url}/audio/speech"

        client = self._http_client
        owns_client = client is None
        if client is None:
            client = httpx.AsyncClient(timeout=30.0)
        try:
            response = await client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            return AudioBlob(wav_bytes=response.content, sample_rate=24000)
        except httpx.HTTPError as exc:
            raise VoiceProviderError(f"OpenAI TTS failure: {exc}") from exc
        finally:
            if owns_client:
                await client.aclose()

    async def is_available(self) -> bool:
        return bool(self._api_key)

    def build_realtime_instructions(
        self,
        persona_brief: str,
        voice: PersonaVoice,
    ) -> str:
        """Compose le bloc 'instructions' envoyé à la session Realtime.

        Sert quand on ouvre une session bidi via WebSocket. Le brief de persona
        (rendu par la macro Jinja `_persona_render.j2`) est combiné aux consignes
        vocales pour donner une voix cohérente à l'IA Realtime.
        """
        directive = format_voice_directive(voice)
        return (
            f"{persona_brief.strip()}\n\n"
            f"DIRECTIVES VOCALES :\n{directive}\n\n"
            "Réponds toujours dans le rôle. N'évoque jamais que tu es une IA."
        )


_SPEED_MAP: dict[str, float] = {
    "slow": 0.85,
    "normal": 1.0,
    "fast": 1.15,
}
