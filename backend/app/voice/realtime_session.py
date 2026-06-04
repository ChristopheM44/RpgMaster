"""Session WebSocket bidirectionnelle vers OpenAI Realtime API.

Encapsule l'ouverture du WS, l'envoi des events OpenAI Realtime protocol, et
l'itération async sur les events reçus. Utilisé par l'endpoint
``/ws/dialogue/{session_id}/{persona_id}`` pour bridger l'audio joueur ↔ PNJ.

Protocole OpenAI Realtime résumé :
- WS URL: wss://api.openai.com/v1/realtime?model=<model>
- Headers: Authorization Bearer, OpenAI-Beta: realtime=v1
- Client envoie: session.update, input_audio_buffer.append/commit
- Serveur envoie: response.audio.delta, response.audio_transcript.delta/done

Réf: https://platform.openai.com/docs/guides/realtime
"""

from __future__ import annotations

import base64
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import websockets
from websockets.exceptions import WebSocketException

from app.agents.persona import PersonaVoice
from app.config import settings
from app.voice.base import VoiceProviderError
from app.voice.realtime_provider import format_voice_directive, openai_voice_for

logger = logging.getLogger(__name__)


@dataclass
class RealtimeTranscript:
    """Transcription complète accumulée pendant une session Realtime."""

    user_turns: list[str] = field(default_factory=list)
    assistant_turns: list[str] = field(default_factory=list)

    def append_user(self, text: str) -> None:
        if text:
            self.user_turns.append(text)

    def append_assistant(self, text: str) -> None:
        if text:
            self.assistant_turns.append(text)

    def to_payload(self) -> dict[str, Any]:
        return {
            "user_turns": list(self.user_turns),
            "assistant_turns": list(self.assistant_turns),
        }


class RealtimeSession:
    """Une session WebSocket avec OpenAI Realtime API.

    Usage typique::

        session = RealtimeSession(api_key="sk-...", voice=persona.voice)
        async with session.open(instructions="Tu es Vermithrax..."):
            await session.send_user_audio(audio_chunk)
            async for event in session.iter_events():
                ...
    """

    def __init__(
        self,
        api_key: str,
        voice: PersonaVoice,
        *,
        model: str | None = None,
        base_url: str | None = None,
        ws_factory: Any = None,
    ) -> None:
        self._api_key = api_key
        self._voice = voice
        self._model = model or settings.openai_realtime_model
        self._base_url = base_url or settings.openai_realtime_base_url
        self._ws: Any = None
        self._ws_factory = ws_factory or websockets.connect
        self.transcript = RealtimeTranscript()

    @property
    def url(self) -> str:
        return f"{self._base_url}?model={self._model}"

    @property
    def headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "OpenAI-Beta": "realtime=v1",
        }

    async def connect(self, instructions: str) -> None:
        """Ouvre le WS et envoie la configuration initiale de session."""
        if not self._api_key:
            raise VoiceProviderError("OPENAI_REALTIME_API_KEY non configurée")
        try:
            self._ws = await self._ws_factory(
                self.url,
                additional_headers=self.headers,
            )
        except WebSocketException as exc:
            raise VoiceProviderError(f"Realtime WS connect failed: {exc}") from exc

        full_instructions = (
            f"{instructions.strip()}\n\nDIRECTIVES VOCALES :\n{format_voice_directive(self._voice)}"
        )
        await self._send(
            {
                "type": "session.update",
                "session": {
                    "modalities": ["audio", "text"],
                    "voice": openai_voice_for(self._voice),
                    "instructions": full_instructions,
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {"model": "whisper-1"},
                },
            }
        )

    async def send_user_audio(self, pcm16_bytes: bytes) -> None:
        """Ajoute un chunk audio utilisateur au buffer d'entrée."""
        await self._send(
            {
                "type": "input_audio_buffer.append",
                "audio": base64.b64encode(pcm16_bytes).decode("ascii"),
            }
        )

    async def commit_user_audio(self) -> None:
        """Finalise le tour utilisateur — déclenche la réponse de l'IA."""
        await self._send({"type": "input_audio_buffer.commit"})
        await self._send({"type": "response.create"})

    async def cancel_response(self) -> None:
        """Annule la génération en cours (le joueur interrompt l'IA)."""
        await self._send({"type": "response.cancel"})

    async def iter_events(self) -> AsyncIterator[dict[str, Any]]:
        """Itère sur les events reçus depuis le WS Realtime.

        Met à jour ``self.transcript`` à chaque événement de transcription
        (user audio transcribed ou assistant audio transcript).
        """
        if self._ws is None:
            raise VoiceProviderError("Session non ouverte")
        try:
            async for raw in self._ws:
                event: dict[str, Any] = json.loads(raw)
                self._handle_transcript_event(event)
                yield event
        except WebSocketException as exc:
            raise VoiceProviderError(f"Realtime stream failure: {exc}") from exc

    def _handle_transcript_event(self, event: dict[str, Any]) -> None:
        etype = event.get("type", "")
        # Transcription du joueur (user audio → text via whisper)
        if etype == "conversation.item.input_audio_transcription.completed":
            self.transcript.append_user(str(event.get("transcript") or ""))
        # Transcription de la réponse assistant (audio synthétisé → texte)
        elif etype == "response.audio_transcript.done":
            self.transcript.append_assistant(str(event.get("transcript") or ""))

    async def close(self) -> None:
        if self._ws is not None:
            try:
                await self._ws.close()
            except Exception:
                pass
            self._ws = None

    async def _send(self, payload: dict[str, Any]) -> None:
        if self._ws is None:
            raise VoiceProviderError("Session non ouverte")
        try:
            await self._ws.send(json.dumps(payload))
        except WebSocketException as exc:
            raise VoiceProviderError(f"Realtime send failed: {exc}") from exc
