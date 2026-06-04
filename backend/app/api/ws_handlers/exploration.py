"""Exploration WebSocket action handlers."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.game.event_bus import EventType, event_bus
from app.services.message_service import persist_narration

logger = logging.getLogger(__name__)


async def send_welcome_narration(session_id: str, active: Any, db: AsyncSession) -> None:
    """Demande au GMAgent de décrire la scène courante quand un joueur rejoint en exploration."""
    # Guard d'idempotence : atomique en asyncio (pas d'await avant cette ligne)
    if active.state_data.get("welcome_narration_sent") or active.state_data.get(
        "_opening_narration_in_progress"
    ):
        return
    active.state_data["welcome_narration_sent"] = True

    try:
        await event_bus.publish_to_session(
            session_id,
            EventType.AI_THINKING,
            {"agent_kind": "gm", "thinking": True},
            source="ws_game",
        )
        from app.game.action_resolver import ActionResolver
        from app.services import campaign_dossier_service

        game_state = dict(active.state_data)
        gm_prompt_context = await campaign_dossier_service.build_gm_prompt_context(
            session_id,
            db,
            active.state_data,
        )
        if gm_prompt_context:
            game_state["_gm_prompt_context"] = gm_prompt_context

        action_resolver = ActionResolver()
        gm_response = await action_resolver._gm.narrate(
            game_state=game_state,
            player_action=None,
        )
        welcome_text = (
            gm_response.narration
            if gm_response
            else ("Bienvenue dans l'aventure ! Décrivez votre action pour commencer.")
        )
    except Exception as exc:
        logger.warning("send_welcome_narration: GMAgent failed: %s", exc)
        welcome_text = "Bienvenue dans l'aventure ! Décrivez votre action pour commencer."
    finally:
        await event_bus.publish_to_session(
            session_id,
            EventType.AI_THINKING,
            {"agent_kind": "gm", "thinking": False},
            source="ws_game",
        )

    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": welcome_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, welcome_text, "Maître du Jeu", db)
