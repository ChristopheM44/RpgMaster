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
import json
import logging
import random
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import AgentContext
from app.db.database import get_db
from app.game.action_resolver import ActionResolver
from app.game.event_bus import EventType, GameEvent, event_bus
from app.game.session_manager import SessionManager
from app.game.turn_manager import CombatantInfo
from app.models.character import Character
from app.models.session import SessionStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# SRD data path
# ---------------------------------------------------------------------------

_SRD_DIR = Path(__file__).parent.parent / "engine" / "srd_data"

# ---------------------------------------------------------------------------
# Module-level session manager (shared across all WS connections)
# ---------------------------------------------------------------------------

session_manager = SessionManager()
action_resolver = ActionResolver()

# ---------------------------------------------------------------------------
# Incoming message schemas
# ---------------------------------------------------------------------------


class JoinMessage(BaseModel):
    type: str  # "join"
    character_id: str


class PlayerActionMessage(BaseModel):
    type: str  # "action"
    action_type: str  # free_text|attack|cast_spell|move|end_turn|start_combat|take_rest
    content: Optional[str] = None
    target_id: Optional[str] = None
    character_id: Optional[str] = None
    spell_id: Optional[str] = None    # cast_spell only
    slot_level: Optional[int] = None  # cast_spell only


class PingMessage(BaseModel):
    type: str  # "ping"


# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------


class ConnectionManager:
    """Tracks all active WebSocket connections grouped by session."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    def connect(self, session_id: str, websocket: WebSocket) -> None:
        self._connections.setdefault(session_id, set()).add(websocket)
        logger.debug(
            "WS connected: session=%s total=%d",
            session_id,
            len(self._connections[session_id]),
        )

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(session_id, set())
        connections.discard(websocket)
        if not connections:
            self._connections.pop(session_id, None)
        logger.debug("WS disconnected: session=%s", session_id)

    def connection_count(self, session_id: str) -> int:
        return len(self._connections.get(session_id, set()))

    async def broadcast(self, session_id: str, data: dict[str, Any]) -> None:
        """Send *data* to all WebSocket clients connected to *session_id*."""
        dead: set[WebSocket] = set()
        for ws in list(self._connections.get(session_id, set())):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    async def send_to(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        """Send *data* to a single WebSocket client."""
        try:
            await websocket.send_json(data)
        except Exception as exc:
            logger.warning("Failed to send to WS client: %s", exc)


# Module-level singleton
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
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.debug("Relay task ended: %s", exc)


# ---------------------------------------------------------------------------
# Session state payload builder
# ---------------------------------------------------------------------------


def _build_session_state_payload(session_id: str) -> dict[str, Any]:
    """Build the ``session_state`` event payload from the active session.

    Maps backend TurnEntry field names to frontend-compatible names:
    combatant_id → id, initiative_total → initiative, is_ai_controlled → is_ai.
    """
    active = session_manager.get_session(session_id)
    if active is None:
        return {"session_id": session_id, "phase": "unknown"}

    turn_data = active.turn_manager.to_dict()

    def _map_entry(e: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": e.get("combatant_id", ""),
            "name": e.get("name", ""),
            "initiative": e.get("initiative_total", 0),
            "is_ai": e.get("is_ai_controlled", False),
            "is_player": e.get("is_player", True),
        }

    return {
        "session_id": session_id,
        "phase": active.phase.value,
        "turn_number": active.turn_number,
        "round_number": active.round_number,
        "turn_order": [_map_entry(e) for e in turn_data.get("order", [])],
        "current_turn_index": turn_data.get("index", 0),
        "valid_transitions": [
            s.value for s in active.game_loop.get_valid_transitions(active.phase)
        ],
    }


# ---------------------------------------------------------------------------
# Combat helpers
# ---------------------------------------------------------------------------


async def _remove_dead_combatants(session_id: str, active: Any) -> None:
    """Remove NPCs with hp <= 0 from the turn order and broadcast narration."""
    combatants: dict[str, Any] = active.state_data.get("combatants", {})
    dead_ids = [
        cid
        for cid, cdata in combatants.items()
        if int(cdata.get("hp", 1)) <= 0 and not cdata.get("is_player", True)
    ]
    for cid in dead_ids:
        removed = active.turn_manager.remove_combatant(cid)
        if removed:
            name = combatants[cid].get("name", cid)
            await event_bus.publish_to_session(
                session_id,
                EventType.NARRATION,
                {"text": f"{name} a été vaincu !", "speaker": "Maître du Jeu"},
                source="ws_game",
            )
            active.mark_dirty()


async def _handle_combat_end(session_id: str, active: Any, db: AsyncSession) -> None:
    """Wrap up combat: transition to EXPLORATION and notify clients."""
    active.turn_manager.reset()
    active.phase = SessionStatus.EXPLORATION
    active.state_data.pop("combatants", None)
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.EXPLORATION.value},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {
            "text": "Victoire ! Tous les ennemis ont été vaincus. Le calme revient.",
            "speaker": "Maître du Jeu",
        },
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


# ---------------------------------------------------------------------------
# Special action handlers
# ---------------------------------------------------------------------------


async def _handle_start_combat(session_id: str, active: Any, db: AsyncSession) -> None:
    """Spawn a random encounter, roll initiative, and start combat."""
    # Load a random low-CR monster
    monsters_path = _SRD_DIR / "monsters.json"
    with monsters_path.open(encoding="utf-8") as f:
        monsters_data = json.load(f)

    candidates = [m for m in monsters_data["monsters"] if 0 < m["cr"] <= 1]
    if not candidates:
        candidates = monsters_data["monsters"][:1]
    monster = random.choice(candidates)

    monster_id = f"{monster['id']}_1"

    # Build combatant maps
    characters_data: dict[str, Any] = active.state_data.get("characters", {})
    combatants_list: list[CombatantInfo] = []
    combatants_info: dict[str, Any] = {}

    for char_id, cdata in characters_data.items():
        dex = int(cdata.get("dex", 10))
        dex_mod = (dex - 10) // 2
        combatants_list.append(
            CombatantInfo(
                combatant_id=char_id,
                name=cdata["name"],
                dex_score=dex,
                is_player=True,
                is_ai_controlled=bool(cdata.get("is_ai", False)),
            )
        )
        combatants_info[char_id] = {
            "name": cdata["name"],
            "hp": int(cdata.get("hp", 10)),
            "hp_max": int(cdata.get("hp_max", 10)),
            "is_player": True,
            "is_ai": bool(cdata.get("is_ai", False)),
            "ac": 10 + dex_mod,
            "attack_bonus": 3,
            "damage_notation": "1d6+2",
        }

    monster_dex = int(monster["ability_scores"].get("dexterity", 10))
    monster_actions = monster.get("actions", [])
    first_action = monster_actions[0] if monster_actions else {}
    monster_name = monster.get("name_fr", monster["name"])

    combatants_list.append(
        CombatantInfo(
            combatant_id=monster_id,
            name=monster_name,
            dex_score=monster_dex,
            is_player=False,
            is_ai_controlled=True,
        )
    )
    combatants_info[monster_id] = {
        "name": monster_name,
        "hp": int(monster["hp"]),
        "hp_max": int(monster["hp"]),
        "is_player": False,
        "is_ai": True,
        "ac": int(monster["ac"]),
        "attack_bonus": int(first_action.get("attack_bonus", 2)),
        "damage_notation": first_action.get("damage_dice", "1d4"),
    }

    # Roll initiative and set up TurnManager
    turn_entries = active.turn_manager.setup_combat(combatants_list)
    active.state_data["combatants"] = combatants_info
    active.phase = SessionStatus.COMBAT
    active.round_number = 1
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    # Broadcast phase change
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.COMBAT.value},
        source="ws_game",
    )

    # Broadcast full combatant list for CombatTracker
    combat_combatants = [
        {
            "id": entry.combatant_id,
            "name": combatants_info[entry.combatant_id]["name"],
            "initiative": entry.initiative_total,
            "hp_current": combatants_info[entry.combatant_id]["hp"],
            "hp_max": combatants_info[entry.combatant_id]["hp_max"],
            "is_ai": not combatants_info[entry.combatant_id]["is_player"],
            "conditions": [],
            "is_active": (i == 0),
        }
        for i, entry in enumerate(turn_entries)
    ]
    await event_bus.publish_to_session(
        session_id,
        "combat_start",
        {"combatants": combat_combatants},
        source="ws_game",
    )

    # Updated session state (includes new turn order)
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )

    # Narration d'introduction
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {
            "text": (
                f"Un {monster_name} surgit de l'ombre ! "
                "L'initiative est lancée — le combat commence !"
            ),
            "speaker": "Maître du Jeu",
        },
        source="ws_game",
    )

    # Announce first turn (or trigger AI turns if monster goes first)
    first = active.turn_manager.current_turn
    if first:
        if first.is_ai_controlled:
            await _handle_ai_turns(session_id, active, db)
        else:
            await event_bus.publish_to_session(
                session_id,
                EventType.TURN_START,
                {"combatant_id": first.combatant_id, "combatant_name": first.name},
                source="ws_game",
            )


async def _handle_end_turn(session_id: str, active: Any, db: AsyncSession) -> None:
    """Advance to the next combatant's turn; end combat if all NPCs are down."""
    if not active.turn_manager._order:
        return

    # Remove any newly-dead NPCs before advancing
    await _remove_dead_combatants(session_id, active)

    if active.turn_manager.all_npcs_removed():
        await _handle_combat_end(session_id, active, db)
        return

    next_entry = active.turn_manager.next_turn()
    active.turn_number += 1
    active.round_number = active.turn_manager.round_number
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    if next_entry and next_entry.is_ai_controlled:
        # Next combatant is AI: delegate to _handle_ai_turns (emits TURN_START + SESSION_STATE)
        await _handle_ai_turns(session_id, active, db)
        return

    if next_entry:
        await event_bus.publish_to_session(
            session_id,
            EventType.TURN_START,
            {"combatant_id": next_entry.combatant_id, "combatant_name": next_entry.name},
            source="ws_game",
        )

    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


async def _handle_ai_turns(session_id: str, active: Any, db: AsyncSession) -> None:
    """Trigger all consecutive AI-controlled turns, then emit TURN_START for the next human."""
    while True:
        current = active.turn_manager.current_turn
        if current is None or not current.is_ai_controlled:
            break

        # Announce this AI combatant's turn to the frontend
        await event_bus.publish_to_session(
            session_id,
            EventType.TURN_START,
            {"combatant_id": current.combatant_id, "combatant_name": current.name},
            source="ws_game",
        )

        agent = active.ai_players.get(current.combatant_id)
        if agent is not None:
            # AI companion: delegate to AIPlayerManager (handles its own next_turn() loop)
            from app.game.ai_player_manager import AIPlayerManager
            ai_manager = AIPlayerManager()
            await ai_manager.process_ai_turns(session_id, active, action_resolver)
            # process_ai_turns already stopped at a non-AI turn — fall through to broadcast
            break

        # Enemy monster: GM narrates the monster's action directly
        context = AgentContext(
            session_id=session_id,
            game_phase=active.phase.value.upper(),
            game_state=active.state_data,
            player_action=f"[Tour du monstre] {current.name} agit.",
        )
        try:
            gm_response = await action_resolver._gm.think(context)
            narration_text = gm_response.content
            for gm_action in gm_response.actions:
                merged_params: dict[str, Any] = dict(gm_action.params)
                if gm_action.target and "target" not in merged_params:
                    merged_params["target"] = gm_action.target
                await action_resolver._apply_gm_action(
                    session_id, gm_action.type, merged_params, active
                )
        except Exception as exc:
            logger.error("_handle_ai_turns: GM agent failed for '%s': %s", current.name, exc)
            narration_text = f"{current.name} se prépare à attaquer…"

        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {"text": narration_text, "speaker": current.name},
            source="ws_game",
        )

        # Check for newly dead combatants after monster action
        await _remove_dead_combatants(session_id, active)
        if active.turn_manager.all_npcs_removed():
            await _handle_combat_end(session_id, active, db)
            return

        # Advance past the monster's turn
        active.turn_manager.next_turn()
        active.turn_number += 1
        active.round_number = active.turn_manager.round_number

    # Save state and announce the next (human) combatant
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    current = active.turn_manager.current_turn
    if current:
        await event_bus.publish_to_session(
            session_id,
            EventType.TURN_START,
            {"combatant_id": current.combatant_id, "combatant_name": current.name},
            source="ws_game",
        )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


async def _handle_take_rest(session_id: str, active: Any, db: AsyncSession) -> None:
    """Long rest: restore full HP for all characters, then return to exploration."""
    characters_data: dict[str, Any] = active.state_data.get("characters", {})

    # Restore in-memory snapshots
    for cdata in characters_data.values():
        cdata["hp"] = cdata.get("hp_max", cdata.get("hp", 10))

    # Persist HP to DB
    result = await db.execute(
        select(Character).where(Character.session_id == session_id)
    )
    chars = result.scalars().all()
    for char in chars:
        char.hp_current = char.hp_max
    await db.commit()

    active.phase = SessionStatus.EXPLORATION
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.EXPLORATION.value},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {
            "text": (
                "Le groupe prend un long repos. Les blessures guérissent, "
                "les forces sont entièrement restaurées. L'aventure continue..."
            ),
            "speaker": "Maître du Jeu",
        },
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


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

    # ----------------------------------------------------------------
    # Route special action types directly (bypass GM agent)
    # ----------------------------------------------------------------
    if action.action_type == "end_turn":
        await _handle_end_turn(session_id, active, db)
        return

    if action.action_type == "start_combat":
        await _handle_start_combat(session_id, active, db)
        return

    if action.action_type == "take_rest":
        await _handle_take_rest(session_id, active, db)
        return

    # ----------------------------------------------------------------
    # Normal action: engine resolution → GM narration → events
    # ----------------------------------------------------------------
    await action_resolver.resolve(
        session_id=session_id,
        action_type=action.action_type,
        content=action.content,
        character_id=action.character_id,
        target_id=action.target_id,
        active=active,
        db=db,
        spell_id=action.spell_id,
        slot_level=action.slot_level,
    )

    # After resolution: check for dead NPC combatants
    if active.phase == SessionStatus.COMBAT:
        await _remove_dead_combatants(session_id, active)
        if active.turn_manager.all_npcs_removed():
            await _handle_combat_end(session_id, active, db)
            return
        # Auto-advance turn: one action = end of turn
        await _handle_end_turn(session_id, active, db)
    else:
        active.turn_number += 1
        active.mark_dirty()
        await event_bus.publish_to_session(
            session_id,
            EventType.TURN_END,
            {"turn_number": active.turn_number},
            source="ws_game",
        )


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws/game/{session_id}")
async def game_websocket(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Main WebSocket endpoint for real-time game communication."""
    await websocket.accept()

    # ------------------------------------------------------------------
    # 1. Open / load session
    # ------------------------------------------------------------------
    try:
        await session_manager.open_session(session_id, db)
    except KeyError:
        await websocket.send_json({
            "event_type": EventType.ERROR,
            "session_id": session_id,
            "payload": {"message": f"Session '{session_id}' not found."},
        })
        await websocket.close(code=4404)
        return

    # ------------------------------------------------------------------
    # 2. Register connection and subscribe to event bus
    # ------------------------------------------------------------------
    connection_manager.connect(session_id, websocket)
    queue = event_bus.subscribe(session_id)

    relay_task = asyncio.create_task(_relay_events(websocket, queue))

    # ------------------------------------------------------------------
    # 3. Send initial session state
    # ------------------------------------------------------------------
    await websocket.send_json({
        "event_type": EventType.SESSION_STATE,
        "session_id": session_id,
        "payload": _build_session_state_payload(session_id),
    })

    character_id: Optional[str] = None

    try:
        # ----------------------------------------------------------------
        # 4. Receive loop
        # ----------------------------------------------------------------
        while True:
            try:
                raw = await websocket.receive_json()
            except Exception:
                break

            msg_type = raw.get("type", "")

            # --- ping ---------------------------------------------------
            if msg_type == "ping":
                await websocket.send_json({"event_type": "pong"})
                continue

            # --- join ---------------------------------------------------
            if msg_type == "join":
                try:
                    join = JoinMessage(**raw)
                except ValidationError as exc:
                    await websocket.send_json({
                        "event_type": EventType.ERROR,
                        "session_id": session_id,
                        "payload": {"message": str(exc)},
                    })
                    continue

                character_id = join.character_id
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
                continue

            # --- action -------------------------------------------------
            if msg_type == "action":
                try:
                    action = PlayerActionMessage(**raw)
                except ValidationError as exc:
                    await websocket.send_json({
                        "event_type": EventType.ERROR,
                        "session_id": session_id,
                        "payload": {"message": str(exc)},
                    })
                    continue

                await _dispatch_action(session_id, action, db)
                continue

            # --- unknown type -------------------------------------------
            await websocket.send_json({
                "event_type": EventType.ERROR,
                "session_id": session_id,
                "payload": {"message": f"Unknown message type: '{msg_type}'."},
            })

    except WebSocketDisconnect:
        pass
    finally:
        # ----------------------------------------------------------------
        # 5. Cleanup
        # ----------------------------------------------------------------
        relay_task.cancel()
        await asyncio.gather(relay_task, return_exceptions=True)

        event_bus.unsubscribe(session_id, queue)
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
                await session_manager.close_session(session_id, db)
            except Exception as exc:
                logger.warning(
                    "Error closing session %s on last disconnect: %s", session_id, exc
                )

        logger.info("WS closed: session=%s character=%s", session_id, character_id)
