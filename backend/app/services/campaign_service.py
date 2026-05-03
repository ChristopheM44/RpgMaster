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
    campaign = result.scalar_one_or_none()
    if campaign is None:
        return None

    changed = await normalize_campaign_sessions(campaign, db)
    if changed:
        await db.commit()
        await db.refresh(campaign)
    return campaign


async def list_campaigns(db: AsyncSession) -> list[Campaign]:
    result = await db.execute(select(Campaign).order_by(Campaign.created_at.desc()))
    campaigns = list(result.scalars().all())
    if not campaigns:
        return campaigns

    session_ids_result = await db.execute(select(Session.id))
    existing_session_ids = set(session_ids_result.scalars().all())

    changed = False
    for campaign in campaigns:
        changed |= _reconcile_campaign_sessions(campaign, existing_session_ids)

    if changed:
        await db.commit()
        for campaign in campaigns:
            await db.refresh(campaign)

    return campaigns


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
                hit_dice=dict(old_char.hit_dice or {}),
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


async def remove_session_references(session_id: str, db: AsyncSession) -> int:
    """Retire une session supprimée de toutes les campagnes qui la référencent."""
    result = await db.execute(select(Campaign))
    campaigns = list(result.scalars().all())
    changed = 0

    for campaign in campaigns:
        ids = list(campaign.session_ids or [])
        if session_id not in ids:
            continue

        remaining_ids = {sid for sid in ids if sid != session_id}
        if _reconcile_campaign_sessions(campaign, remaining_ids):
            changed += 1

    return changed


async def normalize_campaign_sessions(campaign: Campaign, db: AsyncSession) -> bool:
    """Supprime les références vers des sessions inexistantes et recale l'index courant."""
    ids = list(campaign.session_ids or [])
    if not ids:
        return _reconcile_campaign_sessions(campaign, set())

    result = await db.execute(select(Session.id).where(Session.id.in_(ids)))
    existing_session_ids = set(result.scalars().all())
    return _reconcile_campaign_sessions(campaign, existing_session_ids)


def _reconcile_campaign_sessions(campaign: Campaign, valid_session_ids: set[str]) -> bool:
    session_ids = list(campaign.session_ids or [])
    current_index = campaign.current_session_index

    filtered_ids = [session_id for session_id in session_ids if session_id in valid_session_ids]

    if not filtered_ids:
        normalized_index = 0
    else:
        removed_before_current = sum(
            1
            for index, session_id in enumerate(session_ids)
            if session_id not in valid_session_ids and index < current_index
        )
        normalized_index = current_index - removed_before_current
        normalized_index = max(0, min(normalized_index, len(filtered_ids) - 1))

    changed = (
        filtered_ids != session_ids
        or normalized_index != current_index
    )
    if changed:
        campaign.session_ids = filtered_ids
        campaign.current_session_index = normalized_index

    return changed
