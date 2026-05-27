"""Rest WebSocket action handlers."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws_schemas import PlayerActionMessage
from app.game.event_bus import EventType, event_bus
from app.game.runtime import rest_service, session_manager
from app.api.ws_payloads import build_session_state_payload
from app.services.rest_service import RestServiceError

logger = logging.getLogger(__name__)


def _build_session_state_payload(session_id: str) -> dict[str, Any]:
    return build_session_state_payload(session_id, session_manager.get_session(session_id))


async def handle_take_rest(session_id: str, active: Any, db: AsyncSession) -> None:
    """Long rest: restore full HP, spell slots and hit dice."""
    await rest_service.long_rest(
        session_id=session_id,
        active=active,
        db=db,
        session_state_payload=lambda: _build_session_state_payload(session_id),
    )


async def handle_short_rest(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Short rest: spend hit dice chosen by the player."""
    try:
        await rest_service.short_rest(
            session_id=session_id,
            active=active,
            db=db,
            hit_dice_spend=action.hit_dice_spend or {},
            session_state_payload=lambda: _build_session_state_payload(session_id),
        )
    except RestServiceError as exc:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": str(exc)},
            source="ws_game",
        )
