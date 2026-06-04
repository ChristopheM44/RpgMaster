"""WebSocket endpoint pour dialogue Realtime bidi avec un PNJ.

Endpoint : ``/ws/dialogue/{session_id}/{persona_id}``

Flux :
1. Le frontend ouvre une connexion WS et envoie l'audio joueur en PCM16 base64.
2. Le backend ouvre une session OpenAI Realtime configurée avec la persona du PNJ
   (instructions = brief persona + directives vocales).
3. Les chunks audio sont bridgés dans les deux sens en parallèle.
4. À la fermeture, la transcription complète est publiée sur le WS principal
   (`/ws/game/{session_id}`) comme event `dialogue_transcript` pour que le MJ
   puisse en tenir compte dans les narrations suivantes.

Messages client → serveur (JSON) :
- `{"type": "user_audio", "audio_b64": "..."}` — chunk audio PCM16 base64
- `{"type": "commit"}` — fin de tour utilisateur (déclenche réponse IA)
- `{"type": "cancel"}` — interrompt la réponse en cours
- `{"type": "close"}` — fermeture propre (équivaut à WS close)

Messages serveur → client (JSON) :
- `{"type": "openai_event", "event": {...}}` — forward des events Realtime bruts
- `{"type": "error", "message": "..."}` — erreur applicative
- `{"type": "session_ready"}` — session OpenAI ouverte et configurée
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.agents.persona import BasePersona, NPCPersona, persona_from_dict
from app.config import settings
from app.game.event_bus import EventType, event_bus
from app.security import websocket_has_valid_access_token
from app.services import campaign_dossier_service
from app.voice.realtime_session import RealtimeSession

logger = logging.getLogger(__name__)

router = APIRouter()

# Inactivité après laquelle on ferme la session Realtime pour éviter de gaspiller
# des crédits OpenAI si le joueur a abandonné.
_IDLE_TIMEOUT_SECONDS = 30.0


def _db_session_factory(websocket: WebSocket) -> Any:
    app = websocket.scope.get("app")
    factory: async_sessionmaker | None = getattr(
        app.state if app is not None else None, "db_session_factory", None
    )
    if factory is None:
        raise RuntimeError("db_session_factory not registered on app.state")
    return factory


async def _load_persona_brief(
    session_id: str,
    persona_id: str,
    websocket: WebSocket,
) -> tuple[BasePersona, str] | None:
    """Récupère la persona + brief texte rendu pour Realtime.

    Retourne ``(persona, brief)`` ou ``None`` si introuvable (avec close du WS).
    """
    factory = _db_session_factory(websocket)
    async with factory() as db:
        campaign = await campaign_dossier_service.campaign_for_session(session_id, db)
        if campaign is None:
            await websocket.send_json(
                {"type": "error", "message": f"Session inconnue : {session_id}"}
            )
            await websocket.close(code=4404)
            return None
        persona = await campaign_dossier_service.get_npc_persona(campaign.id, persona_id, db)
    if persona is None:
        await websocket.send_json({"type": "error", "message": f"Persona inconnue : {persona_id}"})
        await websocket.close(code=4404)
        return None

    # Brief MJ-only (avec secrets) — la Realtime API joue le rôle complet
    brief = _render_persona_brief(persona)
    return persona, brief


def _render_persona_brief(persona: BasePersona) -> str:
    """Sérialise la persona pour OpenAI Realtime.

    Réutilise la macro Jinja `_persona_render.j2` en mode `include_hidden=True`
    pour que l'IA Realtime ait toutes les motivations cachées et secrets.
    """
    from jinja2 import Environment, FileSystemLoader, select_autoescape

    from app.agents.base_agent import _PROMPTS_DIR

    env = Environment(
        loader=FileSystemLoader(str(_PROMPTS_DIR)),
        autoescape=select_autoescape([]),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.from_string(
        "{% import '_persona_render.j2' as P %}"
        "Tu incarnes ce personnage en jeu de rôle interactif. "
        "Respecte sa voix, ses motivations et ses limites de savoir.\n\n"
        "{{ P.render_persona(persona, include_hidden=True) }}"
    )
    return template.render(persona=persona)


@router.websocket("/ws/dialogue/{session_id}/{persona_id}")
async def dialogue_websocket(
    websocket: WebSocket,
    session_id: str,
    persona_id: str,
) -> None:
    """Bridge bidirectionnel client ↔ OpenAI Realtime pour dialogue PNJ."""
    if not websocket_has_valid_access_token(websocket):
        await websocket.close(code=4401)
        return

    await websocket.accept()

    if not settings.openai_realtime_api_key:
        await websocket.send_json(
            {
                "type": "error",
                "message": (
                    "OpenAI Realtime non configurée. "
                    "Définissez OPENAI_REALTIME_API_KEY pour activer ce mode."
                ),
            }
        )
        await websocket.close(code=4400)
        return

    loaded = await _load_persona_brief(session_id, persona_id, websocket)
    if loaded is None:
        return
    persona, brief = loaded

    session = RealtimeSession(
        api_key=settings.openai_realtime_api_key,
        voice=persona.voice,
    )
    try:
        await session.connect(instructions=brief)
    except Exception as exc:
        logger.warning(
            "ws_dialogue: connexion Realtime échouée (session=%s persona=%s) : %s",
            session_id,
            persona_id,
            exc,
        )
        await websocket.send_json(
            {"type": "error", "message": f"Connexion Realtime impossible : {exc}"}
        )
        await websocket.close(code=1011)
        return

    await websocket.send_json({"type": "session_ready", "persona_id": persona_id})

    client_task = asyncio.create_task(_forward_client_to_openai(websocket, session))
    openai_task = asyncio.create_task(_forward_openai_to_client(websocket, session))

    try:
        done, pending = await asyncio.wait(
            {client_task, openai_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    finally:
        await session.close()
        await _publish_transcript(session_id, persona_id, session)
        try:
            await websocket.close()
        except Exception:
            pass


async def _forward_client_to_openai(
    websocket: WebSocket,
    session: RealtimeSession,
) -> None:
    """Reçoit les messages JSON du client et les forward au WS OpenAI Realtime."""
    while True:
        try:
            message = await asyncio.wait_for(
                websocket.receive_text(), timeout=_IDLE_TIMEOUT_SECONDS
            )
        except TimeoutError:
            logger.info("ws_dialogue: idle timeout, closing session")
            return
        except WebSocketDisconnect:
            return

        try:
            event = json.loads(message)
        except json.JSONDecodeError:
            await websocket.send_json({"type": "error", "message": "JSON invalide"})
            continue

        etype = str(event.get("type") or "")
        if etype == "user_audio":
            import base64

            audio_b64 = event.get("audio_b64") or ""
            try:
                pcm16 = base64.b64decode(audio_b64)
            except Exception:
                await websocket.send_json({"type": "error", "message": "audio_b64 invalide"})
                continue
            await session.send_user_audio(pcm16)
        elif etype == "commit":
            await session.commit_user_audio()
        elif etype == "cancel":
            await session.cancel_response()
        elif etype == "close":
            return
        else:
            await websocket.send_json(
                {"type": "error", "message": f"Type message inconnu : {etype}"}
            )


async def _forward_openai_to_client(
    websocket: WebSocket,
    session: RealtimeSession,
) -> None:
    """Forward les events OpenAI Realtime au client."""
    try:
        async for event in session.iter_events():
            try:
                await websocket.send_json({"type": "openai_event", "event": event})
            except Exception:
                return
    except Exception as exc:
        logger.warning("ws_dialogue: stream OpenAI Realtime interrompu : %s", exc)


async def _publish_transcript(
    session_id: str,
    persona_id: str,
    session: RealtimeSession,
) -> None:
    """Publie la transcription complète sur le bus pour le MJ."""
    payload = {
        "persona_id": persona_id,
        "transcript": session.transcript.to_payload(),
    }
    try:
        await event_bus.publish_to_session(
            session_id,
            EventType.DIALOGUE,
            payload,
            source="ws_dialogue",
        )
    except Exception as exc:
        logger.warning(
            "ws_dialogue: publication transcript échouée (session=%s) : %s",
            session_id,
            exc,
        )


# Utilisé par les tests pour vérifier le rendu du brief sans toucher au WS.
__all__ = ["router", "_render_persona_brief", "_load_persona_brief"]

# Re-export pour testabilité — permet à _load_persona_brief de référencer
# `persona_from_dict` et `NPCPersona` même si non utilisés directement ici.
_ = (persona_from_dict, NPCPersona)
