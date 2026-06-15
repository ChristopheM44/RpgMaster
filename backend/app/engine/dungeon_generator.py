"""Pure deterministic dungeon generator.

The runtime stores only a seed and parameters. This module turns them into a
stable room graph and room scene skeletons without touching I/O, DB state, or
LLM output.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import asdict, dataclass
from math import ceil
from typing import Any, Literal

from app.engine.scene_primitives import asset_element as _asset_element
from app.engine.scene_primitives import ellipse as _ellipse
from app.engine.scene_primitives import rect as _rect
from app.engine.scene_primitives import seed_int as _seed_int
from app.engine.theme_packs import THEME_PACKS

DungeonRoomKind = Literal["gateway", "chamber", "vault", "lair", "snare", "passage"]
DungeonSize = Literal["small", "medium", "large"]

# Dressing générique (pilier, gravats, caisses, tonneaux) délégué au pack "dungeon" —
# les pièces narratives propres à chaque DungeonRoomKind (escalier, coffre, autel...)
# restent définies localement dans _room_elements().
_DUNGEON_PACK = THEME_PACKS["dungeon"]
_COVER_PILLAR, _COVER_RUBBLE, _COVER_CRATES = _DUNGEON_PACK.cover_assets
_DECOR_BARREL = _DUNGEON_PACK.decor_assets[0]

_ROOM_COUNTS: dict[str, int] = {"small": 5, "medium": 8, "large": 12}
_ROOM_LABELS: dict[str, str] = {
    "gateway": "Entrée",
    "chamber": "Salle de garde",
    "vault": "Salle du trésor",
    "lair": "Antre",
    "snare": "Salle piégée",
    "passage": "Jonction",
}
_ROOM_DESCRIPTIONS: dict[str, str] = {
    "gateway": "Une entrée froide ouvre sur des marches usées et des murs humides.",
    "chamber": "Une salle de pierre garde encore les marques d'occupants hostiles.",
    "vault": "Des alcôves fermées et un coffre massif attirent immédiatement le regard.",
    "lair": "L'air se charge d'une présence lourde : cette salle sert d'antre au maître des lieux.",
    "snare": "Le sol paraît trop régulier ; des rainures trahissent un piège ancien.",
    "passage": "Une jonction resserrée distribue plusieurs couloirs dans l'obscurité.",
}


@dataclass(frozen=True)
class DungeonRoom:
    id: str
    kind: DungeonRoomKind
    depth: int
    grid_pos: tuple[int, int]


@dataclass(frozen=True)
class DungeonCorridor:
    id: str
    from_room: str
    to_room: str
    secret: bool = False


@dataclass(frozen=True)
class DungeonParams:
    size: DungeonSize = "medium"
    theme: str = "crypt"
    branchiness: float = 0.35
    cr_target: int | None = None


@dataclass(frozen=True)
class DungeonBlueprint:
    id: str
    seed: str
    params: DungeonParams
    rooms: tuple[DungeonRoom, ...]
    corridors: tuple[DungeonCorridor, ...]
    entry_room_id: str
    boss_room_id: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "seed": self.seed,
            "params": asdict(self.params),
            "rooms": [asdict(room) for room in self.rooms],
            "corridors": [asdict(corridor) for corridor in self.corridors],
            "entry_room_id": self.entry_room_id,
            "boss_room_id": self.boss_room_id,
        }


def generate_dungeon(
    seed: str,
    params: DungeonParams | dict[str, Any] | None = None,
) -> DungeonBlueprint:
    """Generate a connected dungeon blueprint.

    The main spine always runs from the gateway to the boss lair. Branch rooms
    never exceed the boss depth, so the boss remains at max depth even when loops
    or side rooms are added.
    """
    clean_seed = str(seed or "dungeon").strip() or "dungeon"
    clean_params = coerce_dungeon_params(params)
    rng = random.Random(_seed_int(clean_seed))
    room_count = _room_count(clean_params.size)
    spine_count = min(room_count, max(4, ceil(room_count * 0.62)))

    room_specs: list[dict[str, Any]] = []
    occupied: set[tuple[int, int]] = set()
    y = 0
    for idx in range(spine_count):
        if idx > 0:
            y += rng.choice((-1, 0, 0, 1))
        pos = _unused_position((idx * 2, y), occupied)
        occupied.add(pos)
        room_specs.append({"depth": idx, "grid_pos": pos, "spine": True})

    while len(room_specs) < room_count:
        allowed_parents = [
            (idx, room)
            for idx, room in enumerate(room_specs[:spine_count])
            if int(room["depth"]) < spine_count - 2
        ]
        parent_idx, parent = rng.choice(allowed_parents or list(enumerate(room_specs[:1])))
        parent_pos = parent["grid_pos"]
        pos = _branch_position(parent_pos, occupied, rng)
        occupied.add(pos)
        room_specs.append(
            {
                "depth": min(int(parent["depth"]) + 1, spine_count - 2),
                "grid_pos": pos,
                "spine": False,
                "parent": parent_idx,
            }
        )

    room_kinds = _assign_room_kinds(room_specs, spine_count, rng)
    rooms: list[DungeonRoom] = []
    for idx, spec in enumerate(room_specs):
        kind = room_kinds[idx]
        rooms.append(
            DungeonRoom(
                id=f"room_{idx:02d}_{kind}",
                kind=kind,
                depth=int(spec["depth"]),
                grid_pos=spec["grid_pos"],
            )
        )

    corridors: list[DungeonCorridor] = []
    connected_pairs: set[frozenset[str]] = set()

    def connect(a_idx: int, b_idx: int, *, secret: bool = False) -> None:
        a = rooms[a_idx]
        b = rooms[b_idx]
        pair = frozenset((a.id, b.id))
        if a.id == b.id or pair in connected_pairs:
            return
        connected_pairs.add(pair)
        left, right = sorted((a.id, b.id))
        corridors.append(
            DungeonCorridor(
                id=f"corr_{left}_{right}"[:80],
                from_room=a.id,
                to_room=b.id,
                secret=secret,
            )
        )

    for idx in range(spine_count - 1):
        connect(idx, idx + 1)
    for idx, spec in enumerate(room_specs[spine_count:], start=spine_count):
        connect(int(spec.get("parent", 0)), idx)

    loop_budget = int(round(clean_params.branchiness * max(0, room_count - 3)))
    loop_candidates = _loop_candidates(rooms, connected_pairs)
    rng.shuffle(loop_candidates)
    for a_idx, b_idx in loop_candidates[:loop_budget]:
        connect(a_idx, b_idx, secret=rng.random() < 0.4)

    corridors = sorted(corridors, key=lambda corridor: corridor.id)
    rooms = sorted(rooms, key=lambda room: room.id)
    dungeon_id = _dungeon_id(clean_seed)
    return DungeonBlueprint(
        id=dungeon_id,
        seed=clean_seed,
        params=clean_params,
        rooms=tuple(rooms),
        corridors=tuple(corridors),
        entry_room_id="room_00_gateway",
        boss_room_id=f"room_{spine_count - 1:02d}_lair",
    )


def coerce_dungeon_params(params: DungeonParams | dict[str, Any] | None) -> DungeonParams:
    if isinstance(params, DungeonParams):
        return params
    raw = params if isinstance(params, dict) else {}
    size = str(raw.get("size") or "medium").strip().lower()
    if size not in _ROOM_COUNTS:
        size = "medium"
    theme = str(raw.get("theme") or "crypt").strip().lower()[:40] or "crypt"
    try:
        branchiness = float(raw.get("branchiness", 0.35))
    except (TypeError, ValueError):
        branchiness = 0.35
    branchiness = max(0.0, min(branchiness, 1.0))
    cr_target = raw.get("cr_target")
    try:
        cr_target = max(0, min(int(cr_target), 30)) if cr_target is not None else None
    except (TypeError, ValueError):
        cr_target = None
    return DungeonParams(
        size=size,  # type: ignore[arg-type]
        theme=theme,
        branchiness=branchiness,
        cr_target=cr_target,
    )


def blueprint_to_city_map(bp: DungeonBlueprint, name: str | None = None) -> dict[str, Any]:
    """Project a blueprint to the existing CityMap graph shape."""
    positions = _map_positions(bp.rooms)
    nodes = []
    for room in bp.rooms:
        nodes.append(
            {
                "id": room.id,
                "name": _room_name(room),
                "kind": room.kind,
                "position": positions[room.id],
                "status": "current" if room.id == bp.entry_room_id else "known",
                "description": _ROOM_DESCRIPTIONS[room.kind],
                "short_label": _ROOM_LABELS[room.kind],
                "scene_ids": [room.id],
            }
        )
    edges = [
        {
            "id": corridor.id,
            "from": corridor.from_room,
            "to": corridor.to_room,
            "kind": "secret" if corridor.secret else "alley",
            "travel_hint": (
                "Un passage discret relie ces salles." if corridor.secret else "Couloir de pierre."
            ),
            "hidden": corridor.secret,
        }
        for corridor in bp.corridors
    ]
    return {
        "id": bp.id,
        "region_node_id": bp.id,
        "name": str(name or "Donjon").strip() or "Donjon",
        "current_node_id": bp.entry_room_id,
        "nodes": nodes,
        "edges": edges,
        "background_seed": bp.seed,
        "updated_at": "1970-01-01T00:00:00+00:00",
    }


def room_scene_skeleton(bp: DungeonBlueprint, room_id: str) -> dict[str, Any]:
    """Return a minimal 12x12 SceneLayout for one room."""
    room = _room_by_id(bp, room_id)
    exits = _room_exits(bp, room)
    pois = _room_pois(room)
    return {
        "scene_id": room.id,
        "cols": 12,
        "rows": 12,
        "cell_size_m": 1.5,
        "terrain": "stone",
        "scene_theme": "dungeon",
        "description": _ROOM_DESCRIPTIONS[room.kind],
        "state": "uncleared",
        "physical_state": f"Donjon {bp.params.theme}. Profondeur {room.depth}.",
        "pois": pois,
        "exits": exits,
        "party_positions": {},
        "elements": _room_elements(room),
        "ambiance": {"light": "torchlit", "fog_density": 0.25},
        "vegetation_density": 0.0,
    }


def adjacent_room_ids(bp: DungeonBlueprint, room_id: str) -> list[str]:
    ids: list[str] = []
    for corridor in bp.corridors:
        if corridor.from_room == room_id:
            ids.append(corridor.to_room)
        elif corridor.to_room == room_id:
            ids.append(corridor.from_room)
    return sorted(ids)


def room_kind(bp: DungeonBlueprint, room_id: str) -> DungeonRoomKind | None:
    for room in bp.rooms:
        if room.id == room_id:
            return room.kind
    return None


def _dungeon_id(seed: str) -> str:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:10]
    return f"dungeon_{digest}"


def _room_count(size: str) -> int:
    return _ROOM_COUNTS.get(size, _ROOM_COUNTS["medium"])


def _unused_position(pos: tuple[int, int], occupied: set[tuple[int, int]]) -> tuple[int, int]:
    if pos not in occupied:
        return pos
    x, y = pos
    radius = 1
    while True:
        for dx, dy in ((0, radius), (0, -radius), (radius, 0), (-radius, 0)):
            candidate = (x + dx, y + dy)
            if candidate not in occupied:
                return candidate
        radius += 1


def _branch_position(
    parent_pos: tuple[int, int],
    occupied: set[tuple[int, int]],
    rng: random.Random,
) -> tuple[int, int]:
    x, y = parent_pos
    offsets = [(0, -2), (0, 2), (1, -1), (1, 1), (-1, -1), (-1, 1)]
    rng.shuffle(offsets)
    for dx, dy in offsets:
        candidate = (x + dx, y + dy)
        if candidate not in occupied:
            return candidate
    return _unused_position((x, y + 3), occupied)


def _assign_room_kinds(
    room_specs: list[dict[str, Any]],
    spine_count: int,
    rng: random.Random,
) -> list[DungeonRoomKind]:
    kinds: list[DungeonRoomKind] = []
    branch_pool: tuple[DungeonRoomKind, ...] = (
        "vault",
        "snare",
        "chamber",
        "passage",
        "chamber",
        "snare",
    )
    for idx, spec in enumerate(room_specs):
        if idx == 0:
            kinds.append("gateway")
        elif idx == spine_count - 1:
            kinds.append("lair")
        elif spec.get("spine"):
            kinds.append("passage" if idx % 3 == 0 else "chamber")
        else:
            kinds.append(rng.choice(branch_pool))
    if "vault" not in kinds and len(kinds) > 4:
        for idx in range(len(kinds) - 1, spine_count - 1, -1):
            if kinds[idx] not in {"gateway", "lair"}:
                kinds[idx] = "vault"
                break
    return kinds


def _loop_candidates(
    rooms: list[DungeonRoom],
    connected_pairs: set[frozenset[str]],
) -> list[tuple[int, int]]:
    candidates: list[tuple[int, int]] = []
    for a_idx, a in enumerate(rooms):
        for b_idx, b in enumerate(rooms[a_idx + 1 :], start=a_idx + 1):
            pair = frozenset((a.id, b.id))
            if pair in connected_pairs:
                continue
            distance = abs(a.grid_pos[0] - b.grid_pos[0]) + abs(a.grid_pos[1] - b.grid_pos[1])
            if 2 <= distance <= 5 and abs(a.depth - b.depth) <= 2:
                candidates.append((a_idx, b_idx))
    return candidates


def _map_positions(rooms: tuple[DungeonRoom, ...]) -> dict[str, dict[str, float]]:
    xs = [room.grid_pos[0] for room in rooms]
    ys = [room.grid_pos[1] for room in rooms]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    span_x = max(max_x - min_x, 1)
    span_y = max(max_y - min_y, 1)
    positions: dict[str, dict[str, float]] = {}
    for room in rooms:
        x = 14.0 + ((room.grid_pos[0] - min_x) / span_x) * 72.0
        y = 18.0 + ((room.grid_pos[1] - min_y) / span_y) * 64.0
        positions[room.id] = {"x": round(x, 2), "y": round(y, 2)}
    return positions


def _room_name(room: DungeonRoom) -> str:
    label = _ROOM_LABELS.get(room.kind, "Salle")
    if room.kind == "gateway":
        return "Entrée du donjon"
    if room.kind == "lair":
        return "Antre final"
    return f"{label} {room.depth + 1}"


def _room_by_id(bp: DungeonBlueprint, room_id: str) -> DungeonRoom:
    for room in bp.rooms:
        if room.id == room_id:
            return room
    raise KeyError(f"Unknown dungeon room: {room_id}")


def _room_exits(bp: DungeonBlueprint, room: DungeonRoom) -> list[dict[str, Any]]:
    by_id = {item.id: item for item in bp.rooms}
    exits: list[dict[str, Any]] = []
    for idx, target_id in enumerate(adjacent_room_ids(bp, room.id)):
        target = by_id[target_id]
        secret = _is_secret_corridor(bp, room.id, target_id)
        target_label = _ROOM_LABELS[target.kind].lower()
        exits.append(
            {
                "id": f"exit_{target_id}"[:80],
                "label": "Passage discret" if secret else f"Vers {target_label}",
                "description": (
                    "Une couture sombre laisse deviner un passage secondaire."
                    if secret
                    else f"Un couloir mène vers {target_label}."
                ),
                "position": _exit_position(room, target, idx),
                "leads_to": target_id,
            }
        )
    return exits


def _is_secret_corridor(bp: DungeonBlueprint, a: str, b: str) -> bool:
    pair = {a, b}
    for corridor in bp.corridors:
        if {corridor.from_room, corridor.to_room} == pair:
            return corridor.secret
    return False


def _exit_position(room: DungeonRoom, target: DungeonRoom, idx: int) -> dict[str, int]:
    dx = target.grid_pos[0] - room.grid_pos[0]
    dy = target.grid_pos[1] - room.grid_pos[1]
    offset = (idx % 3) - 1
    if abs(dx) >= abs(dy) and dx > 0:
        return {"col": 11, "row": max(2, min(9, 6 + offset))}
    if abs(dx) >= abs(dy) and dx < 0:
        return {"col": 0, "row": max(2, min(9, 6 + offset))}
    if dy > 0:
        return {"col": max(2, min(9, 6 + offset)), "row": 11}
    return {"col": max(2, min(9, 6 + offset)), "row": 0}


def _room_pois(room: DungeonRoom) -> list[dict[str, Any]]:
    if room.kind == "vault":
        return [
            {
                "id": "loot_cache",
                "name": "Cache scellée",
                "kind": "loot",
                "icon": "loot",
                "position": {"col": 8, "row": 5},
                "description": "Un coffre renforcé repose sous une couche de poussière.",
                "action_hint": "Examiner ou forcer la serrure.",
                "element_id": "element_loot_cache",
            }
        ]
    if room.kind == "snare":
        return [
            {
                "id": "floor_snare",
                "name": "Dalles suspectes",
                "kind": "hazard",
                "icon": "trap",
                "position": {"col": 5, "row": 5},
                "description": "Des dalles plus claires dessinent une ligne presque invisible.",
                "action_hint": "Repérer, désamorcer ou contourner le piège.",
                "element_id": "element_floor_snare",
            }
        ]
    if room.kind == "lair":
        return [
            {
                "id": "boss_sign",
                "name": "Marque de domination",
                "kind": "clue",
                "icon": "clue",
                "position": {"col": 6, "row": 3},
                "description": "Une marque ancienne signale que ce lieu est revendiqué.",
                "action_hint": "Identifier l'origine de la marque.",
                "element_id": "element_boss_sign",
            }
        ]
    return []


def _room_elements(room: DungeonRoom) -> list[dict[str, Any]]:
    common_lights = [
        _asset_element(
            "torch_nw",
            "Torche murale",
            "light",
            _rect(1.0, 1.0, 0.45, 0.45),
            "prop/torch_mounted",
            blocks_movement=False,
            opaque=False,
            interactive=True,
        ),
        _asset_element(
            "torch_se",
            "Torche murale",
            "light",
            _rect(10.55, 10.55, 0.45, 0.45),
            "prop/torch_mounted",
            blocks_movement=False,
            opaque=False,
            interactive=True,
        ),
    ]
    by_kind: dict[DungeonRoomKind, list[dict[str, Any]]] = {
        "gateway": [
            _asset_element(
                "entry_stairs",
                "Escalier d'entrée",
                "stairs",
                _rect(5.2, 1.0, 1.6, 1.3),
                "prop/stairs",
                blocks_movement=False,
                opaque=False,
                interactive=True,
                facing="north",
                vertical_direction="up",
            ),
            _asset_element(
                "entry_rubble",
                "Débris du seuil",
                "cover",
                _rect(3.0, 7.0, 1.2, 1.0),
                _COVER_RUBBLE,
            ),
        ],
        "chamber": [
            _asset_element(
                "pillar_west", "Pilier de garde", "cover", _rect(3.0, 4.0, 0.8, 0.8), _COVER_PILLAR
            ),
            _asset_element(
                "pillar_east", "Pilier de garde", "cover", _rect(8.2, 6.8, 0.8, 0.8), _COVER_PILLAR
            ),
            _asset_element(
                "supply_crates",
                "Caisses de garnison",
                "cover",
                _rect(6.0, 3.0, 1.2, 0.9),
                _COVER_CRATES,
            ),
        ],
        "vault": [
            _asset_element(
                "element_loot_cache",
                "Coffre au trésor scellé",
                "furniture",
                _rect(7.65, 4.65, 1.0, 1.0),
                "prop/chest_gold",
                interactive=True,
            ),
            _asset_element(
                "vault_shelf",
                "Étagère d'archives",
                "furniture",
                _rect(1.0, 4.2, 0.7, 2.2),
                "prop/shelf_large",
            ),
            _asset_element(
                "vault_barrels",
                "Tonneaux poussiéreux",
                "cover",
                _rect(9.0, 8.0, 1.1, 1.1),
                _DECOR_BARREL,
            ),
        ],
        "lair": [
            _asset_element(
                "element_boss_sign",
                "Autel marqué",
                "decor",
                _rect(5.2, 2.4, 1.6, 1.0),
                "prop/table_medium",
                interactive=True,
            ),
            _asset_element(
                "lair_pillar_west",
                "Pilier rituel",
                "cover",
                _rect(2.5, 5.0, 0.9, 0.9),
                _COVER_PILLAR,
            ),
            _asset_element(
                "lair_pillar_east",
                "Pilier rituel",
                "cover",
                _rect(8.6, 5.0, 0.9, 0.9),
                _COVER_PILLAR,
            ),
            _asset_element(
                "lair_rubble",
                "Gravats rituels",
                "cover",
                _rect(6.0, 8.5, 1.4, 1.0),
                _COVER_RUBBLE,
            ),
        ],
        "snare": [
            _asset_element(
                "element_floor_snare",
                "Dalles piégées",
                "hazard",
                _ellipse(5.5, 5.5, 1.2, 0.9),
                "",
                blocks_movement=False,
                opaque=False,
                interactive=True,
            ),
            _asset_element(
                "snare_crates",
                "Caisses renversées",
                "cover",
                _rect(2.5, 7.0, 1.2, 0.9),
                _COVER_CRATES,
            ),
            _asset_element(
                "snare_rubble",
                "Gravats instables",
                "cover",
                _rect(8.2, 3.0, 1.2, 1.0),
                _COVER_RUBBLE,
            ),
        ],
        "passage": [
            _asset_element(
                "passage_barrels",
                "Tonneaux abandonnés",
                "cover",
                _rect(3.0, 4.8, 1.0, 1.0),
                _DECOR_BARREL,
            ),
            _asset_element(
                "passage_crates",
                "Caisses empilées",
                "cover",
                _rect(8.0, 6.3, 1.2, 0.9),
                _COVER_CRATES,
            ),
        ],
    }
    return [*common_lights, *by_kind.get(room.kind, [])]
