"""Service de persistance et lecture des messages narratifs en base de données."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import ContextMessage
from app.config import settings
from app.models.message import Message, MessageRole, MessageType

logger = logging.getLogger(__name__)


_ROLE_TO_CONTEXT = {
    MessageRole.GM: "gm",
    MessageRole.PLAYER: "player",
    MessageRole.SYSTEM: "system",
}


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


async def load_recent_messages(
    session_id: str,
    db: AsyncSession,
    limit: Optional[int] = None,
) -> list[ContextMessage]:
    """Relit les derniers messages persistés d'une session, ordre chronologique.

    Utilisé par ``action_resolver`` pour alimenter l'historique conversationnel
    du MJ et maintenir la cohérence narrative entre les échanges.

    En cas d'erreur DB, retourne une liste vide sans propager (le gameplay
    continue avec un contexte vide plutôt que de planter).
    """
    effective_limit = limit if limit is not None else settings.max_context_messages
    if effective_limit <= 0:
        return []

    try:
        stmt = (
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.desc())
            .limit(effective_limit)
        )
        result = await db.execute(stmt)
        rows = list(result.scalars().all())
    except Exception as exc:
        logger.warning(
            "load_recent_messages : échec lecture messages session=%s : %s",
            session_id,
            exc,
        )
        return []

    # La requête retourne les plus récents en premier ; on inverse pour remettre
    # l'historique en ordre chronologique (ce que le LLM attend).
    rows.reverse()

    context: list[ContextMessage] = []
    for msg in rows:
        ctx_role = _ROLE_TO_CONTEXT.get(msg.role, "system")
        context.append(
            ContextMessage(
                role=ctx_role,
                speaker=msg.speaker,
                content=msg.content,
                metadata=msg.metadata_ or {},
            )
        )
    return context
