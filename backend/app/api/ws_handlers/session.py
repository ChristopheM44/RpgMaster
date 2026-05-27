"""Session state and AI synchronization WebSocket action helpers."""
from __future__ import annotations

import logging
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws_payloads import (
    build_session_state_payload,
    build_session_state_payload_enriched,
    character_snapshot,
)
from app.game.runtime import session_manager
from app.models.character import Character
from app.services.rest_service import normalize_character_hit_dice

logger = logging.getLogger(__name__)


def _build_session_state_payload(session_id: str) -> dict[str, Any]:
    return build_session_state_payload(session_id, session_manager.get_session(session_id))


async def _build_session_state_payload_with_maps(
    session_id: str,
    db: AsyncSession,
) -> dict[str, Any]:
    return await build_session_state_payload_enriched(
        session_id,
        session_manager.get_session(session_id),
        db,
    )


async def sync_ai_control_from_db(
    session_id: str,
    active: Any,
    db: AsyncSession,
) -> bool:
    """Reconcile live AI-control flags with the Character table.

    Character control can be changed from REST screens before or during a live
    session. The combat engine relies on the persisted game snapshot and the
    TurnManager, so this keeps those copies aligned with the DB source of truth.
    """
    result = await db.execute(select(Character).where(Character.session_id == session_id))
    characters = result.scalars().all()
    if not characters:
        return False

    from app.game.ai_player_manager import register_ai_player, unregister_ai_player

    changed = False
    chars_data: dict[str, Any] = active.state_data.setdefault("characters", {})
    combatants_info: dict[str, Any] = active.state_data.get("combatants", {})

    for char in characters:
        if char.id not in chars_data:
            chars_data[char.id] = character_snapshot(char)
            changed = True
        cdata = chars_data[char.id]
        if cdata.get("is_ai") != char.is_ai:
            cdata["is_ai"] = char.is_ai
            changed = True
        cdata.setdefault("name", char.name)
        cdata.setdefault("hit_dice", dict(normalize_character_hit_dice(char)))
        cdata.setdefault("personality", dict(char.personality or {}))

        if char.id in combatants_info and combatants_info[char.id].get("is_ai") != char.is_ai:
            combatants_info[char.id]["is_ai"] = char.is_ai
            changed = True

        for entry in active.turn_manager._order:
            if entry.combatant_id == char.id:
                if entry.is_ai_controlled != char.is_ai:
                    entry.is_ai_controlled = char.is_ai
                    changed = True
                break

        if char.is_ai:
            before = len(active.ai_players)
            register_ai_player(active, char.id, cdata)
            changed = changed or len(active.ai_players) != before
        else:
            had_agent = char.id in active.ai_players
            unregister_ai_player(active, char.id)
            changed = changed or had_agent

    if changed:
        active.mark_dirty()
        await session_manager.save_state(session_id, db)

    return changed
