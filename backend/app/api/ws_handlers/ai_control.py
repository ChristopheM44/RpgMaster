"""AI combat turn handling for the game WebSocket facade."""
from __future__ import annotations

from collections.abc import Awaitable
from typing import Any, Callable

from sqlalchemy.ext.asyncio import AsyncSession

from app.game.ai_player_manager import AIPlayerManager
from app.game.constants import INACTIVE_STATUSES
from app.game.event_bus import EventType


async def handle_ai_turns(
    session_id: str,
    active: Any,
    db: AsyncSession,
    *,
    event_bus: Any,
    action_resolver: Any,
    session_manager: Any,
    session_state_payload: Callable[[], dict[str, Any]],
    cleanup_inactive_npcs: Callable[[str, Any], Awaitable[list[dict[str, Any]]]],
    handle_combat_end: Callable[..., Awaitable[None]],
    combat_end_reason_from_removed: Callable[[list[dict[str, Any]]], str],
    auto_death_save: Callable[[str, str, str, Any], Awaitable[None]],
    source: str = "ws_game",
) -> None:
    """Trigger consecutive AI-controlled turns, then announce the next human."""
    ai_manager = AIPlayerManager()

    while True:
        current = active.turn_manager.current_turn
        if current is None or not current.is_ai_controlled:
            break

        await event_bus.publish_to_session(
            session_id,
            EventType.TURN_START,
            {"combatant_id": current.combatant_id, "combatant_name": current.name},
            source=source,
        )

        cdata = active.state_data.get("combatants", {}).get(current.combatant_id, {})
        if cdata.get("is_player") and int(cdata.get("hp", 1)) == 0:
            death_saves = cdata.get("death_saves", {})
            if not death_saves.get("stable") and not cdata.get("dead"):
                await auto_death_save(session_id, current.combatant_id, current.name, active)
            active.turn_manager.next_turn()
            active.turn_number += 1
            active.round_number = active.turn_manager.round_number
            active.mark_dirty()
            continue

        agent = active.ai_players.get(current.combatant_id)
        if agent is not None:
            await ai_manager.process_ai_turns(
                session_id,
                active,
                action_resolver,
                db=db,
                max_turns=1,
            )
            removed_npcs = await cleanup_inactive_npcs(session_id, active)
            if active.turn_manager.all_npcs_removed():
                await handle_combat_end(
                    session_id,
                    active,
                    db,
                    reason=combat_end_reason_from_removed(removed_npcs),
                    removed_npcs=removed_npcs,
                )
                return
            continue

        combatants_info: dict[str, Any] = active.state_data.get("combatants", {})
        monster_info = combatants_info.get(current.combatant_id, {})
        if str(monster_info.get("status", "active")).lower() in INACTIVE_STATUSES:
            active.turn_manager.remove_combatant(current.combatant_id)
            active.mark_dirty()
            continue

        await action_resolver.resolve(
            session_id=session_id,
            action_type="attack",
            content=None,
            character_id=current.combatant_id,
            target_id=None,
            active=active,
            db=db,
            actor_kind="monster",
            actor_name=current.name,
        )

        removed_npcs = await cleanup_inactive_npcs(session_id, active)
        if active.turn_manager.all_npcs_removed():
            await handle_combat_end(
                session_id,
                active,
                db,
                reason=combat_end_reason_from_removed(removed_npcs),
                removed_npcs=removed_npcs,
            )
            return

        active.turn_manager.next_turn()
        active.turn_number += 1
        active.round_number = active.turn_manager.round_number

    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    current = active.turn_manager.current_turn
    if current:
        await event_bus.publish_to_session(
            session_id,
            EventType.TURN_START,
            {"combatant_id": current.combatant_id, "combatant_name": current.name},
            source=source,
        )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        session_state_payload(),
        source=source,
    )
