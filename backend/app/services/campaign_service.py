"""Campaign service — business logic for multi-session campaigns."""
from __future__ import annotations

import uuid
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.campaign import Campaign
from app.models.character import Character
from app.models.session import Session, SessionStatus


async def create_campaign(name: str, description: str, db: AsyncSession) -> Campaign:
    """Create a new empty campaign."""
    campaign = Campaign(
        id=str(uuid.uuid4()),
        name=name,
        description=description,
        session_ids=[],
        current_session_index=0,
        character_ids=[],
        xp_pool={},
    )
    db.add(campaign)
    await db.commit()
    await db.refresh(campaign)
    return campaign


async def get_campaign(campaign_id: str, db: AsyncSession) -> Optional[Campaign]:
    result = await db.execute(select(Campaign).where(Campaign.id == campaign_id))
    return result.scalar_one_or_none()


async def list_campaigns(db: AsyncSession) -> list[Campaign]:
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    return list(result.scalars().all())


async def attach_session(campaign_id: str, session_id: str, db: AsyncSession) -> Campaign:
    """Add an existing session to a campaign (at the end of the list)."""
    campaign = await get_campaign(campaign_id, db)
    if campaign is None:
        raise KeyError(f"Campaign {campaign_id} not found")

    ids = list(campaign.session_ids)
    if session_id not in ids:
        ids.append(session_id)
        campaign.session_ids = ids

    # Register characters from this session as campaign party members
    result = await db.execute(select(Character).where(Character.session_id == session_id))
    chars = result.scalars().all()
    char_ids = list(campaign.character_ids)
    for c in chars:
        if c.id not in char_ids:
            char_ids.append(c.id)
    campaign.character_ids = char_ids

    await db.commit()
    await db.refresh(campaign)
    return campaign


async def advance_to_next_session(
    campaign_id: str,
    new_session_name: str,
    db: AsyncSession,
) -> dict[str, Any]:
    """Complete the current session and create the next one.

    Transfers surviving characters (with current stats) to the new session.
    Returns {"campaign": campaign, "new_session_id": str, "characters_transferred": int}.
    """
    campaign = await get_campaign(campaign_id, db)
    if campaign is None:
        raise KeyError(f"Campaign {campaign_id} not found")

    # Create the new session
    new_session = Session(
        id=str(uuid.uuid4()),
        name=new_session_name,
        status=SessionStatus.LOBBY,
    )
    db.add(new_session)
    await db.flush()

    # Sync characters from the current session into campaign.character_ids
    # (in case attach_session was never explicitly called)
    if campaign.session_ids:
        current_sid = campaign.session_ids[campaign.current_session_index]
        sync_result = await db.execute(
            select(Character).where(Character.session_id == current_sid)
        )
        existing_ids = set(campaign.character_ids or [])
        char_ids = list(campaign.character_ids or [])
        for c in sync_result.scalars().all():
            if c.id not in existing_ids:
                char_ids.append(c.id)
                existing_ids.add(c.id)
        campaign.character_ids = char_ids

    # Transfer surviving characters
    transferred = 0
    if campaign.character_ids:
        result = await db.execute(
            select(Character).where(Character.id.in_(campaign.character_ids))
        )
        chars = result.scalars().all()
        xp_pool = dict(campaign.xp_pool)

        for old_char in chars:
            # Clone character into new session
            new_char = Character(
                id=str(uuid.uuid4()),
                name=old_char.name,
                player_name=old_char.player_name,
                is_ai=old_char.is_ai,
                species=old_char.species,
                char_class=old_char.char_class,
                level=old_char.level,
                background=old_char.background,
                ability_scores=dict(old_char.ability_scores),
                hp_current=old_char.hp_max,  # Full heal at session start
                hp_max=old_char.hp_max,
                hp_temp=0,
                equipment=list(old_char.equipment),
                spell_slots=dict(old_char.spell_slots),
                known_spells=list(old_char.known_spells),
                conditions=[],  # Clear conditions between sessions
                proficiencies=dict(old_char.proficiencies),
                personality=dict(old_char.personality),
                session_id=new_session.id,
            )
            db.add(new_char)
            xp_pool[new_char.id] = xp_pool.pop(old_char.id, 0)
            transferred += 1

        campaign.xp_pool = xp_pool

    # Update campaign
    ids = list(campaign.session_ids)
    ids.append(new_session.id)
    campaign.session_ids = ids
    campaign.current_session_index = len(ids) - 1

    await db.commit()
    await db.refresh(campaign)

    return {
        "campaign": campaign,
        "new_session_id": new_session.id,
        "characters_transferred": transferred,
    }


async def award_xp(
    campaign_id: str,
    character_id: str,
    xp: int,
    db: AsyncSession,
) -> Campaign:
    """Award XP to a character in the campaign's XP pool."""
    campaign = await get_campaign(campaign_id, db)
    if campaign is None:
        raise KeyError(f"Campaign {campaign_id} not found")

    pool = dict(campaign.xp_pool)
    pool[character_id] = pool.get(character_id, 0) + xp
    campaign.xp_pool = pool
    await db.commit()
    await db.refresh(campaign)
    return campaign
