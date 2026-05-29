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
        logger.warning(
            "persist_narration : échec persistance message session=%s : %s",
            session_id, exc,
        )


async def persist_roll_result(
    session_id: str,
    roll_payload: dict[str, Any],
    db: Optional[AsyncSession],
) -> None:
    """Persiste un résultat de jet (ROLL_RESULT) pour restaurer le récit au rechargement.

    Le payload complet du jet est stocké dans ``metadata`` afin que la restauration
    d'historique côté frontend reconstruise une carte de jet identique à l'affichage
    live (notation, DD, succès, détail). Fire-and-forget comme ``persist_narration``.

    Ces messages sont volontairement exclus de ``load_recent_messages`` : le MJ reçoit
    déjà les résultats de jets via le canal ``roll_results`` lors de la narration
    d'outcome, inutile de les réinjecter dans la fenêtre de contexte.
    """
    if db is None or not isinstance(roll_payload, dict) or not roll_payload:
        return
    label = str(roll_payload.get("label") or roll_payload.get("summary") or "Jet de dé")
    speaker = str(roll_payload.get("character_name") or "Système")
    await persist_narration(
        session_id,
        label,
        speaker,
        db,
        role=MessageRole.SYSTEM,
        message_type=MessageType.ROLL_RESULT,
        metadata=dict(roll_payload),
    )


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
            .where(Message.message_type != MessageType.ROLL_RESULT)
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
