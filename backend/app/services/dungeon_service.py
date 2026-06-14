"""Runtime glue for procedural dungeons.

The generator remains pure in ``app.engine``. This service owns the played state:
which dungeon is active, which room is current, and which rooms are cleared or
looted so backtracking never respawns enemies.
"""

from __future__ import annotations

import hashlib
import random
from copy import deepcopy
from dataclasses import asdict
from typing import Any

from app.engine.dungeon_generator import (
    DungeonBlueprint,
    adjacent_room_ids,
    blueprint_to_city_map,
    generate_dungeon,
    room_kind,
    room_scene_skeleton,
)
from app.engine.encounter_builder import BuiltEncounter
from app.game.session_manager import ActiveSession
from app.services.encounter_service import encounter_service
from app.services.local_map_service import enrich_scene_layout

DUNGEON_RUNTIME_KEY = "dungeon_runtime"
ACTIVE_DUNGEON_ID_KEY = "active_dungeon_id"
ACTIVE_DUNGEON_ENCOUNTER_KEY = "active_dungeon_encounter"


def ensure_dungeon_city_map(
    active: ActiveSession,
    dungeon_config: dict[str, Any],
) -> tuple[dict[str, Any], DungeonBlueprint]:
    """Ensure a dungeon graph exists in ``active.state_data['world_maps']``."""
    bp = _blueprint_from_config(dungeon_config)
    dungeon_id = bp.id
    world_maps = _world_maps(active)
    city_maps = world_maps.setdefault("city_maps", {})
    if not isinstance(city_maps, dict):
        city_maps = {}
        world_maps["city_maps"] = city_maps

    city_map = city_maps.get(dungeon_id)
    if not isinstance(city_map, dict):
        city_map = blueprint_to_city_map(bp, str(dungeon_config.get("name") or "Donjon"))
        endpoint_node_id = str(dungeon_config.get("endpoint_node_id") or "").strip()
        if endpoint_node_id:
            city_map["region_node_id"] = endpoint_node_id
        city_maps[dungeon_id] = city_map

    runtime = _runtime_for(active, dungeon_id, dungeon_config, bp)
    current_room_id = str(runtime.get("current_room_id") or bp.entry_room_id)
    _set_current_room(city_map, current_room_id)
    world_maps["active_city_id"] = dungeon_id
    world_maps[ACTIVE_DUNGEON_ID_KEY] = dungeon_id
    active.mark_dirty()
    return city_map, bp


def enter_dungeon(
    active: ActiveSession,
    dungeon_config: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], DungeonBlueprint]:
    """Activate a dungeon and materialize its entry room."""
    city_map, bp = ensure_dungeon_city_map(active, dungeon_config)
    scene = transition_to_room(active, bp.id, bp.entry_room_id)
    return city_map, scene, bp


def transition_to_room(
    active: ActiveSession,
    dungeon_id: str,
    room_id: str,
) -> dict[str, Any]:
    """Move the party to a room in the active dungeon and return its scene."""
    state = active.state_data if isinstance(active.state_data, dict) else {}
    runtime = _runtime_or_none(state, dungeon_id)
    if runtime is None:
        raise KeyError(f"Unknown active dungeon: {dungeon_id}")
    bp = _blueprint_from_config(runtime)
    if room_id not in {room.id for room in bp.rooms}:
        raise KeyError(f"Unknown dungeon room: {room_id}")

    world_maps = _world_maps(active)
    city_maps = world_maps.setdefault("city_maps", {})
    city_map = city_maps.get(dungeon_id)
    if not isinstance(city_map, dict):
        city_map = blueprint_to_city_map(bp, str(runtime.get("name") or "Donjon"))
        city_maps[dungeon_id] = city_map

    _set_current_room(city_map, room_id)
    runtime["current_room_id"] = room_id
    world_maps["active_city_id"] = dungeon_id
    world_maps[ACTIVE_DUNGEON_ID_KEY] = dungeon_id

    scene = materialize_room_scene(active, dungeon_id, room_id)
    active.mark_dirty()
    return scene


def materialize_room_scene(
    active: ActiveSession,
    dungeon_id: str,
    room_id: str,
) -> dict[str, Any]:
    runtime = _require_runtime(active, dungeon_id)
    bp = _blueprint_from_config(runtime)
    scene = room_scene_skeleton(bp, room_id)
    scene["party_positions"] = _party_positions(active)
    room_state = _room_runtime(runtime, room_id)
    if room_state.get("cleared"):
        scene["state"] = "cleared"
        scene["physical_state"] = "La salle a déjà été sécurisée par le groupe."
    enrich_scene_layout(scene)
    populate_room(active, dungeon_id, room_id, scene)
    return scene


def populate_room(
    active: ActiveSession,
    dungeon_id: str,
    room_id: str,
    scene: dict[str, Any],
) -> list[str]:
    """Populate a room and prime combat when needed.

    Returns the monster ids selected for the room. Empty means the room is safe
    or already cleared.
    """
    runtime = _require_runtime(active, dungeon_id)
    room_state = _room_runtime(runtime, room_id)
    if room_state.get("cleared"):
        _clear_pending_for_room(active, dungeon_id, room_id)
        return []

    kind = room_kind(_blueprint_from_config(runtime), room_id)
    if kind not in {"chamber", "lair"}:
        _clear_pending_for_room(active, dungeon_id, room_id)
        return []

    monster_ids = _select_monster_ids(active, runtime, room_id, kind)
    if not monster_ids:
        _clear_pending_for_room(active, dungeon_id, room_id)
        return []

    room_state["populated"] = True
    active.state_data["pending_encounter"] = {
        "monster_ids": monster_ids,
        "context": _encounter_context(scene, kind),
        "dungeon_id": dungeon_id,
        "room_id": room_id,
    }
    active.state_data["pending_phase_transition"] = "COMBAT"
    active.state_data[ACTIVE_DUNGEON_ENCOUNTER_KEY] = {
        "dungeon_id": dungeon_id,
        "room_id": room_id,
    }
    scene.setdefault("pois", []).append(
        {
            "id": "hostile_presence",
            "name": "Présence hostile",
            "kind": "hostile",
            "icon": "enemy",
            "position": {"col": 6, "row": 6},
            "description": "Des adversaires tiennent la salle et forcent l'initiative.",
            "action_hint": "Se préparer au combat.",
        }
    )
    active.mark_dirty()
    return monster_ids


def mark_room_cleared(active: ActiveSession) -> bool:
    """Mark the dungeon room tied to the current combat as cleared."""
    marker = active.state_data.pop(ACTIVE_DUNGEON_ENCOUNTER_KEY, None)
    if not isinstance(marker, dict):
        return False
    dungeon_id = str(marker.get("dungeon_id") or "").strip()
    room_id = str(marker.get("room_id") or "").strip()
    runtime = _runtime_or_none(active.state_data, dungeon_id)
    if runtime is None or not room_id:
        return False
    room_state = _room_runtime(runtime, room_id)
    room_state["cleared"] = True
    room_state["populated"] = False
    room_state.setdefault("looted", False)

    world_maps = _world_maps(active)
    city_map = (world_maps.get("city_maps") or {}).get(dungeon_id)
    if isinstance(city_map, dict):
        _set_current_room(city_map, room_id)
        for node in city_map.get("nodes") or []:
            if isinstance(node, dict) and node.get("id") == room_id:
                node["status"] = "visited"
    active.mark_dirty()
    return True


def is_room_transition(active: ActiveSession, room_id: str) -> str | None:
    """Return the active dungeon id if ``room_id`` is adjacent to its current room."""
    state = active.state_data if isinstance(active.state_data, dict) else {}
    dungeon_id = _active_dungeon_id(state)
    if not dungeon_id:
        return None
    runtime = _runtime_or_none(state, dungeon_id)
    if runtime is None:
        return None
    current_room_id = str(runtime.get("current_room_id") or "").strip()
    if not current_room_id or room_id == current_room_id:
        return None
    bp = _blueprint_from_config(runtime)
    if room_id in adjacent_room_ids(bp, current_room_id):
        return dungeon_id
    return None


def _world_maps(active: ActiveSession) -> dict[str, Any]:
    world_maps = active.state_data.setdefault(
        "world_maps",
        {"region_map": None, "city_maps": {}, "active_city_id": None},
    )
    if not isinstance(world_maps, dict):
        world_maps = {"region_map": None, "city_maps": {}, "active_city_id": None}
        active.state_data["world_maps"] = world_maps
    world_maps.setdefault("region_map", None)
    world_maps.setdefault("city_maps", {})
    world_maps.setdefault("active_city_id", None)
    return world_maps


def _runtime_for(
    active: ActiveSession,
    dungeon_id: str,
    dungeon_config: dict[str, Any],
    bp: DungeonBlueprint,
) -> dict[str, Any]:
    runtime_root = active.state_data.setdefault(DUNGEON_RUNTIME_KEY, {})
    if not isinstance(runtime_root, dict):
        runtime_root = {}
        active.state_data[DUNGEON_RUNTIME_KEY] = runtime_root
    runtime = runtime_root.setdefault(
        dungeon_id,
        {
            "id": dungeon_id,
            "seed": bp.seed,
            "params": asdict(bp.params),
            "endpoint_node_id": dungeon_config.get("endpoint_node_id"),
            "name": dungeon_config.get("name") or "Donjon",
            "entry_room_id": bp.entry_room_id,
            "boss_room_id": bp.boss_room_id,
            "current_room_id": bp.entry_room_id,
            "rooms": {},
        },
    )
    runtime.setdefault("seed", bp.seed)
    runtime.setdefault("params", asdict(bp.params))
    runtime.setdefault("entry_room_id", bp.entry_room_id)
    runtime.setdefault("boss_room_id", bp.boss_room_id)
    runtime.setdefault("current_room_id", bp.entry_room_id)
    runtime.setdefault("rooms", {})
    return runtime


def _runtime_or_none(state: dict[str, Any], dungeon_id: str) -> dict[str, Any] | None:
    runtime_root = state.get(DUNGEON_RUNTIME_KEY)
    if not isinstance(runtime_root, dict):
        return None
    runtime = runtime_root.get(dungeon_id)
    return runtime if isinstance(runtime, dict) else None


def _require_runtime(active: ActiveSession, dungeon_id: str) -> dict[str, Any]:
    runtime = _runtime_or_none(active.state_data, dungeon_id)
    if runtime is None:
        raise KeyError(f"Unknown active dungeon: {dungeon_id}")
    return runtime


def _room_runtime(runtime: dict[str, Any], room_id: str) -> dict[str, Any]:
    rooms = runtime.setdefault("rooms", {})
    if not isinstance(rooms, dict):
        rooms = {}
        runtime["rooms"] = rooms
    room_state = rooms.setdefault(room_id, {"cleared": False, "looted": False})
    if not isinstance(room_state, dict):
        room_state = {"cleared": False, "looted": False}
        rooms[room_id] = room_state
    return room_state


def _blueprint_from_config(config: dict[str, Any]) -> DungeonBlueprint:
    return generate_dungeon(str(config.get("seed") or "dungeon"), config.get("params") or {})


def _set_current_room(city_map: dict[str, Any], room_id: str) -> None:
    previous = str(city_map.get("current_node_id") or "").strip()
    city_map["current_node_id"] = room_id
    for node in city_map.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        node_id = str(node.get("id") or "")
        if node_id == room_id:
            node["status"] = "current"
        elif node_id == previous and node.get("status") == "current":
            node["status"] = "visited"


def _active_dungeon_id(state: dict[str, Any]) -> str:
    world_maps = state.get("world_maps")
    if isinstance(world_maps, dict):
        dungeon_id = str(world_maps.get(ACTIVE_DUNGEON_ID_KEY) or "").strip()
        if dungeon_id:
            return dungeon_id
    return str(state.get(ACTIVE_DUNGEON_ID_KEY) or "").strip()


def _party_positions(active: ActiveSession) -> dict[str, dict[str, int]]:
    positions: dict[str, dict[str, int]] = {}
    characters = active.state_data.get("characters")
    if not isinstance(characters, dict):
        return positions
    starts = [(2, 8), (3, 8), (2, 9), (3, 9), (4, 8), (4, 9)]
    for idx, char_id in enumerate(characters):
        col, row = starts[idx % len(starts)]
        positions[str(char_id)] = {"col": col, "row": row}
    return positions


def _select_monster_ids(
    active: ActiveSession,
    runtime: dict[str, Any],
    room_id: str,
    kind: str | None,
) -> list[str]:
    rng = _room_rng(active, runtime, room_id)
    chapter = _active_chapter(active)
    custom_refs = [
        f"custom:{item}" for item in _string_list(chapter.get("possible_custom_encounters")) if item
    ]
    srd_refs = _string_list(chapter.get("possible_srd_encounters"))

    if kind == "lair":
        for refs in (custom_refs[:1], srd_refs[:1]):
            built = _built_from_refs(active, refs)
            if built and built.entries:
                return _ids_from_built(built)
        return _ids_from_built(encounter_service.generate(_party_levels(active), "hard", rng=rng))

    pool = srd_refs or custom_refs
    if pool:
        refs = [rng.choice(pool)]
        built = _built_from_refs(active, refs)
        if built and built.entries:
            return _ids_from_built(built)
    return _ids_from_built(encounter_service.generate(_party_levels(active), "medium", rng=rng))


def _built_from_refs(active: ActiveSession, refs: list[str]) -> BuiltEncounter | None:
    if not refs:
        return None
    built = encounter_service.build_from_monster_ids(
        refs,
        custom_monsters=_custom_monsters(active),
    )
    return built if built.entries else None


def _ids_from_built(built: BuiltEncounter) -> list[str]:
    ids: list[str] = []
    for entry in built.entries:
        ids.extend([entry.monster_id] * max(1, int(entry.count)))
    return ids


def _party_levels(active: ActiveSession) -> list[int]:
    characters = active.state_data.get("characters")
    if not isinstance(characters, dict):
        return [1]
    levels: list[int] = []
    for data in characters.values():
        if not isinstance(data, dict):
            continue
        try:
            levels.append(max(1, min(20, int(data.get("level") or 1))))
        except (TypeError, ValueError):
            levels.append(1)
    return levels or [1]


def _custom_monsters(active: ActiveSession) -> list[dict[str, Any]]:
    context = active.state_data.get("campaign_context")
    if not isinstance(context, dict):
        return []
    custom = context.get("custom_monsters")
    return [deepcopy(item) for item in custom or [] if isinstance(item, dict)]


def _active_chapter(active: ActiveSession) -> dict[str, Any]:
    context = active.state_data.get("campaign_context")
    if not isinstance(context, dict):
        return {}
    chapter = context.get("active_chapter")
    return chapter if isinstance(chapter, dict) else {}


def _string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _room_rng(active: ActiveSession, runtime: dict[str, Any], room_id: str) -> random.Random:
    chapter = _active_chapter(active)
    chapter_id = str(chapter.get("id") or "chapter").strip()
    seed = f"{runtime.get('seed')}:{chapter_id}:{runtime.get('id')}:{room_id}"
    return random.Random(int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16))


def _encounter_context(scene: dict[str, Any], kind: str | None) -> str:
    if kind == "lair":
        return "La salle finale du donjon se referme autour de la confrontation."
    return str(scene.get("description") or "Des adversaires gardent la salle.")


def _clear_pending_for_room(active: ActiveSession, dungeon_id: str, room_id: str) -> None:
    pending = active.state_data.get("pending_encounter")
    if (
        isinstance(pending, dict)
        and pending.get("dungeon_id") == dungeon_id
        and pending.get("room_id") == room_id
    ):
        active.state_data.pop("pending_encounter", None)
        active.state_data.pop("pending_phase_transition", None)
        active.state_data.pop(ACTIVE_DUNGEON_ENCOUNTER_KEY, None)
