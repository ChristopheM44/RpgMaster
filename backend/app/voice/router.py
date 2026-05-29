"""VoiceRouter — choisit le provider selon config + importance de la persona.

Modes (settings.voice_provider) :
- ``local``   : tout passe par LocalVoiceProvider (TTS Kokoro/vLLM)
- ``realtime``: tout passe par RealtimeVoiceProvider (OpenAI Realtime API)
- ``hybrid``  : Realtime pour personas importance="rich", Local pour le reste

En cas d'échec du provider primaire en mode Realtime/hybrid, fallback automatique
sur le LocalVoiceProvider — le jeu continue avec une voix dégradée plutôt qu'un
silence ou une erreur visible côté joueur.
"""
from __future__ import annotations

import logging

from app.agents.persona import BasePersona, PersonaImportance
from app.config import settings
from app.voice.base import AudioBlob, VoiceProvider, VoiceProviderError
from app.voice.local_provider import LocalVoiceProvider

logger = logging.getLogger(__name__)


class VoiceRouter:
    """Routeur entre Local et Realtime selon config et importance de la persona."""

    def __init__(
        self,
        local: VoiceProvider | None = None,
        realtime: VoiceProvider | None = None,
    ) -> None:
        self._local: VoiceProvider = local or LocalVoiceProvider(
            backend=settings.tts_backend,
        )
        # realtime peut être None tant qu'OpenAI Realtime n'est pas configuré
        self._realtime: VoiceProvider | None = realtime

    def set_realtime_provider(self, provider: VoiceProvider | None) -> None:
        """Permet d'injecter le RealtimeProvider après initialisation."""
        self._realtime = provider

    @property
    def mode(self) -> str:
        return settings.voice_provider

    def _select_provider(self, importance: PersonaImportance) -> VoiceProvider:
        mode = self.mode
        if mode == "realtime" and self._realtime is not None:
            return self._realtime
        if mode == "hybrid" and importance == "rich" and self._realtime is not None:
            return self._realtime
        return self._local

    async def speak_for_persona(
        self,
        persona: BasePersona,
        text: str,
    ) -> AudioBlob:
        """Synthétise *text* avec la voix de *persona*, fallback Local si Realtime KO."""
        provider = self._select_provider(persona.importance)
        try:
            return await provider.speak(persona.voice, text)
        except VoiceProviderError as exc:
            if provider is self._local:
                raise
            logger.warning(
                "VoiceRouter: provider primaire (%s) a échoué pour %s — fallback local : %s",
                provider.name,
                persona.id,
                exc,
            )
            return await self._local.speak(persona.voice, text)


voice_router = VoiceRouter()
