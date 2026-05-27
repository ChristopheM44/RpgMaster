"""Tactical combat resolution helpers.

This module keeps grid movement, reach checks, and opportunity attacks in one
place so narration can only describe state changes that the server applied.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.engine.combat import roll_attack, roll_damage
from app.engine.conditions import Condition, can_take_reactions
from app.engine.pathfinding import astar_path
from app.engine.tactical_grid import CELL_SIZE_M, GridPosition, distance_m
from app.game.constants import INACTIVE_STATUSES
from app.game.event_bus import EventType
from app.game.state_sync import sync_character_state


@dataclass
class OpportunityAttackResult:
    attacker_id: str
    attacker_name: str
    target_id: str
    target_name: str
    hit: bool
    critical: bool
    d20: int
    attack_total: int
    target_ac: int
    damage: int = 0
    damage_notation: str = ""


@dataclass
class TacticalMoveResult:
    valid: bool
    reason: str = ""
    path: list[GridPosition] = field(default_factory=list)
    final_position: Optional[GridPosition] = None
    movement_used_m: float = 0.0
    interrupted: bool = False
    opportunity_attacks: list[OpportunityAttackResult] = field(default_factory=list)


@dataclass
class TacticalAttackPreparation:
    target_id: Optional[str]
    allowed: bool
    reason: str = ""
    moved: Optional[TacticalMoveResult] = None


_NO_REACTION_ALIASES = {
    "incapacitated",
    "neutralise",
    "neutralis\u00e9",
    "paralyzed",
    "paralyse",
    "paralys\u00e9",
    "petrified",
    "petrifie",
    "petrifi\u00e9",
    "stunned",
    "etourdi",
    "\u00e9tourdi",
    "unconscious",
    "inconscient",
}


def grid_dimensions(state_data: dict[str, Any]) -> tuple[int, int]:
    grid_config = state_data.get("grid_config") or {"cols": 10, "rows": 8}
    return int(grid_config.get("cols", 10)), int(grid_config.get("rows", 8))


def grid_position_for(
    state_data: dict[str, Any],
    combatant_id: str,
) -> Optional[GridPosition]:
    raw = (state_data.get("grid_positions") or {}).get(combatant_id)
    if not isinstance(raw, dict) or "col" not in raw or "row" not in raw:
        return None
    return GridPosition.from_dict(raw)


def combatant_name(state_data: dict[str, Any], combatant_id: Optional[str]) -> str:
    if not combatant_id:
        return "cible"
    cdata = (state_data.get("combatants") or {}).get(combatant_id, {})
    if isinstance(cdata, dict):
        return str(cdata.get("name") or combatant_id)
    return combatant_id


def is_active_combatant(cdata: Any) -> bool:
    if not isinstance(cdata, dict):
        return False
    status = str(cdata.get("status", "active")).lower()
    if status in INACTIVE_STATUSES:
        return False
    try:
        return int(cdata.get("hp", 0)) > 0
    except (TypeError, ValueError):
        return False


def combatant_reach_m(cdata: dict[str, Any]) -> float:
    if cdata.get("reach_m") is not None:
        return float(cdata.get("reach_m") or CELL_SIZE_M)
    for action in cdata.get("actions") or []:
        if not isinstance(action, dict):
            continue
        if action.get("reach_m") is not None and action.get("attack_bonus") is not None:
            return float(action.get("reach_m") or CELL_SIZE_M)
    return CELL_SIZE_M


def combatant_attack_range_m(cdata: dict[str, Any]) -> float:
    if cdata.get("attack_range_m") is not None:
        return float(cdata.get("attack_range_m") or combatant_reach_m(cdata))
    for action in cdata.get("actions") or []:
        if not isinstance(action, dict) or action.get("attack_bonus") is None:
            continue
        action_type = str(action.get("type") or "").lower()
        if action_type in {"ranged_attack", "melee_or_ranged_attack"}:
            range_m = action.get("range_m")
            if isinstance(range_m, (int, float)):
                return float(range_m)
            if isinstance(range_m, list) and range_m:
                return float(range_m[0])
        if action.get("reach_m") is not None:
            return float(action.get("reach_m") or CELL_SIZE_M)
    return combatant_reach_m(cdata)


def combatant_speed_m(cdata: dict[str, Any]) -> float:
    return float(cdata.get("speed_m") or cdata.get("speed") or 9.0)


def has_reaction_available(entry: Any, cdata: dict[str, Any]) -> bool:
    if not getattr(entry.action_economy, "reaction", False):
        return False
    raw_conditions = cdata.get("conditions") or []
    lowered = {str(cond).strip().lower() for cond in raw_conditions}
    if lowered & _NO_REACTION_ALIASES:
        return False
    parsed: set[Condition] = set()
    for cond in lowered:
        try:
            parsed.add(Condition(cond))
        except ValueError:
            continue
    return can_take_reactions(parsed)


def occupied_positions(
    state_data: dict[str, Any],
    *,
    exclude: Optional[str] = None,
) -> list[GridPosition]:
    positions = state_data.get("grid_positions") or {}
    result: list[GridPosition] = []
    combatants = state_data.get("combatants") or {}
    for cid, raw in positions.items():
        if cid == exclude:
            continue
        if cid in combatants and not is_active_combatant(combatants.get(cid)):
            continue
        if isinstance(raw, dict) and "col" in raw and "row" in raw:
            result.append(GridPosition.from_dict(raw))
    return result


def obstacle_positions(state_data: dict[str, Any]) -> list[GridPosition]:
    decoration = state_data.get("grid_decoration") or {}
    obstacles = decoration.get("obstacles") if isinstance(decoration, dict) else []
    return [
        GridPosition.from_dict(pos)
        for pos in obstacles or []
        if isinstance(pos, dict) and "col" in pos and "row" in pos
    ]


def difficult_positions(state_data: dict[str, Any]) -> list[GridPosition]:
    decoration = state_data.get("grid_decoration") or {}
    difficult = decoration.get("difficult") if isinstance(decoration, dict) else []
    return [
        GridPosition.from_dict(pos)
        for pos in difficult or []
        if isinstance(pos, dict) and "col" in pos and "row" in pos
    ]


def path_cost_m(
    path: list[GridPosition],
    difficult: Optional[list[GridPosition]] = None,
) -> float:
    difficult_set = {(pos.col, pos.row) for pos in difficult or []}
    cost_cells = 0.0
    for step in path[1:]:
        cost_cells += 2.0 if (step.col, step.row) in difficult_set else 1.0
    return cost_cells * CELL_SIZE_M


def is_within_reach(
    state_data: dict[str, Any],
    attacker_id: str,
    target_id: str,
    *,
    reach_m: Optional[float] = None,
) -> bool:
    attacker_pos = grid_position_for(state_data, attacker_id)
    target_pos = grid_position_for(state_data, target_id)
    if attacker_pos is None or target_pos is None:
        return True
    attacker = (state_data.get("combatants") or {}).get(attacker_id, {})
    effective_reach = float(reach_m if reach_m is not None else combatant_reach_m(attacker))
    return distance_m(attacker_pos, target_pos) <= effective_reach


def choose_attack_target(
    state_data: dict[str, Any],
    actor_id: Optional[str],
    *,
    actor_is_player: bool,
) -> Optional[str]:
    combatants = state_data.get("combatants") or {}
    if not isinstance(combatants, dict):
        return None

    candidates: list[tuple[float, int, str]] = []
    actor_pos = grid_position_for(state_data, actor_id or "")
    for cid, cdata in combatants.items():
        if cid == actor_id or not isinstance(cdata, dict):
            continue
        if bool(cdata.get("is_player", False)) == actor_is_player:
            continue
        if not is_active_combatant(cdata):
            continue
        try:
            hp = int(cdata.get("hp", 0))
        except (TypeError, ValueError):
            hp = 0
        target_pos = grid_position_for(state_data, cid)
        dist = distance_m(actor_pos, target_pos) if actor_pos and target_pos else 0.0
        candidates.append((dist, hp, str(cid)))

    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[0], item[1], item[2]))
    return candidates[0][2]


def approach_path_to_target(
    state_data: dict[str, Any],
    mover_id: str,
    target_id: str,
    movement_m: float,
    reach_m: float,
) -> list[GridPosition]:
    start = grid_position_for(state_data, mover_id)
    target = grid_position_for(state_data, target_id)
    if start is None or target is None:
        return []

    grid_cols, grid_rows = grid_dimensions(state_data)
    occupied = occupied_positions(state_data, exclude=mover_id)
    obstacles = obstacle_positions(state_data)
    difficult = difficult_positions(state_data)
    blocked = occupied + obstacles
    blocked_set = {(pos.col, pos.row) for pos in blocked}

    candidates: list[tuple[float, float, list[GridPosition]]] = []
    for row in range(grid_rows):
        for col in range(grid_cols):
            candidate = GridPosition(col, row)
            if candidate == start:
                continue
            if (col, row) in blocked_set:
                continue
            if distance_m(candidate, target) > reach_m:
                continue
            path = astar_path(start, candidate, grid_cols, grid_rows, blocked, difficult)
            if not path:
                continue
            cost = path_cost_m(path, difficult)
            if cost <= movement_m:
                candidates.append((cost, distance_m(candidate, target), path))

    if not candidates:
        return []
    candidates.sort(key=lambda item: (item[0], item[1], len(item[2])))
    return candidates[0][2]


def resolve_ai_move_destination(
    state_data: dict[str, Any],
    actor_id: str,
    intent: str,
    target_id: str,
    movement_m: float,
) -> Optional[GridPosition]:
    """Resolve a semantic AI movement intent into a reachable grid cell."""
    normalized = str(intent or "").strip().lower()
    if normalized == "approach":
        path = approach_path_to_target(
            state_data,
            actor_id,
            target_id,
            movement_m,
            CELL_SIZE_M,
        )
        return (
            path[-1]
            if path
            else _closest_reachable_cell_to_target(state_data, actor_id, target_id, movement_m)
        )
    if normalized == "retreat":
        return _retreat_destination(state_data, actor_id, target_id, movement_m)
    if normalized == "flank":
        return _flank_destination(state_data, actor_id, target_id, movement_m)
    return None


async def apply_tactical_move(
    *,
    session_id: str,
    active: Any,
    mover_id: str,
    destination: GridPosition,
    event_bus: Any,
    movement_m: Optional[float] = None,
    ignore_opportunity_attacks: bool = False,
    forced_movement: bool = False,
    teleport: bool = False,
    source: str = "tactical_combat",
) -> TacticalMoveResult:
    state_data = active.state_data
    grid_cols, grid_rows = grid_dimensions(state_data)
    if destination.col < 0 or destination.col >= grid_cols:
        return TacticalMoveResult(
            False,
            f"Colonne {destination.col} hors grille (0-{grid_cols - 1})",
        )
    if destination.row < 0 or destination.row >= grid_rows:
        return TacticalMoveResult(
            False,
            f"Rangee {destination.row} hors grille (0-{grid_rows - 1})",
        )

    start = grid_position_for(state_data, mover_id)
    if start is None:
        return TacticalMoveResult(False, "Position de depart introuvable.")
    if start == destination:
        return TacticalMoveResult(True, path=[start], final_position=start)

    combatants = state_data.get("combatants") or {}
    mover = combatants.get(mover_id, {})
    if not isinstance(mover, dict):
        mover = {}

    occupied = occupied_positions(state_data, exclude=mover_id)
    obstacles = obstacle_positions(state_data)
    difficult = difficult_positions(state_data)
    blocked = occupied + obstacles
    if (destination.col, destination.row) in {(pos.col, pos.row) for pos in blocked}:
        return TacticalMoveResult(False, "Case occupee ou bloquee.")

    if teleport:
        path = [start, destination]
    else:
        path = astar_path(start, destination, grid_cols, grid_rows, blocked, difficult)
    if not path:
        return TacticalMoveResult(False, "Aucun chemin valide vers cette case.")

    limit = float(movement_m if movement_m is not None else combatant_speed_m(mover))
    total_cost = path_cost_m(path, difficult)
    if total_cost > limit:
        return TacticalMoveResult(
            False,
            f"Distance {total_cost} m depasse mouvement {limit} m",
        )

    should_skip_oa = ignore_opportunity_attacks or forced_movement or teleport
    current = active.turn_manager.current_turn
    if current is not None and current.combatant_id == mover_id:
        should_skip_oa = should_skip_oa or bool(
            getattr(current.action_economy, "has_disengaged", False)
        )

    travelled = [path[0]]
    opportunity_attacks: list[OpportunityAttackResult] = []
    interrupted = False
    final_position = path[-1]

    for index in range(1, len(path)):
        previous = path[index - 1]
        step = path[index]
        if not should_skip_oa:
            triggered = await _trigger_opportunity_attacks_for_step(
                session_id=session_id,
                active=active,
                mover_id=mover_id,
                from_pos=previous,
                to_pos=step,
                event_bus=event_bus,
                source=source,
            )
            opportunity_attacks.extend(triggered)
            if not is_active_combatant((state_data.get("combatants") or {}).get(mover_id)):
                interrupted = True
                final_position = previous
                break
        travelled.append(step)

    if not interrupted:
        final_position = path[-1]

    movement_used = path_cost_m(travelled, difficult)
    (state_data.setdefault("grid_positions", {}))[mover_id] = final_position.to_dict()
    active.mark_dirty()

    return TacticalMoveResult(
        valid=True,
        path=travelled,
        final_position=final_position,
        movement_used_m=movement_used,
        interrupted=interrupted,
        reason="interrupted_by_opportunity_attack" if interrupted else "",
        opportunity_attacks=opportunity_attacks,
    )


async def prepare_attack(
    *,
    session_id: str,
    active: Any,
    actor_id: Optional[str],
    target_id: Optional[str],
    actor_kind: str,
    event_bus: Any,
    source: str = "tactical_combat",
) -> TacticalAttackPreparation:
    if not actor_id:
        return TacticalAttackPreparation(target_id, False, "Attaquant introuvable.")

    state_data = active.state_data
    combatants = state_data.get("combatants") or {}
    actor = combatants.get(actor_id, {})
    if not isinstance(actor, dict):
        return TacticalAttackPreparation(target_id, False, "Attaquant introuvable.")

    effective_target = target_id
    if not effective_target:
        effective_target = choose_attack_target(
            state_data,
            actor_id,
            actor_is_player=bool(actor.get("is_player", actor_kind != "monster")),
        )
    if not effective_target:
        return TacticalAttackPreparation(None, False, "Aucune cible valide.")
    if not is_active_combatant(combatants.get(effective_target)):
        return TacticalAttackPreparation(
            effective_target,
            False,
            "Cible invalide ou neutralisee.",
        )

    if (
        grid_position_for(state_data, actor_id) is None
        or grid_position_for(state_data, effective_target) is None
    ):
        return TacticalAttackPreparation(effective_target, True)

    attack_range = combatant_attack_range_m(actor)
    if is_within_reach(state_data, actor_id, effective_target, reach_m=attack_range):
        return TacticalAttackPreparation(effective_target, True)

    if actor_kind not in {"monster", "companion"}:
        return TacticalAttackPreparation(
            effective_target,
            False,
            f"Cible hors de portee ({attack_range:g} m).",
        )

    current = active.turn_manager.current_turn
    economy = (
        current.action_economy if current is not None and current.combatant_id == actor_id else None
    )
    movement_left = float(economy.movement if economy is not None else combatant_speed_m(actor))
    path = approach_path_to_target(
        state_data,
        actor_id,
        effective_target,
        movement_left,
        attack_range,
    )
    if not path:
        return TacticalAttackPreparation(
            effective_target,
            False,
            "Aucun chemin ne permet d'atteindre une cible a portee.",
        )

    move_result = await apply_tactical_move(
        session_id=session_id,
        active=active,
        mover_id=actor_id,
        destination=path[-1],
        event_bus=event_bus,
        movement_m=movement_left,
        source=source,
    )
    if not move_result.valid:
        return TacticalAttackPreparation(effective_target, False, move_result.reason, move_result)
    if economy is not None:
        economy.spend_movement(move_result.movement_used_m)
    if move_result.interrupted:
        return TacticalAttackPreparation(
            effective_target,
            False,
            "Deplacement interrompu par une attaque d'opportunite.",
            move_result,
        )
    if not is_within_reach(state_data, actor_id, effective_target, reach_m=attack_range):
        return TacticalAttackPreparation(
            effective_target,
            False,
            "La cible reste hors de portee apres le deplacement.",
            move_result,
        )
    return TacticalAttackPreparation(effective_target, True, moved=move_result)


async def prepare_cast_spell(
    *,
    session_id: str,
    active: Any,
    actor_id: Optional[str],
    target_id: Optional[str],
    spell_id: str,
    actor_kind: str,
    event_bus: Any,
    source: str = "tactical_combat",
) -> TacticalAttackPreparation:
    if not actor_id:
        return TacticalAttackPreparation(target_id, False, "Lanceur introuvable.")

    from app.game.action_mechanics import _load_spells  # noqa: PLC0415

    spell = _load_spells().get(spell_id)
    if not spell:
        return TacticalAttackPreparation(
            target_id,
            False,
            f"Sort inconnu : '{spell_id}'.",
        )

    effective_range = _spell_effective_range_m(spell, target_id)
    if target_id is None or effective_range <= 0:
        return TacticalAttackPreparation(target_id, True)

    state_data = active.state_data
    combatants = state_data.get("combatants") or {}
    actor = combatants.get(actor_id, {})
    if not isinstance(actor, dict):
        return TacticalAttackPreparation(target_id, False, "Lanceur introuvable.")
    if target_id not in combatants:
        return TacticalAttackPreparation(target_id, False, "Cible invalide.")

    if (
        grid_position_for(state_data, actor_id) is None
        or grid_position_for(state_data, target_id) is None
    ):
        return TacticalAttackPreparation(target_id, True)

    if is_within_reach(state_data, actor_id, target_id, reach_m=effective_range):
        return TacticalAttackPreparation(target_id, True)

    if actor_kind not in {"monster", "companion"}:
        return TacticalAttackPreparation(
            target_id,
            False,
            f"Sort hors de portee ({effective_range:g} m).",
        )

    current = active.turn_manager.current_turn
    economy = (
        current.action_economy if current is not None and current.combatant_id == actor_id else None
    )
    movement_left = float(economy.movement if economy is not None else combatant_speed_m(actor))
    path = approach_path_to_target(
        state_data,
        actor_id,
        target_id,
        movement_left,
        effective_range,
    )
    if not path:
        return TacticalAttackPreparation(
            target_id,
            False,
            "Aucun chemin ne permet d'atteindre une cible a portee du sort.",
        )

    move_result = await apply_tactical_move(
        session_id=session_id,
        active=active,
        mover_id=actor_id,
        destination=path[-1],
        event_bus=event_bus,
        movement_m=movement_left,
        source=source,
    )
    if not move_result.valid:
        return TacticalAttackPreparation(target_id, False, move_result.reason, move_result)
    if economy is not None:
        economy.spend_movement(move_result.movement_used_m)
    if move_result.interrupted:
        return TacticalAttackPreparation(
            target_id,
            False,
            "Deplacement interrompu par une attaque d'opportunite.",
            move_result,
        )
    if not is_within_reach(state_data, actor_id, target_id, reach_m=effective_range):
        return TacticalAttackPreparation(
            target_id,
            False,
            "La cible reste hors de portee du sort apres le deplacement.",
            move_result,
        )
    return TacticalAttackPreparation(target_id, True, moved=move_result)


def _spell_effective_range_m(spell: dict[str, Any], target_id: Optional[str]) -> float:
    range_m = _float_value(spell.get("range_m"), 0.0)
    attack_type = str(spell.get("attack_type") or "").lower()
    if range_m == 0 and target_id is None:
        return 0.0
    if range_m == 0 or attack_type == "melee_spell" and range_m == 0:
        return CELL_SIZE_M
    return range_m


def _closest_reachable_cell_to_target(
    state_data: dict[str, Any],
    actor_id: str,
    target_id: str,
    movement_m: float,
) -> Optional[GridPosition]:
    target = grid_position_for(state_data, target_id)
    if target is None:
        return None
    candidates = _reachable_paths(state_data, actor_id, movement_m)
    if not candidates:
        return None
    candidates.sort(key=lambda item: (distance_m(item[0], target), item[1]))
    return candidates[0][0]


def _retreat_destination(
    state_data: dict[str, Any],
    actor_id: str,
    target_id: str,
    movement_m: float,
) -> Optional[GridPosition]:
    actor = (state_data.get("combatants") or {}).get(actor_id, {})
    actor_is_player = bool(actor.get("is_player", True)) if isinstance(actor, dict) else True
    combatants = state_data.get("combatants") or {}
    enemy_positions: list[GridPosition] = []
    for cid, cdata in combatants.items():
        if cid == actor_id or not isinstance(cdata, dict) or not is_active_combatant(cdata):
            continue
        if bool(cdata.get("is_player", True)) == actor_is_player:
            continue
        pos = grid_position_for(state_data, str(cid))
        if pos is not None:
            enemy_positions.append(pos)

    reference = grid_position_for(state_data, target_id)
    candidates = _reachable_paths(state_data, actor_id, movement_m)
    if not candidates:
        return None

    def score(item: tuple[GridPosition, float, list[GridPosition]]) -> tuple[float, float, float]:
        pos, cost, _path = item
        if enemy_positions:
            nearest_enemy = min(distance_m(pos, enemy) for enemy in enemy_positions)
            total_enemy_distance = sum(distance_m(pos, enemy) for enemy in enemy_positions)
        else:
            nearest_enemy = distance_m(pos, reference) if reference is not None else 0.0
            total_enemy_distance = nearest_enemy
        reference_distance = distance_m(pos, reference) if reference is not None else 0.0
        return (nearest_enemy, total_enemy_distance + reference_distance, -cost)

    candidates.sort(key=score, reverse=True)
    return candidates[0][0]


def _flank_destination(
    state_data: dict[str, Any],
    actor_id: str,
    target_id: str,
    movement_m: float,
) -> Optional[GridPosition]:
    target = grid_position_for(state_data, target_id)
    if target is None:
        return None
    candidates = [
        item
        for item in _reachable_paths(state_data, actor_id, movement_m)
        if 0 < distance_m(item[0], target) <= CELL_SIZE_M
    ]
    if not candidates:
        return None
    candidates.sort(key=lambda item: (item[1], item[0].row, item[0].col))
    return candidates[0][0]


def _reachable_paths(
    state_data: dict[str, Any],
    actor_id: str,
    movement_m: float,
) -> list[tuple[GridPosition, float, list[GridPosition]]]:
    start = grid_position_for(state_data, actor_id)
    if start is None:
        return []

    grid_cols, grid_rows = grid_dimensions(state_data)
    blocked = occupied_positions(state_data, exclude=actor_id) + obstacle_positions(state_data)
    difficult = difficult_positions(state_data)
    blocked_set = {(pos.col, pos.row) for pos in blocked}
    candidates: list[tuple[GridPosition, float, list[GridPosition]]] = []

    for row in range(grid_rows):
        for col in range(grid_cols):
            candidate = GridPosition(col, row)
            if candidate == start or (col, row) in blocked_set:
                continue
            path = astar_path(start, candidate, grid_cols, grid_rows, blocked, difficult)
            if not path:
                continue
            cost = path_cost_m(path, difficult)
            if cost <= movement_m:
                candidates.append((candidate, cost, path))
    return candidates


def _float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def calculate_reachable_cells(
    active: Any,
    combatant_id: Optional[str],
) -> Optional[dict[str, Any]]:
    if not combatant_id:
        return None
    state_data = active.state_data
    start = grid_position_for(state_data, combatant_id)
    if start is None:
        return None
    combatants = state_data.get("combatants") or {}
    cdata = combatants.get(combatant_id, {})
    if not isinstance(cdata, dict) or not is_active_combatant(cdata):
        return None

    current = active.turn_manager.current_turn
    economy = (
        current.action_economy
        if current is not None and current.combatant_id == combatant_id
        else None
    )
    movement_m = float(economy.movement if economy is not None else combatant_speed_m(cdata))
    dash_m = movement_m + float(
        economy.movement_max if economy is not None else combatant_speed_m(cdata)
    )
    grid_cols, grid_rows = grid_dimensions(state_data)
    blocked = occupied_positions(state_data, exclude=combatant_id) + obstacle_positions(state_data)
    difficult = difficult_positions(state_data)

    free: list[dict[str, int]] = []
    with_dash: list[dict[str, int]] = []
    paths: dict[str, list[dict[str, int]]] = {}
    for row in range(grid_rows):
        for col in range(grid_cols):
            target = GridPosition(col, row)
            if target == start:
                continue
            path = astar_path(start, target, grid_cols, grid_rows, blocked, difficult)
            if not path:
                continue
            cost = path_cost_m(path, difficult)
            key = f"{col},{row}"
            if cost <= movement_m:
                free.append(target.to_dict())
                paths[key] = [step.to_dict() for step in path]
            elif cost <= dash_m:
                with_dash.append(target.to_dict())
                paths[key] = [step.to_dict() for step in path]
    return {
        "free": free,
        "with_dash": with_dash,
        "paths": paths,
    }


async def _trigger_opportunity_attacks_for_step(
    *,
    session_id: str,
    active: Any,
    mover_id: str,
    from_pos: GridPosition,
    to_pos: GridPosition,
    event_bus: Any,
    source: str,
) -> list[OpportunityAttackResult]:
    state_data = active.state_data
    combatants = state_data.get("combatants") or {}
    grid_positions = state_data.get("grid_positions") or {}
    mover = combatants.get(mover_id, {})
    if not isinstance(mover, dict):
        return []
    mover_is_player = bool(mover.get("is_player", True))
    results: list[OpportunityAttackResult] = []

    for entry in active.turn_manager._order:
        attacker_id = entry.combatant_id
        if attacker_id == mover_id:
            continue
        attacker = combatants.get(attacker_id, {})
        if not isinstance(attacker, dict) or not is_active_combatant(attacker):
            continue
        if bool(attacker.get("is_player", True)) == mover_is_player:
            continue
        if not has_reaction_available(entry, attacker):
            continue
        attacker_pos_data = grid_positions.get(attacker_id)
        if not isinstance(attacker_pos_data, dict):
            continue
        attacker_pos = GridPosition.from_dict(attacker_pos_data)
        reach = combatant_reach_m(attacker)
        if distance_m(attacker_pos, from_pos) > reach:
            continue
        if distance_m(attacker_pos, to_pos) <= reach:
            continue

        entry.action_economy.use_reaction()
        attack = roll_attack(
            int(attacker.get("attack_bonus", 3) or 3),
            int(mover.get("ac", 10) or 10),
        )
        damage_notation = str(attacker.get("damage_notation") or "1d6+1")
        damage_amount = 0
        if attack.hit:
            damage = roll_damage(damage_notation, critical=attack.critical)
            damage_amount = int(damage.total)
            old_hp = int(mover.get("hp", 0))
            new_hp = max(0, old_hp - damage_amount)
            mover["hp"] = new_hp
            sync_character_state(active, mover_id, hp=new_hp)
            await event_bus.publish_to_session(
                session_id,
                EventType.HP_CHANGED,
                {"combatant_id": mover_id, "delta": -damage_amount, "hp": new_hp},
                source=source,
            )

        payload = {
            "attacker_id": attacker_id,
            "attacker_name": combatant_name(state_data, attacker_id),
            "target_id": mover_id,
            "target_name": combatant_name(state_data, mover_id),
            "hit": bool(attack.hit),
            "critical": bool(attack.critical),
            "d20": int(attack.d20_roll),
            "attack_total": int(attack.total),
            "target_ac": int(mover.get("ac", 10) or 10),
            "damage": damage_amount,
            "damage_notation": damage_notation,
        }
        await event_bus.publish_to_session(
            session_id,
            EventType.OPPORTUNITY_ATTACK_TRIGGERED,
            payload,
            source=source,
        )
        await event_bus.publish_to_session(
            session_id,
            EventType.ACTION_ECONOMY_CHANGED,
            {
                "combatant_id": attacker_id,
                "action_economy": getattr(
                    entry.action_economy,
                    "__dict__",
                    entry.action_economy,
                ),
            },
            source=source,
        )
        active.mark_dirty()
        results.append(OpportunityAttackResult(**payload))
        if not is_active_combatant(mover):
            break

    return results
