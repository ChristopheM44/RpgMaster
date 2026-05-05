"""WebSocket lifecycle helpers for connection-level messages."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.game.event_bus import EventType
from app.models.character import Character

VALIDATION_ERROR_MESSAGE = "Message WebSocket invalide."


async def character_belongs_to_session(
    session_id: str,
    character_id: str,
    db: AsyncSession,
) -> bool:
    """Return True when a joining character exists in the target session."""
    result = await db.execute(
        select(Character.id).where(
            Character.id == character_id,
            Character.session_id == session_id,
        )
    )
    return result.scalar_one_or_none() is not None


async def send_ws_error(websocket, session_id: str, message: str) -> None:
    await websocket.send_json({
        "event_type": EventType.ERROR,
        "session_id": session_id,
        "payload": {"message": message},
    })
