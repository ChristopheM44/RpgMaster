"""Interface abstraite des fournisseurs vocaux (TTS local et Realtime API)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass

from app.agents.persona import PersonaVoice


class VoiceProviderError(Exception):
    """Erreur de synthèse vocale (toute provider confondue)."""


@dataclass(frozen=True)
class AudioBlob:
    """Audio synthétisé prêt à diffuser sur le WebSocket."""

    wav_bytes: bytes
    sample_rate: int = 24000
    mime_type: str = "audio/wav"


class VoiceProvider(ABC):
    """Producteur audio pour une persona.

    L'API minimale est ``speak(voice, text)`` qui retourne un AudioBlob.
    Les providers Realtime ajoutent ``stream_conversation()`` séparément (cf.
    ``realtime_provider.py``) — interface non requise au niveau base car le
    pipeline TTS classique n'en a pas besoin.
    """

    name: str = "voice_provider"

    @abstractmethod
    async def speak(self, voice: PersonaVoice, text: str) -> AudioBlob:
        """Synthétise *text* avec les paramètres de la persona.

        Doit raise ``VoiceProviderError`` en cas d'échec — pas de Exception
        générique pour laisser le router gérer le fallback.
        """

    @abstractmethod
    async def is_available(self) -> bool:
        """Indique si le provider peut servir des requêtes en l'état courant."""
