"""Service de persistance des messages narratifs en base de données."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.message import Message, MessageRole, MessageType

logger = logging.getLogger(__name__)


async def persist_narration(
    session_id: str,
    content: str,
    speaker: str,
    db: AsyncSession,
    role: MessageRole = MessageRole.GM,
    message_type: MessageType = MessageType.NARRATION,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """Persiste un message narratif en base de données.

    Appelé en fire-and-forget depuis action_resolver et ws_game.
    En cas d'erreur, logge sans propager pour ne pas bloquer le gameplay.
    """
    try:
        msg = Message(
            session_id=session_id,
            role=role,
            speaker=speaker,
            message_type=message_type,
            content=content,
            metadata_=metadata,
        )
        db.add(msg)
        await db.commit()
    except Exception as exc:
        logger.warning("persist_narration : échec persistance message session=%s : %s", session_id, exc)
