"""Voice abstraction layer — TTS local + OpenAI Realtime API.

Voir le plan persona §5 :
/Users/christophe/.claude/plans/je-voudrais-reflechir-moonlit-hammock.md
"""
from app.voice.base import AudioBlob, VoiceProvider, VoiceProviderError
from app.voice.local_provider import LocalVoiceProvider, kokoro_voice_for
from app.voice.realtime_provider import (
    RealtimeVoiceProvider,
    format_voice_directive,
    openai_voice_for,
)
from app.voice.router import VoiceRouter, voice_router

__all__ = [
    "AudioBlob",
    "VoiceProvider",
    "VoiceProviderError",
    "LocalVoiceProvider",
    "RealtimeVoiceProvider",
    "kokoro_voice_for",
    "openai_voice_for",
    "format_voice_directive",
    "VoiceRouter",
    "voice_router",
]
