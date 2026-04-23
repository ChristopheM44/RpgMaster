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

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import AgentContext
from app.db.database import get_db
from app.engine.combat import roll_attack, roll_damage
from app.engine.tactical_grid import initialize_positions, validate_move, GridPosition
from app.game.action_resolver import ActionResolver
from app.game.event_bus import EventType, GameEvent, event_bus
from app.game.session_manager import SessionManager
from app.game.turn_manager import CombatantInfo
from app.models.character import Character
from app.models.session import SessionStatus
from app.services.encounter_service import encounter_service
from app.services.message_service import persist_narration

logger = logging.getLogger(__name__)

router = APIRouter()

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
    action_type: str  # free_text|attack|cast_spell|move|end_turn|start_combat|take_rest|equip|use_item|drop_item
    content: Optional[str] = None
    target_id: Optional[str] = None
    character_id: Optional[str] = None
    spell_id: Optional[str] = None    # cast_spell only
    slot_level: Optional[int] = None  # cast_spell only
    item_id: Optional[str] = None     # equip/use_item/drop_item only


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


_ARMOR_CATS = {"light", "medium", "heavy"}


def _compute_ac_from_equipment(equipment: list, dex_mod: int) -> int:
    """Calcule l'AC à partir de l'équipement équipé (armure + bouclier).

    Utilise les champs SRD : base_ac, dex_cap (0=lourd, None=libre, int=moyen).
    """
    armor = next(
        (it for it in equipment if it.get("equipped") and it.get("category") in _ARMOR_CATS),
        None,
    )
    shield = next(
        (it for it in equipment if it.get("equipped") and it.get("category") == "shield"),
        None,
    )
    shield_bonus = 2 if shield else 0

    if armor and isinstance(armor.get("base_ac"), int):
        dex_cap = armor.get("dex_cap")  # None = uncapped, 0 = heavy, int = medium
        dex_applied = dex_mod if dex_cap is None else min(dex_mod, int(dex_cap))
        return armor["base_ac"] + dex_applied + shield_bonus

    return 10 + dex_mod + shield_bonus


async def _auto_death_save(
    session_id: str,
    combatant_id: str,
    name: str,
    active: Any,
) -> None:
    """Auto-roule un jet de sauvegarde contre la mort pour un compagnon IA à 0 PV."""
    from app.engine.combat import roll_death_save  # noqa: PLC0415

    result = roll_death_save()
    combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
    cdata = combatants.get(combatant_id, {})
    ds: dict[str, Any] = cdata.setdefault("death_saves", {"successes": 0, "failures": 0, "stable": False})

    if result.critical_success:
        cdata["hp"] = 1
        ds["stable"] = True
        conds = list(cdata.get("conditions", []))
        if "inconscient" in conds:
            conds.remove("inconscient")
            cdata["conditions"] = conds
        active.mark_dirty()
        await event_bus.publish_to_session(
            session_id,
            EventType.HP_CHANGED,
            {"combatant_id": combatant_id, "hp": 1, "delta": 1},
            source="ws_game",
        )
        narr = f"{name} réussit son jet de sauvegarde avec un 20 naturel et reprend conscience avec 1 PV !"
    elif result.critical_failure:
        ds["failures"] = min(3, ds.get("failures", 0) + 2)
        active.mark_dirty()
        narr = f"{name} rate son jet de sauvegarde avec un 1 naturel — 2 échecs !"
    elif result.success:
        ds["successes"] = min(3, ds.get("successes", 0) + 1)
        if ds["successes"] >= 3:
            ds["stable"] = True
        active.mark_dirty()
        narr = f"{name} réussit son jet de sauvegarde contre la mort ({result.d20_roll}) [{ds['successes']}/3 succès]."
    else:
        ds["failures"] = min(3, ds.get("failures", 0) + 1)
        active.mark_dirty()
        narr = f"{name} rate son jet de sauvegarde contre la mort ({result.d20_roll}) [{ds['failures']}/3 échecs]."

    if ds.get("failures", 0) >= 3 and not ds.get("stable"):
        cdata["dead"] = True
        active.mark_dirty()
        narr = f"{name} est mort(e) — 3 échecs aux jets de sauvegarde."

    await event_bus.publish_to_session(
        session_id,
        EventType.ROLL_RESULT,
        {
            "dice_notation": "1d20",
            "rolls": [result.d20_roll],
            "total": result.d20_roll,
            "modifier": 0,
            "label": f"Jet de sauvegarde — {name}",
            "success": result.success,
        },
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": narr, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


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
    victory_text = "Victoire ! Tous les ennemis ont été vaincus. Le calme revient."
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": victory_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, victory_text, "Maître du Jeu", db)
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


# ---------------------------------------------------------------------------
# Special action handlers
# ---------------------------------------------------------------------------


async def _handle_start_combat(
    session_id: str,
    active: Any,
    db: AsyncSession,
    encounter_id: Optional[str] = None,
) -> None:
    """Spawn an encounter, roll initiative, and start combat.

    If encounter_id is provided, load that pre-built encounter.
    Otherwise generate a dynamic encounter adapted to the party's levels.
    """
    # Garde d'idempotence : un combat déjà en cours ne doit jamais être
    # "re-démarré" (double-trigger possible si flag consommé deux fois ou
    # si le joueur clique sur le bouton pendant qu'une transition auto arrive).
    if active.phase == SessionStatus.COMBAT:
        logger.warning(
            "_handle_start_combat: combat déjà en cours pour session=%s — ignoré.",
            session_id,
        )
        return

    # Resolve party levels from characters in state_data
    characters_data: dict[str, Any] = active.state_data.get("characters", {})
    party_levels = [int(c.get("level", 1)) for c in characters_data.values()]
    if not party_levels:
        party_levels = [1]

    # Build (or generate) the encounter
    intro_text: Optional[str] = None
    built = None

    # 1. Priorité : encounter déclaré par le GM via encounter_setup
    pending = active.state_data.pop("pending_encounter", None)
    if pending:
        monster_ids = pending.get("monster_ids", [])
        intro_text = pending.get("context") or None
        if monster_ids:
            candidate = encounter_service.build_from_monster_ids(monster_ids)
            if candidate.entries:
                built = candidate
            else:
                logger.warning(
                    "_handle_start_combat: aucun monster_id valide dans pending_encounter"
                    " %s, fallback.",
                    monster_ids,
                )

    # 2. Fallback : preset ou génération dynamique
    if built is None:
        if encounter_id:
            built = encounter_service.build_from_preset(encounter_id)
            preset = encounter_service.get_preset(encounter_id)
            intro_text = preset.get("intro_text") if preset else None
            if built is None:
                built = encounter_service.generate(party_levels)
        else:
            preset = encounter_service.pick_preset_for_party(party_levels)
            if preset:
                intro_text = preset.get("intro_text")
                built = encounter_service.build_from_preset(preset["id"])
            else:
                built = encounter_service.generate(party_levels)

    npc_combatants = encounter_service.expand(built)

    # Build player combatant maps
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
        char_equipment = cdata.get("equipment", [])
        combatants_info[char_id] = {
            "name": cdata["name"],
            "hp": int(cdata.get("hp", 10)),
            "hp_max": int(cdata.get("hp_max", 10)),
            "is_player": True,
            "is_ai": bool(cdata.get("is_ai", False)),
            "ac": _compute_ac_from_equipment(char_equipment, dex_mod),
            "attack_bonus": 3,
            "damage_notation": "1d6+2",
        }

    # Add NPC combatants from the built encounter
    npc_names: list[str] = []
    for npc in npc_combatants:
        cid = npc["combatant_id"]
        encounter_service._ensure_loaded()
        monster_id_base = "_".join(cid.rsplit("_", 1)[:-1]) if "_" in cid else cid
        monster_data = encounter_service._monsters_by_id.get(monster_id_base, {})
        dex = int(monster_data.get("ability_scores", {}).get("dexterity", 10))
        combatants_list.append(
            CombatantInfo(
                combatant_id=cid,
                name=npc["name"],
                dex_score=dex,
                is_player=False,
                is_ai_controlled=True,
            )
        )
        combatants_info[cid] = {
            "name": npc["name"],
            "hp": npc["hp"],
            "hp_max": npc["hp_max"],
            "is_player": False,
            "is_ai": True,
            "ac": npc["ac"],
            "attack_bonus": npc["attack_bonus"],
            "damage_notation": npc["damage_notation"],
        }
        npc_names.append(npc["name"])

    # Enregistrer les PlayerAgent pour les compagnons IA (personnages avec is_ai=True)
    # Si non enregistrés, ils tomberaient dans le chemin "monstre ennemi" de _handle_ai_turns.
    from app.agents.player_agent import PlayerAgent, PlayerPersonality
    for char_id, cdata in characters_data.items():
        if cdata.get("is_ai", False) and char_id not in active.ai_players:
            personality_traits = cdata.get("personality", ["brave"])
            if isinstance(personality_traits, str):
                personality_traits = [personality_traits]
            active.ai_players[char_id] = PlayerAgent(
                character_id=char_id,
                character_name=cdata["name"],
                personality=PlayerPersonality(traits=personality_traits),
            )
            logger.info(
                "_handle_start_combat: PlayerAgent enregistré pour compagnon IA '%s' (%s).",
                cdata["name"],
                char_id,
            )

    # Roll initiative and set up TurnManager
    turn_entries = active.turn_manager.setup_combat(combatants_list)
    active.state_data["combatants"] = combatants_info

    # Initialize tactical grid positions
    player_ids = [cid for cid, c in combatants_info.items() if c["is_player"]]
    npc_ids = [cid for cid, c in combatants_info.items() if not c["is_player"]]
    grid_cols, grid_rows = 10, 8
    grid_positions = initialize_positions(player_ids, npc_ids, grid_cols, grid_rows)
    active.state_data["grid_positions"] = {
        cid: pos.to_dict() for cid, pos in grid_positions.items()
    }
    active.state_data["grid_config"] = {
        "cols": grid_cols, "rows": grid_rows, "cell_size_m": 1.5
    }

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
            "position": grid_positions.get(entry.combatant_id, GridPosition(0, 0)).to_dict(),
        }
        for i, entry in enumerate(turn_entries)
    ]
    await event_bus.publish_to_session(
        session_id,
        "combat_start",
        {
            "combatants": combat_combatants,
            "grid_config": {"cols": grid_cols, "rows": grid_rows, "cell_size_m": 1.5},
        },
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
    if not intro_text:
        enemy_list = ", ".join(npc_names) if npc_names else "des ennemis"
        verb = "surgissent" if len(npc_names) > 1 else "surgit"
        intro_text = (
            f"{enemy_list} {verb} devant vous ! "
            "L'initiative est lancée — le combat commence !"
        )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": intro_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, intro_text, "Maître du Jeu", db)

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

        # Si ce combattant IA est un joueur à 0 PV → jet de sauvegarde automatique
        _cdata = active.state_data.get("combatants", {}).get(current.combatant_id, {})
        if _cdata.get("is_player") and int(_cdata.get("hp", 1)) == 0:
            _ds = _cdata.get("death_saves", {})
            if not _ds.get("stable") and not _cdata.get("dead"):
                await _auto_death_save(session_id, current.combatant_id, current.name, active)
            active.turn_manager.next_turn()
            active.turn_number += 1
            active.round_number = active.turn_manager.round_number
            active.mark_dirty()
            continue

        agent = active.ai_players.get(current.combatant_id)
        if agent is not None:
            # AI companion: delegate to AIPlayerManager (handles its own next_turn() loop)
            from app.game.ai_player_manager import AIPlayerManager
            ai_manager = AIPlayerManager()
            await ai_manager.process_ai_turns(session_id, active, action_resolver)
            # process_ai_turns already stopped at a non-AI turn — fall through to broadcast
            break

        # Enemy monster: deterministic mechanical resolution first, then GM prose narration
        combatants_info: dict[str, Any] = active.state_data.get("combatants", {})

        # Pick target: first alive player
        target_id: Optional[str] = None
        target_name = "la cible"
        target_ac = 10
        for cid, cdata in combatants_info.items():
            if cdata.get("is_player", False) and int(cdata.get("hp", 0)) > 0:
                target_id = cid
                target_name = cdata.get("name", cid)
                target_ac = int(cdata.get("ac", 10))
                break

        monster_info = combatants_info.get(current.combatant_id, {})
        attack_bonus = int(monster_info.get("attack_bonus", 0))
        damage_notation = monster_info.get("damage_notation", "1d4")

        # Résolution déterministe (moteur de règles D&D SRD)
        damage_dealt = 0
        try:
            atk = roll_attack(attack_bonus, target_ac)
            if target_id is not None and atk.hit:
                dmg = roll_damage(damage_notation, critical=atk.critical)
                damage_dealt = dmg.total
                new_hp = max(0, int(combatants_info[target_id].get("hp", 0)) - damage_dealt)
                combatants_info[target_id]["hp"] = new_hp
                active.mark_dirty()
                await event_bus.publish_to_session(
                    session_id,
                    EventType.HP_CHANGED,
                    {"combatant_id": target_id, "hp": new_hp, "delta": -damage_dealt},
                    source="ws_game",
                )
                # Si un joueur tombe à 0 PV : init jets de sauvegarde contre la mort
                if new_hp == 0 and combatants_info[target_id].get("is_player", False):
                    cdata = combatants_info[target_id]
                    if "death_saves" not in cdata:
                        cdata["death_saves"] = {"successes": 0, "failures": 0, "stable": False}
                    conds = list(cdata.get("conditions", []))
                    if "inconscient" not in conds:
                        conds.append("inconscient")
                        cdata["conditions"] = conds
        except Exception as exc:
            logger.error("_handle_ai_turns: résolution mécanique échouée pour '%s': %s", current.name, exc)
            atk = roll_attack(0, 10)  # attaque neutre pour continuer

        # Émission de l'event structuré COMBAT_ACTION
        await event_bus.publish_to_session(
            session_id,
            EventType.COMBAT_ACTION,
            {
                "attacker_id": current.combatant_id,
                "attacker_name": current.name,
                "target_id": target_id,
                "target_name": target_name,
                "action_type": "attack",
                "action_name": "Attaque",
                "d20": atk.d20_roll,
                "attack_roll": atk.total,
                "attack_bonus": attack_bonus,
                "target_ac": target_ac,
                "hit": atk.hit,
                "critical": atk.critical,
                "damage": damage_dealt if atk.hit else None,
                "damage_notation": damage_notation,
            },
            source="ws_game",
        )

        # GM narre l'action en prose (mécaniques déjà résolues — ne pas réappliquer)
        roll_results = {
            "attacker": current.name,
            "target": target_name,
            "d20": atk.d20_roll,
            "attack_total": atk.total,
            "target_ac": target_ac,
            "hit": atk.hit,
            "critical": atk.critical,
            "damage": damage_dealt,
            "damage_notation": damage_notation,
        }
        try:
            gm_response = await action_resolver._gm.run_combat_turn(
                game_state=active.state_data,
                player_action=f"[Tour du monstre] {current.name} attaque {target_name}.",
                roll_results=roll_results,
            )
            narration_text = gm_response.narration
            # NE PAS exécuter gm_response.actions — les mécaniques sont déjà résolues
        except Exception as exc:
            logger.error("_handle_ai_turns: GM agent failed for '%s': %s", current.name, exc)
            if atk.hit:
                crit_str = " (CRITIQUE !)" if atk.critical else ""
                narration_text = (
                    f"{current.name} attaque {target_name}{crit_str}"
                    f" et inflige {damage_dealt} dégâts !"
                )
            else:
                narration_text = f"{current.name} attaque {target_name} mais rate !"

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


async def _handle_reset_combat(session_id: str, active: Any, db: AsyncSession) -> None:
    """Test utility: exit combat, restore full HP, return to exploration."""
    active.turn_manager.reset()
    active.phase = SessionStatus.EXPLORATION
    active.state_data.pop("combatants", None)

    # Restore HP in characters snapshot
    characters_data: dict[str, Any] = active.state_data.get("characters", {})
    for cdata in characters_data.values():
        cdata["hp"] = cdata.get("hp_max", cdata.get("hp", 10))

    # Persist to DB
    result = await db.execute(
        select(Character).where(Character.session_id == session_id)
    )
    chars = result.scalars().all()
    for char in chars:
        char.hp_current = char.hp_max
    await db.commit()

    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.EXPLORATION.value},
        source="ws_game",
    )
    reset_text = "[TEST] Combat annulé. Points de vie restaurés. Retour en exploration."
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": reset_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, reset_text, "Maître du Jeu", db)
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


async def _handle_equip_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Équipe ou retire un objet (toggle) pendant une session active."""
    item_id = action.item_id
    character_id = action.character_id
    if not item_id or not character_id:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": "item_id et character_id requis pour équiper un objet."},
            source="ws_game",
        )
        return

    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if not char:
        return

    equipment = list(char.equipment or [])
    idx = next((i for i, it in enumerate(equipment) if it.get("id") == item_id), -1)
    if idx == -1:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": f"Objet '{item_id}' introuvable dans l'inventaire."},
            source="ws_game",
        )
        return

    item = equipment[idx]
    new_equipped = not item.get("equipped", False)

    _armor_cats = {"light", "medium", "heavy"}
    if new_equipped and item.get("category", "") in _armor_cats:
        for i, eq in enumerate(equipment):
            if i != idx and eq.get("category", "") in _armor_cats:
                equipment[i] = {**eq, "equipped": False}

    equipment[idx] = {**item, "equipped": new_equipped}
    char.equipment = equipment
    await db.commit()

    # Sync in-memory snapshot
    chars_data = active.state_data.get("characters", {})
    if character_id in chars_data:
        chars_data[character_id]["equipment"] = equipment
    active.mark_dirty()

    item_name = item.get("name_fr") or item_id
    action_label = "équipe" if new_equipped else "retire"
    await event_bus.publish_to_session(
        session_id, EventType.EQUIPMENT_UPDATED,
        {"character_id": character_id, "equipment": equipment},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id, EventType.NARRATION,
        {"text": f"{char.name} {action_label} : {item_name}.", "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def _handle_use_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Utilise un objet consommable pendant une session (potion = soin)."""
    from app.engine.dice import roll as dice_roll

    item_id = action.item_id
    character_id = action.character_id
    if not item_id or not character_id:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": "item_id et character_id requis pour utiliser un objet."},
            source="ws_game",
        )
        return

    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if not char:
        return

    equipment = list(char.equipment or [])
    idx = next((i for i, it in enumerate(equipment) if it.get("id") == item_id), -1)
    if idx == -1:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": f"Objet '{item_id}' introuvable dans l'inventaire."},
            source="ws_game",
        )
        return

    item = equipment[idx]
    item_name = item.get("name_fr") or item_id
    hp_restored = 0

    item_id_lower = item_id.lower()
    name_fr_lower = (item.get("name_fr") or "").lower()
    if "potion" in item_id_lower or "potion" in name_fr_lower:
        heal_result = dice_roll("2d4+2")
        hp_restored = heal_result.total
        new_hp = min(char.hp_max, char.hp_current + hp_restored)
        char.hp_current = new_hp

        chars_data = active.state_data.get("characters", {})
        if character_id in chars_data:
            chars_data[character_id]["hp"] = new_hp
        combatants = active.state_data.get("combatants", {})
        if character_id in combatants:
            combatants[character_id]["hp"] = new_hp

        await event_bus.publish_to_session(
            session_id, EventType.HP_CHANGED,
            {"combatant_id": character_id, "delta": hp_restored, "hp": new_hp},
            source="ws_game",
        )

    qty = int(item.get("quantity", 1))
    if qty > 1:
        equipment[idx] = {**item, "quantity": qty - 1}
    else:
        equipment.pop(idx)

    char.equipment = equipment
    await db.commit()

    chars_data = active.state_data.get("characters", {})
    if character_id in chars_data:
        chars_data[character_id]["equipment"] = equipment
    active.mark_dirty()

    await event_bus.publish_to_session(
        session_id, EventType.EQUIPMENT_UPDATED,
        {"character_id": character_id, "equipment": equipment},
        source="ws_game",
    )

    if hp_restored > 0:
        narration = f"{char.name} boit {item_name} et récupère {hp_restored} point(s) de vie."
    else:
        narration = f"{char.name} utilise {item_name}."
    await event_bus.publish_to_session(
        session_id, EventType.NARRATION,
        {"text": narration, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def _handle_drop_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Retire définitivement un objet de l'inventaire."""
    item_id = action.item_id
    character_id = action.character_id
    if not item_id or not character_id:
        await event_bus.publish_to_session(
            session_id, EventType.ERROR,
            {"message": "item_id et character_id requis pour lâcher un objet."},
            source="ws_game",
        )
        return

    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if not char:
        return

    equipment = list(char.equipment or [])
    idx = next((i for i, it in enumerate(equipment) if it.get("id") == item_id), -1)
    if idx == -1:
        return

    item = equipment.pop(idx)
    item_name = item.get("name_fr") or item_id
    char.equipment = equipment
    await db.commit()

    chars_data = active.state_data.get("characters", {})
    if character_id in chars_data:
        chars_data[character_id]["equipment"] = equipment
    active.mark_dirty()

    await event_bus.publish_to_session(
        session_id, EventType.EQUIPMENT_UPDATED,
        {"character_id": character_id, "equipment": equipment},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id, EventType.NARRATION,
        {"text": f"{char.name} lâche {item_name}.", "speaker": "Maître du Jeu"},
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
    rest_text = (
        "Le groupe prend un long repos. Les blessures guérissent, "
        "les forces sont entièrement restaurées. L'aventure continue..."
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": rest_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, rest_text, "Maître du Jeu", db)
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


async def _handle_move(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Handle a movement action: validate, update position, broadcast."""
    if not action.content or "," not in action.content:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Format de déplacement invalide. Attendu: 'col,row'"},
            source="ws_game",
        )
        return

    try:
        parts = action.content.split(",")
        target_col = int(parts[0].strip())
        target_row = int(parts[1].strip())
    except (ValueError, IndexError):
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Coordonnées de déplacement invalides."},
            source="ws_game",
        )
        return

    mover_id = action.character_id
    if not mover_id:
        return

    grid_positions: dict[str, Any] = active.state_data.get("grid_positions", {})
    grid_config: dict[str, Any] = active.state_data.get("grid_config", {"cols": 10, "rows": 8})
    grid_cols = int(grid_config.get("cols", 10))
    grid_rows = int(grid_config.get("rows", 8))

    from_data = grid_positions.get(mover_id)
    if from_data is None:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Position de départ introuvable."},
            source="ws_game",
        )
        return

    from_pos = GridPosition.from_dict(from_data)
    to_pos = GridPosition(col=target_col, row=target_row)

    # Get mover's speed from characters data
    combatants_info: dict[str, Any] = active.state_data.get("combatants", {})
    mover_data = combatants_info.get(mover_id, {})
    speed_m = float(mover_data.get("speed_m", 9.0))

    # Occupied positions (excluding mover)
    occupied = [
        GridPosition.from_dict(v)
        for cid, v in grid_positions.items()
        if cid != mover_id
    ]

    valid, reason = validate_move(from_pos, to_pos, speed_m, grid_cols, grid_rows, occupied)
    if not valid:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"Déplacement invalide : {reason}"},
            source="ws_game",
        )
        return

    from app.engine.tactical_grid import distance_m as grid_distance_m
    dist = grid_distance_m(from_pos, to_pos)

    # Update position in state
    grid_positions[mover_id] = to_pos.to_dict()
    active.mark_dirty()

    await event_bus.publish_to_session(
        session_id,
        EventType.COMBATANT_MOVED,
        {
            "combatant_id": mover_id,
            "position": to_pos.to_dict(),
            "movement_used_m": dist,
        },
        source="ws_game",
    )


# ---------------------------------------------------------------------------
# Welcome narration (join en exploration)
# ---------------------------------------------------------------------------


async def _send_welcome_narration(session_id: str, active: Any, db: AsyncSession) -> None:
    """Demande au GMAgent de décrire la scène courante quand un joueur rejoint en exploration."""
    # Guard d'idempotence : atomique en asyncio (pas d'await avant cette ligne)
    if active.state_data.get("welcome_narration_sent"):
        return
    active.state_data["welcome_narration_sent"] = True

    try:
        gm_response = await action_resolver._gm.narrate(
            game_state=active.state_data,
            player_action=None,
        )
        welcome_text = gm_response.narration if gm_response else (
            "Bienvenue dans l'aventure ! Décrivez votre action pour commencer."
        )
    except Exception as exc:
        logger.warning("_send_welcome_narration: GMAgent failed: %s", exc)
        welcome_text = "Bienvenue dans l'aventure ! Décrivez votre action pour commencer."

    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": welcome_text, "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await persist_narration(session_id, welcome_text, "Maître du Jeu", db)


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
    # Guard : un joueur inconscient ne peut pas attaquer ni lancer de sort
    # ----------------------------------------------------------------
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

    # ----------------------------------------------------------------
    # Route special action types directly (bypass GM agent)
    # ----------------------------------------------------------------
    if action.action_type == "move":
        await _handle_move(session_id, action, active, db)
        return

    if action.action_type == "end_turn":
        await _handle_end_turn(session_id, active, db)
        return

    if action.action_type == "start_combat":
        # Optional: client may pass encounter_id in content to trigger a preset
        encounter_id: Optional[str] = action.content if action.content else None
        await _handle_start_combat(session_id, active, db, encounter_id=encounter_id)
        return

    if action.action_type == "take_rest":
        await _handle_take_rest(session_id, active, db)
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

    # Auto-déclenchement du combat demandé par le MJ via state_transition.
    # Le resolver a posé le drapeau ; on le consomme ici (accès à db +
    # possibilité d'appeler _handle_start_combat qui roule l'initiative).
    pending_transition = active.state_data.pop("pending_phase_transition", None)
    if pending_transition == "COMBAT" and active.phase != SessionStatus.COMBAT:
        await _handle_start_combat(session_id, active, db, encounter_id=None)
        return

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

                # Si la session est déjà en exploration, le MJ décrit la scène
                active_on_join = session_manager.get_session(session_id)
                if active_on_join and active_on_join.phase == SessionStatus.EXPLORATION:
                    asyncio.create_task(
                        _send_welcome_narration(session_id, active_on_join, db)
                    )
                elif active_on_join and active_on_join.phase == SessionStatus.COMBAT:
                    # Rejouer l'état de combat pour ce client qui se (re)connecte
                    combatants_info: dict[str, Any] = active_on_join.state_data.get("combatants", {})
                    grid_cfg: dict[str, Any] = active_on_join.state_data.get("grid_config", {"cols": 10, "rows": 8, "cell_size_m": 1.5})
                    grid_positions: dict[str, Any] = active_on_join.state_data.get("grid_positions", {})
                    turn_data = active_on_join.turn_manager.to_dict()
                    current_idx = turn_data.get("index", 0)
                    combat_combatants = [
                        {
                            "id": entry.get("combatant_id", ""),
                            "name": entry.get("name", ""),
                            "initiative": entry.get("initiative_total", 0),
                            "hp_current": combatants_info.get(entry.get("combatant_id", ""), {}).get("hp", 0),
                            "hp_max": combatants_info.get(entry.get("combatant_id", ""), {}).get("hp_max", 0),
                            "is_ai": entry.get("is_ai_controlled", False),
                            "conditions": [],
                            "is_active": (i == current_idx),
                            "position": grid_positions.get(entry.get("combatant_id", ""), {"col": 0, "row": 0}),
                        }
                        for i, entry in enumerate(turn_data.get("order", []))
                    ]
                    await websocket.send_json({
                        "event_type": "combat_start",
                        "session_id": session_id,
                        "payload": {
                            "combatants": combat_combatants,
                            "grid_config": grid_cfg,
                        },
                    })
                    current = active_on_join.turn_manager.current_turn
                    if current:
                        await websocket.send_json({
                            "event_type": EventType.TURN_START,
                            "session_id": session_id,
                            "payload": {"combatant_id": current.combatant_id, "combatant_name": current.name},
                        })
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

                try:
                    await _dispatch_action(session_id, action, db)
                except Exception as exc:
                    logger.error("Unhandled error in _dispatch_action: %s", exc, exc_info=True)
                    await event_bus.publish_to_session(
                        session_id,
                        EventType.ERROR,
                        {"message": "Une erreur interne s'est produite. Réessayez."},
                        source="ws_game",
                    )
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
