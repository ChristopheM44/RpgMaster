"""Provider voix local — wrap KokoroClient / VLLMVoxtralClient existants.

Mappe ``PersonaVoice(gender, age_range)`` → ``kokoro_voice_id`` quand la persona
ne spécifie pas ``voice_id_local`` explicitement.
"""

from __future__ import annotations

import logging

from app.agents.persona import PersonaAgeRange, PersonaGender, PersonaVoice
from app.llm.voxtral_client import KokoroClient, VLLMVoxtralClient, VoxtralError
from app.voice.base import AudioBlob, VoiceProvider, VoiceProviderError

logger = logging.getLogger(__name__)


# Mapping (gender, age_range) → kokoro_voice_id (cf. plan §5).
# ff_siwis est la seule voix française dispo dans Kokoro v1.0, donc le mapping
# fallback dessus pour le français. Les autres voix sont anglaises mais
# acceptables avec consigne d'accent dans le texte.
_KOKORO_VOICES: dict[tuple[PersonaGender, PersonaAgeRange], str] = {
    ("male", "child"): "am_adam",
    ("male", "young"): "am_michael",
    ("male", "adult"): "am_adam",
    ("male", "elder"): "am_michael",
    ("male", "ancient"): "am_michael",
    ("female", "child"): "af_bella",
    ("female", "young"): "af_bella",
    ("female", "adult"): "af_sarah",
    ("female", "elder"): "af_nicole",
    ("female", "ancient"): "af_nicole",
    ("neutral", "child"): "af_sky",
    ("neutral", "young"): "af_sky",
    ("neutral", "adult"): "af_sky",
    ("neutral", "elder"): "af_sky",
    ("neutral", "ancient"): "af_sky",
}

# Voix française par défaut quand le persona n'a aucune préférence — gardé pour
# le mode "tout français" qui est le défaut du projet.
_DEFAULT_FR_VOICE = "ff_siwis"

# Ajustement de speed selon age_range pour donner une texture cohérente sans
# avoir besoin de voix supplémentaires.
_AGE_SPEED_MAP: dict[PersonaAgeRange, float] = {
    "child": 1.1,
    "young": 1.05,
    "adult": 1.0,
    "elder": 0.92,
    "ancient": 0.85,
}


def kokoro_voice_for(voice: PersonaVoice, *, prefer_french: bool = True) -> str:
    """Retourne l'ID de voix Kokoro à utiliser pour cette persona.

    Si ``voice.voice_id_local`` est défini, il prend la priorité absolue.
    Sinon le mapping (gender, age_range) ou ff_siwis pour le français.
    """
    if voice.voice_id_local:
        return voice.voice_id_local
    if prefer_french:
        return _DEFAULT_FR_VOICE
    return _KOKORO_VOICES.get((voice.gender, voice.age_range), _DEFAULT_FR_VOICE)


def kokoro_speed_for(voice: PersonaVoice) -> float:
    """Vitesse Kokoro dérivée de age_range + rate."""
    base = _AGE_SPEED_MAP.get(voice.age_range, 1.0)
    if voice.rate == "slow":
        return max(0.5, base * 0.85)
    if voice.rate == "fast":
        return min(2.0, base * 1.15)
    return base


class LocalVoiceProvider(VoiceProvider):
    """Wrap TTS local — Kokoro par défaut, vLLM si configuré."""

    name = "local"

    def __init__(
        self,
        backend: str = "kokoro",
        kokoro: KokoroClient | None = None,
        vllm: VLLMVoxtralClient | None = None,
        *,
        prefer_french: bool = True,
    ) -> None:
        self._backend = backend
        self._kokoro = kokoro or KokoroClient()
        self._vllm = vllm or VLLMVoxtralClient()
        self._prefer_french = prefer_french

    async def speak(self, voice: PersonaVoice, text: str) -> AudioBlob:
        try:
            if self._backend == "vllm":
                wav = await self._vllm.synthesize(text, voice=voice.voice_id_local)
            else:
                wav = await self._kokoro.synthesize(
                    text,
                    voice=kokoro_voice_for(voice, prefer_french=self._prefer_french),
                    speed=kokoro_speed_for(voice),
                )
        except VoxtralError as exc:
            raise VoiceProviderError(f"Local TTS failure: {exc}") from exc
        return AudioBlob(wav_bytes=wav)

    async def is_available(self) -> bool:
        if self._backend == "vllm":
            return await self._vllm.is_available()
        return await self._kokoro.is_available()
