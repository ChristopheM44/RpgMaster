"""XP persistence service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.xp import level_from_xp, xp_to_next_level
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession
from app.game.state_sync import sync_character_state
from app.models.character import Character
from app.services import campaign_dossier_service


class XPServiceError(Exception):
    """Base XP service error."""


class CharacterNotFoundError(XPServiceError):
    """The requested character does not exist."""


@dataclass
class XPGrantResult:
    character_id: str
    old_xp: int
    new_xp: int
    current_level: int
    target_level: int
    level_up_available: bool


class XPService:
    async def grant_xp(
        self,
        *,
        session_id: str,
        character_id: str,
        amount: int,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> XPGrantResult:
        if int(amount) < 0:
            raise ValueError("XP amount must be non-negative")

        result = await db.execute(select(Character).where(Character.id == character_id))
        char = result.scalar_one_or_none()
        if char is None:
            raise CharacterNotFoundError("Personnage introuvable")

        old_xp = int(getattr(char, "xp", 0) or 0)
        new_xp = old_xp + int(amount)
        current_level = int(char.level or 1)
        target_level = level_from_xp(new_xp)
        char.xp = new_xp

        campaign = await campaign_dossier_service.campaign_for_session(session_id, db)
        if campaign is not None:
            pool = dict(campaign.xp_pool or {})
            pool[character_id] = int(pool.get(character_id, 0) or 0) + int(amount)
            campaign.xp_pool = pool

        await db.commit()
        await db.refresh(char)

        remaining = xp_to_next_level(new_xp, current_level)
        sync_character_state(
            active,
            character_id,
            xp=new_xp,
            xp_to_next_level=remaining,
        )
        await event_bus.publish_to_session(
            session_id,
            EventType.XP_UPDATED,
            {
                "character_id": character_id,
                "old_xp": old_xp,
                "new_xp": new_xp,
                "xp": new_xp,
                "level": current_level,
                "target_level": target_level,
                "xp_to_next_level": remaining,
            },
            source="xp_service",
        )
        level_up_available = target_level > current_level
        if level_up_available:
            await event_bus.publish_to_session(
                session_id,
                EventType.LEVEL_UP_AVAILABLE,
                {
                    "character_id": character_id,
                    "current_level": current_level,
                    "target_level": target_level,
                    "xp": new_xp,
                },
                source="xp_service",
            )

        return XPGrantResult(
            character_id=character_id,
            old_xp=old_xp,
            new_xp=new_xp,
            current_level=current_level,
            target_level=target_level,
            level_up_available=level_up_available,
        )


xp_service = XPService()
