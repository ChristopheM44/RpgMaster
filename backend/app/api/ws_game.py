"""WebSocket endpoint for real-time game communication.

Protocol summary
----------------

Client → Server (JSON):

    {"type": "join",   "character_id": "<id>"}
    {"type": "action", "action_type": "free_text|attack|end_turn|start_combat|take_rest",
                       "content": "Je cherche des pièges",
                       "target_id": "<id|null>"}
    {"type": "ping"}

Server → Client (JSON):

    {"event_type": "session_state", "session_id": "...", "payload": {...}, "timestamp": "..."}
    {"event_type": "narration",     "session_id": "...", "payload": {"text": "..."}, ...}
    {"event_type": "roll_result",   "session_id": "...", "payload": {...}, ...}
    {"event_type": "turn_start",    "session_id": "...", "payload": {"combatant_id": "..."}, ...}
    {"event_type": "phase_change",  "session_id": "...", "payload": {"phase": "..."}, ...}
    {"event_type": "combat_start",  "session_id": "...", "payload": {"combatants": [...]}, ...}
    {"event_type": "hp_changed", "session_id": "...", "payload": {"combatant_id": "...", "hp": 0}}

    {"event_type": "error",         "session_id": "...", "payload": {"message": "..."}, ...}
    {"event_type": "pong"}

Connection lifecycle
--------------------
1. Client connects: session is opened/loaded from DB, client receives ``session_state``.
2. Client sends ``join`` with its character_id → ``player_joined`` broadcast.
3. Client sends ``action`` messages → dispatched to the game layer → results broadcast.
4. Client disconnects: ``player_left`` broadcast, session closed if no more clients.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.connection_manager import ConnectionManager
from app.api.ws_handlers.rest import handle_take_rest, handle_short_rest
from app.api.ws_handlers.session import (
    sync_ai_control_from_db,
    _build_session_state_payload,
    _build_session_state_payload_with_maps,
)
from app.api.ws_handlers.equipment import (
    handle_equip_item,
    handle_use_item,
    handle_drop_item,
    handle_give_item,
    handle_give_currency,
    handle_identify_item,
    handle_asi_choice,
)
from app.api.ws_handlers.exploration import send_welcome_narration
from app.api.ws_handlers.combat import (
    handle_start_combat,
    handle_end_turn,
    handle_ai_turns,
    handle_reset_combat,
    handle_flee,
    handle_dash,
    handle_disengage,
    handle_move,
    handle_toggle_ai_control,
    handle_trigger_ai_reactions,
    consume_pending_combat_transition,
    reject_out_of_turn_action,
    combat_target_id,
    cleanup_inactive_npcs,
    handle_combat_end,
    combat_end_reason_from_removed,
    active_npc_ids,
)
from app.api.ws_payloads import build_combat_start_payload
from app.api.ws_schemas import (
    JoinMessage,
    PingMessage,
    PlayerActionMessage,
    ToggleAiControlMessage,
    TriggerAiReactionsMessage,
)
from app.config import settings
from app.db.database import async_session
from app.game.action_resolver import ActionResolver
from app.game.async_tasks import create_logged_task
from app.game.combat_triggers import prime_combat_from_aggressive_action
from app.game.event_bus import BACKPRESSURE_ERROR_CODE, EventType, GameEvent, event_bus
from app.game.runtime import session_manager
from app.models.session import SessionStatus
from app.security import websocket_has_valid_access_token
from app.services.encounter_service import encounter_service
from app.api.ws_handlers.lifecycle import (
    VALIDATION_ERROR_MESSAGE,
    character_belongs_to_session,
    send_ws_error,
)

logger = logging.getLogger(__name__)
router = APIRouter()
action_resolver = ActionResolver()
connection_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Relay task
# ---------------------------------------------------------------------------


async def _relay_events(websocket: WebSocket, queue: asyncio.Queue) -> None:
    """Background coroutine: forward events from *queue* to *websocket*."""
    try:
        while True:
            event: GameEvent = await queue.get()
            payload = event.model_dump(mode="json")
            await websocket.send_json(payload)
            if (
                event.event_type == EventType.ERROR
                and event.payload.get("code") == BACKPRESSURE_ERROR_CODE
            ):
                await websocket.close(code=1013)
                return
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.debug("Relay task ended: %s", exc)


def _db_session_factory(websocket: WebSocket) -> Any:
    app = websocket.scope.get("app")
    state = getattr(app, "state", None)
    return getattr(state, "db_session_factory", async_session)


# ---------------------------------------------------------------------------
# Action dispatcher
# ---------------------------------------------------------------------------


async def _dispatch_action(
    session_id: str,
    action: PlayerActionMessage,
    db: AsyncSession,
) -> None:
    """Process a player action through the full pipeline and broadcast results."""
    active = session_manager.get_session(session_id)
    if active is None:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"Session '{session_id}' is not active."},
            source="ws_game",
        )
        return

    if active.phase in (
        SessionStatus.EXPLORATION,
        SessionStatus.ENCOUNTER_START,
    ) and prime_combat_from_aggressive_action(
        active,
        action_type=action.action_type,
        content=action.content,
        target_id=action.target_id,
    ):
        await _consume_pending_combat_transition(session_id, active, db, force=True)
        return

    if active.phase == SessionStatus.COMBAT:
        await _sync_ai_control_from_db(session_id, active, db)
        current = active.turn_manager.current_turn
        if action.action_type == "end_turn" and current is not None and current.is_ai_controlled:
            await _handle_ai_turns(session_id, active, db)
            return
        if await _reject_out_of_turn_action(session_id, action, active, event_bus=event_bus):
            return

    # Guard : un joueur inconscient ne peut pas attaquer ni lancer de sort
    if action.action_type in ("attack", "cast_spell") and action.character_id:
        _combatants = active.state_data.get("combatants", {})
        _cdata = _combatants.get(action.character_id, {})
        if int(_cdata.get("hp", 1)) == 0:
            await event_bus.publish_to_session(
                session_id,
                EventType.NARRATION,
                {
                    "text": (
                        "Vous êtes inconscient(e) — effectuez votre jet de sauvegarde "
                        "contre la mort."
                    ),
                    "speaker": "Maître du Jeu",
                },
                source="ws_game",
            )
            return

    # Route special action types directly (bypass GM agent)
    if action.action_type == "flee":
        await _handle_flee(session_id, action, active, db)
        return

    if action.action_type == "move":
        await _handle_move(session_id, action, active, db)
        return

    if action.action_type == "dash":
        await _handle_dash(session_id, action, active, db)
        return

    if action.action_type == "disengage":
        await _handle_disengage(session_id, action, active, db)
        return

    if action.action_type == "end_turn":
        await _handle_end_turn(session_id, active, db)
        return

    if action.action_type == "start_combat":
        encounter_id: Optional[str] = action.content if action.content else None
        await _handle_start_combat(
            session_id,
            active,
            db,
            encounter_id=encounter_id,
            force=True,
        )
        return

    if action.action_type in ("take_rest", "long_rest"):
        await _handle_take_rest(session_id, active, db)
        return

    if action.action_type == "short_rest":
        await _handle_short_rest(session_id, action, active, db)
        return

    if action.action_type == "reset_combat":
        await _handle_reset_combat(session_id, active, db)
        return

    if action.action_type == "equip":
        await _handle_equip_item(session_id, action, active, db)
        return

    if action.action_type == "use_item":
        await _handle_use_item(session_id, action, active, db)
        return

    if action.action_type == "drop_item":
        await _handle_drop_item(session_id, action, active, db)
        return

    if action.action_type == "give_item":
        await _handle_give_item(session_id, action, active, db)
        return

    if action.action_type == "give_currency":
        await _handle_give_currency(session_id, action, active, db)
        return

    if action.action_type == "identify_item":
        await _handle_identify_item(session_id, action, active, db)
        return

    if action.action_type == "asi_choice":
        await _handle_asi_choice(session_id, action, active, db)
        return

    # Normal action: exploration scene flow or combat pipeline.
    if active.phase != SessionStatus.COMBAT:
        from app.services.narrative_flow_service import NarrativeFlowService

        active.turn_number += 1
        active.mark_dirty()

        await NarrativeFlowService().handle_exploration_action(
            session_id=session_id,
            action=action,
            active=active,
            action_resolver=action_resolver,
            db=db,
        )

        if await _consume_pending_combat_transition(
            session_id,
            active,
            db,
            force=active.phase == SessionStatus.ENCOUNTER_START,
        ):
            return

        await session_manager.save_state(session_id, db)
        return

    resolved_action = await action_resolver.resolve(
        session_id=session_id,
        action_type=action.action_type,
        content=action.content,
        character_id=action.character_id,
        target_id=_combat_target_id(action, active) or action.target_id,
        active=active,
        db=db,
        spell_id=action.spell_id,
        slot_level=action.slot_level,
    )

    if await _consume_pending_combat_transition(
        session_id,
        active,
        db,
        force=True,
    ):
        return

    # After resolution: check for inactive NPC combatants
    if active.phase == SessionStatus.COMBAT:
        if getattr(resolved_action, "mechanics", {}).get("error"):
            await session_manager.save_state(session_id, db)
            return
        removed_npcs = await _cleanup_inactive_npcs(session_id, active)
        if active.turn_manager.all_npcs_removed():
            await _handle_combat_end(
                session_id,
                active,
                db,
                reason=_combat_end_reason_from_removed(removed_npcs),
                removed_npcs=removed_npcs,
            )
            return
        # Auto-advance turn: one action = end of turn
        await _handle_end_turn(session_id, active, db)


# ---------------------------------------------------------------------------
# Background task helpers (keep the WS receive loop free from LLM latency)
# ---------------------------------------------------------------------------


async def _run_action_bg(session_id: str, action: PlayerActionMessage, factory: Any) -> None:
    """Dispatch a player action in a background task so pings remain responsive."""
    try:
        async with factory() as db:
            async with session_manager.session_lock(session_id):
                await _dispatch_action(session_id, action, db)
    except Exception as exc:
        logger.error("Unhandled error in _dispatch_action (bg): %s", exc, exc_info=True)
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Une erreur interne s'est produite. Réessayez."},
            source="ws_game",
        )


async def _run_welcome_bg(session_id: str, factory: Any) -> None:
    """Send welcome narration in a background task so pings remain responsive."""
    try:
        async with factory() as db:
            async with session_manager.session_lock(session_id):
                active = session_manager.get_session(session_id)
                if active and active.phase == SessionStatus.EXPLORATION:
                    await _send_welcome_narration(session_id, active, db)
    except Exception as exc:
        logger.warning("_run_welcome_bg: error: %s", exc)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws/game/{session_id}")
async def game_websocket(
    websocket: WebSocket,
    session_id: str,
) -> None:
    """Main WebSocket endpoint for real-time game communication."""
    db_session_factory = _db_session_factory(websocket)
    queue: asyncio.Queue | None = None
    relay_task: asyncio.Task | None = None
    registered_connection = False
    if not websocket_has_valid_access_token(websocket):
        await websocket.close(code=4401)
        return

    # Open and subscribe before accept so the client cannot trigger /start
    # while this handler is still missing session bus events.
    try:
        async with db_session_factory() as db:
            await session_manager.open_session(session_id, db)
    except KeyError:
        await websocket.accept()
        await websocket.send_json(
            {
                "event_type": EventType.ERROR,
                "session_id": session_id,
                "payload": {"message": f"Session '{session_id}' not found."},
            }
        )
        await websocket.close(code=4404)
        return

    queue = event_bus.subscribe(session_id, maxsize=settings.ws_event_queue_size)
    await websocket.accept()

    # 2. Register connection and start relaying queued events
    connection_manager.connect(session_id, websocket)
    registered_connection = True
    relay_task = create_logged_task(_relay_events(websocket, queue), "ws_game.relay_events")

    # 3. Send initial session state
    async with db_session_factory() as db:
        initial_payload = await _build_session_state_payload_with_maps(session_id, db)
    await websocket.send_json(
        {
            "event_type": EventType.SESSION_STATE,
            "session_id": session_id,
            "payload": initial_payload,
        }
    )

    character_id: Optional[str] = None

    try:
        # 4. Receive loop
        while True:
            try:
                raw = await websocket.receive_json()
            except Exception:
                break
            if not isinstance(raw, dict):
                await websocket.send_json(
                    {
                        "event_type": EventType.ERROR,
                        "session_id": session_id,
                        "payload": {"message": "Message WebSocket invalide."},
                    }
                )
                continue

            msg_type = raw.get("type", "")

            # --- ping ---------------------------------------------------
            if msg_type == "ping":
                try:
                    PingMessage(**raw)
                except ValidationError:
                    await send_ws_error(websocket, session_id, VALIDATION_ERROR_MESSAGE)
                    continue
                await websocket.send_json({"event_type": "pong", "payload": {}})
                continue

            # --- join ---------------------------------------------------
            if msg_type == "join":
                try:
                    join = JoinMessage(**raw)
                except ValidationError:
                    await send_ws_error(websocket, session_id, VALIDATION_ERROR_MESSAGE)
                    continue

                async with db_session_factory() as db:
                    async with session_manager.session_lock(session_id):
                        character_id = join.character_id
                        if not await character_belongs_to_session(session_id, character_id, db):
                            character_id = None
                            await send_ws_error(
                                websocket,
                                session_id,
                                "Personnage introuvable dans cette session.",
                            )
                            continue
                        await event_bus.publish_to_session(
                            session_id,
                            EventType.PLAYER_JOINED,
                            {"character_id": character_id},
                            source="ws_game",
                        )
                        logger.info(
                            "Player joined session %s with character %s.",
                            session_id,
                            character_id,
                        )

                        active_on_join = session_manager.get_session(session_id)
                        if active_on_join:
                            await _sync_ai_control_from_db(session_id, active_on_join, db)
                        if active_on_join and active_on_join.phase == SessionStatus.EXPLORATION:
                            create_logged_task(
                                _run_welcome_bg(session_id, db_session_factory),
                                "ws_game._run_welcome_bg",
                            )
                        elif active_on_join and active_on_join.phase == SessionStatus.COMBAT:
                            await websocket.send_json(
                                {
                                    "event_type": "combat_start",
                                    "session_id": session_id,
                                    "payload": _build_combat_start_payload(active_on_join),
                                }
                            )
                            current = active_on_join.turn_manager.current_turn
                            if current:
                                await websocket.send_json(
                                    {
                                        "event_type": EventType.TURN_START,
                                        "session_id": session_id,
                                        "payload": {
                                            "combatant_id": current.combatant_id,
                                            "combatant_name": current.name,
                                        },
                                    }
                                )
                                if current.is_ai_controlled:
                                    await _handle_ai_turns(session_id, active_on_join, db)
                continue

            # --- action -------------------------------------------------
            if msg_type == "action":
                try:
                    action = PlayerActionMessage(**raw)
                except ValidationError:
                    await send_ws_error(websocket, session_id, VALIDATION_ERROR_MESSAGE)
                    continue

                asyncio.create_task(_run_action_bg(session_id, action, db_session_factory))
                continue

            # --- toggle_ai_control --------------------------------------
            if msg_type == "toggle_ai_control":
                try:
                    msg = ToggleAiControlMessage(**raw)
                    async with db_session_factory() as db:
                        async with session_manager.session_lock(session_id):
                            await _handle_toggle_ai_control(
                                session_id,
                                character_id=msg.character_id,
                                next_is_ai=msg.is_ai,
                                db=db,
                            )
                except ValidationError:
                    await send_ws_error(websocket, session_id, VALIDATION_ERROR_MESSAGE)
                except Exception as exc:
                    logger.error("Unhandled error in toggle_ai_control: %s", exc, exc_info=True)
                    await event_bus.publish_to_session(
                        session_id,
                        EventType.ERROR,
                        {"message": f"Erreur toggle IA : {exc}"},
                        source="ws_game",
                    )
                continue

            # --- trigger_ai_reactions -----------------------------------
            if msg_type == "trigger_ai_reactions":
                try:
                    msg = TriggerAiReactionsMessage(**raw)
                    async with db_session_factory() as db:
                        async with session_manager.session_lock(session_id):
                            await _handle_trigger_ai_reactions(
                                session_id,
                                db,
                                trigger_character_id=msg.character_id,
                            )
                except ValidationError:
                    await send_ws_error(websocket, session_id, VALIDATION_ERROR_MESSAGE)
                except Exception as exc:
                    logger.error("Unhandled error in trigger_ai_reactions: %s", exc, exc_info=True)
                    await event_bus.publish_to_session(
                        session_id,
                        EventType.ERROR,
                        {"message": f"Erreur déclenchement IA : {exc}"},
                        source="ws_game",
                    )
                continue

            # --- unknown type -------------------------------------------
            await websocket.send_json(
                {
                    "event_type": EventType.ERROR,
                    "session_id": session_id,
                    "payload": {"message": f"Unknown message type: '{msg_type}'."},
                }
            )

    except WebSocketDisconnect:
        pass
    finally:
        if relay_task is not None:
            relay_task.cancel()
            await asyncio.gather(relay_task, return_exceptions=True)

        if queue is not None:
            event_bus.unsubscribe(session_id, queue)
        if registered_connection:
            connection_manager.disconnect(session_id, websocket)

        if character_id:
            await event_bus.publish_to_session(
                session_id,
                EventType.PLAYER_LEFT,
                {"character_id": character_id},
                source="ws_game",
            )

        if connection_manager.connection_count(session_id) == 0:
            try:
                async with async_session() as db:
                    async with session_manager.session_lock(session_id):
                        await session_manager.close_session(session_id, db)
            except Exception as exc:
                logger.warning("Error closing session %s on last disconnect: %s", session_id, exc)

        logger.info("WS closed: session=%s character=%s", session_id, character_id)


# ---------------------------------------------------------------------------
# Backwards-compatibility aliases and private bindings for legacy unit tests
# ---------------------------------------------------------------------------

from app.api.ws_payloads import (
    compute_ac_from_equipment as _compute_ac_from_equipment,
    monster_base_id as _monster_base_id,
    monster_instance_number as _monster_instance_number,
    monster_token as _monster_token,
    monster_token_for_combatant as _monster_token_for_combatant,
    monster_color as _monster_color,
    format_monster_actions as _format_monster_actions,
    character_snapshot as _character_snapshot,
)
from app.services.message_service import (
    load_recent_messages as load_recent_messages,
    persist_narration as persist_narration,
)
from app.api.ws_handlers.rest import handle_take_rest as _handle_take_rest
from app.api.ws_handlers.rest import handle_short_rest as _handle_short_rest
from app.api.ws_handlers.equipment import handle_equip_item as _handle_equip_item
from app.api.ws_handlers.equipment import handle_use_item as _handle_use_item
from app.api.ws_handlers.equipment import handle_drop_item as _handle_drop_item
from app.api.ws_handlers.equipment import handle_give_item as _handle_give_item
from app.api.ws_handlers.equipment import handle_give_currency as _handle_give_currency
from app.api.ws_handlers.equipment import handle_identify_item as _handle_identify_item
from app.api.ws_handlers.equipment import handle_asi_choice as _handle_asi_choice

from app.api.ws_handlers.combat import (
    _build_combat_summary as _build_combat_summary,
    _generate_encounter_end as _generate_encounter_end,
)

async def _generate_encounter_intro(
    session_id: str,
    active: Any,
    db: AsyncSession,
    combatants_info: dict[str, Any],
) -> Optional[str]:
    from app.api.ws_handlers.encounter_intro import generate_encounter_intro
    return await generate_encounter_intro(
        session_id,
        active,
        db,
        combatants_info,
        gm_agent=getattr(action_resolver, "_gm", None),
        event_bus=event_bus,
        load_recent_messages=load_recent_messages,
    )

_handle_start_combat = handle_start_combat
_handle_end_turn = handle_end_turn
_handle_ai_turns = handle_ai_turns
_handle_reset_combat = handle_reset_combat
_handle_flee = handle_flee
_handle_dash = handle_dash
_handle_disengage = handle_disengage
_handle_move = handle_move
_handle_toggle_ai_control = handle_toggle_ai_control
_handle_trigger_ai_reactions = handle_trigger_ai_reactions
async def _consume_pending_combat_transition(
    session_id: str,
    active: Any,
    db: AsyncSession,
    *,
    force: bool,
) -> bool:
    pending_transition = active.state_data.get("pending_phase_transition")
    if pending_transition != "COMBAT" or active.phase == SessionStatus.COMBAT:
        return False

    await _handle_start_combat(
        session_id,
        active,
        db,
        encounter_id=None,
        force=force,
    )
    active.state_data.pop("pending_phase_transition", None)
    active.mark_dirty()
    await session_manager.save_state(session_id, db)
    return True


_reject_out_of_turn_action = reject_out_of_turn_action
_combat_target_id = combat_target_id
_cleanup_inactive_npcs = cleanup_inactive_npcs
_handle_combat_end = handle_combat_end
_combat_end_reason_from_removed = combat_end_reason_from_removed
_active_npc_ids = active_npc_ids

_sync_ai_control_from_db = sync_ai_control_from_db
_build_session_state_payload = _build_session_state_payload
_build_session_state_payload_with_maps = _build_session_state_payload_with_maps

_send_welcome_narration = send_welcome_narration
_build_combat_start_payload = build_combat_start_payload
