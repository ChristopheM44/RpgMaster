from __future__ import annotations

import base64
import logging
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_admin import router as admin_router
from app.api.routes_campaign import router as campaign_router
from app.api.routes_character import router as character_router
from app.api.routes_encounters import router as encounters_router
from app.api.routes_game import router as game_router
from app.api.routes_pregen import router as pregen_router
from app.api.routes_session import router as session_router
from app.api.routes_srd import router as srd_router
from app.api.ws_dialogue import router as ws_dialogue_router
from app.api.ws_game import router as ws_router
from app.config import get_cors_origins
from app.db.database import async_session
from app.game.async_tasks import create_logged_task
from app.game.event_bus import EventType, GameEvent, event_bus
from app.llm.voxtral_client import tts_router
from app.security import (
    access_token_required,
    admin_access_token_required,
    request_has_valid_access_token,
    request_has_valid_admin_access_token,
    validate_access_token_configuration,
)
from app.services import campaign_dossier_service
from app.voice.base import AudioBlob
from app.voice.local_provider import kokoro_speed_for, kokoro_voice_for
from app.voice.router import voice_router

logger = logging.getLogger(__name__)


def _is_gm_narration_payload(payload: dict) -> bool:
    speaker_kind = payload.get("speaker_kind")
    if speaker_kind is not None:
        return speaker_kind == "gm"

    speaker = str(payload.get("speaker") or "").strip().casefold()
    return speaker in {"maître du jeu", "maitre du jeu", "gm"}


def _is_npc_dialogue_payload(payload: dict) -> bool:
    speaker_kind = payload.get("speaker_kind")
    if speaker_kind is not None:
        return speaker_kind == "npc"
    return payload.get("entry_kind") == "dialogue" and bool(
        str(payload.get("speaker") or "").strip()
    )


def _queue_tts_for_visible_event(
    event: GameEvent,
    *,
    db_session_factory: Any = async_session,
) -> None:
    payload = event.payload
    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        return

    narration_id = str(payload.get("narration_id") or event.event_id)
    if event.event_type == EventType.NARRATION and _is_gm_narration_payload(payload):
        voice = tts_router.gm_voice
        create_logged_task(
            tts_router.synthesize_and_broadcast(
                text,
                event.session_id,
                narration_id,
                voice=voice["voice_id_local"],
                lang=voice["lang"],
                speed=voice["speed"],
                speaker=str(payload.get("speaker") or "Maître du Jeu"),
                speaker_kind="gm",
            ),
            "tts.gm_narration",
        )
        return

    if event.event_type == EventType.DIALOGUE and _is_npc_dialogue_payload(payload):
        create_logged_task(
            _synthesize_npc_dialogue(
                event,
                text,
                narration_id,
                db_session_factory=db_session_factory,
            ),
            "tts.npc_dialogue",
        )


async def _broadcast_audio_blob(
    session_id: str,
    narration_id: str,
    blob: AudioBlob,
    *,
    speaker: str,
    speaker_kind: str,
) -> None:
    """Diffuse un ``AudioBlob`` déjà synthétisé via l'event ``AUDIO``.

    Reproduit le contrat de ``TtsRouter.synthesize_and_broadcast`` (séquence
    ``generating`` → ``ready`` avec ``audio_b64``) pour l'audio produit par le
    ``VoiceRouter`` côté narration PNJ (modes hybrid/realtime).
    """
    status_payload: dict[str, Any] = {"narration_id": narration_id, "status": "generating"}
    if speaker:
        status_payload["speaker"] = speaker
    if speaker_kind:
        status_payload["speaker_kind"] = speaker_kind

    await event_bus.publish_to_session(
        session_id,
        EventType.AUDIO,
        dict(status_payload),
        source="voice_router",
    )
    audio_b64 = base64.b64encode(blob.wav_bytes).decode("ascii")
    await event_bus.publish_to_session(
        session_id,
        EventType.AUDIO,
        {**status_payload, "status": "ready", "audio_b64": audio_b64},
        source="voice_router",
    )


async def _synthesize_npc_dialogue(
    event: GameEvent,
    text: str,
    narration_id: str,
    *,
    db_session_factory: Any = async_session,
) -> None:
    if not tts_router.tts_enabled or not tts_router.npc_voice_enabled:
        return

    voice_id = "ff_siwis"
    lang = "fr-fr"
    speed = 0.95
    speaker_id = str(event.payload.get("speaker_id") or "").strip()

    if speaker_id:
        try:
            async with db_session_factory() as db:
                campaign = await campaign_dossier_service.campaign_for_session(
                    event.session_id,
                    db,
                )
                persona = None
                if campaign is not None:
                    persona = await campaign_dossier_service.get_npc_persona(
                        campaign.id,
                        speaker_id,
                        db,
                    )
        except Exception:
            persona = None

        if persona is not None:
            # Modes hybrid/realtime : router via VoiceRouter pour que les personas
            # "rich" atteignent la voix Realtime (fallback Local automatique géré par
            # le router). En mode local (défaut), on conserve le chemin Kokoro direct
            # ci-dessous — comportement strictement identique.
            if voice_router.mode != "local":
                try:
                    blob = await voice_router.speak_for_persona(persona, text)
                    await _broadcast_audio_blob(
                        event.session_id,
                        narration_id,
                        blob,
                        speaker=str(event.payload.get("speaker") or ""),
                        speaker_kind="npc",
                    )
                    return
                except Exception as exc:  # défensif : jamais d'erreur visible joueur
                    logger.warning(
                        "VoiceRouter narration PNJ échec (%s) — fallback synthèse locale.",
                        exc,
                    )
            voice = persona.voice
            voice_id = voice.voice_id_local or kokoro_voice_for(voice, prefer_french=False)
            speed = kokoro_speed_for(voice)

    await tts_router.synthesize_and_broadcast(
        text,
        event.session_id,
        narration_id,
        voice=voice_id,
        lang=lang,
        speed=speed,
        speaker=str(event.payload.get("speaker") or ""),
        speaker_kind="npc",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: charger les paramètres TTS persistés
    tts_router._runtime = tts_router._load_runtime()

    async def publish_audio(session_id: str, payload: dict) -> None:
        await event_bus.publish_to_session(
            session_id,
            EventType.AUDIO,
            payload,
            source="tts_router",
        )

    tts_router.configure_audio_publisher(publish_audio)
    db_session_factory = getattr(app.state, "db_session_factory", async_session)
    event_bus.configure_event_hook(
        lambda event: _queue_tts_for_visible_event(
            event,
            db_session_factory=db_session_factory,
        )
    )
    yield
    event_bus.configure_event_hook(None)


def create_app() -> FastAPI:
    validate_access_token_configuration()

    app = FastAPI(
        title="RpgMaster",
        description="AI-powered D&D 5.2 Game Master",
        version="0.1.0",
        lifespan=lifespan,
    )
    app.state.db_session_factory = async_session

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-RpgMaster-Token"],
    )

    @app.middleware("http")
    async def require_local_access_token(request: Request, call_next):
        # GM/author-only routes outside /api/admin/* (e.g. the campaign gm-dossier,
        # which exposes GM-only secrets by design) are gated the same way admin
        # routes are: when a distinct ADMIN_ACCESS_TOKEN is configured, it alone
        # gates the route and the general access token is not also required.
        is_admin_route = request.url.path.startswith("/api/admin/") or request.url.path.endswith(
            "/gm-dossier"
        )
        if (
            is_admin_route
            and request.method != "OPTIONS"
            and admin_access_token_required()
            and not request_has_valid_admin_access_token(request)
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing admin access token."},
            )
        if (
            access_token_required()
            and request.url.path.startswith("/api/")
            and request.method != "OPTIONS"
            and not (is_admin_route and admin_access_token_required())
            and not request_has_valid_access_token(request)
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing access token."},
            )
        return await call_next(request)

    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
    app.include_router(campaign_router, prefix="/api/campaigns", tags=["campaigns"])
    app.include_router(session_router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(pregen_router, prefix="/api/characters", tags=["characters"])
    app.include_router(character_router, prefix="/api/characters", tags=["characters"])
    app.include_router(encounters_router, prefix="/api/encounters", tags=["encounters"])
    app.include_router(game_router, prefix="/api/game", tags=["game"])
    app.include_router(srd_router, prefix="/api/srd", tags=["srd"])
    app.include_router(ws_router, tags=["websocket"])
    app.include_router(ws_dialogue_router, tags=["websocket"])

    return app


app = create_app()
