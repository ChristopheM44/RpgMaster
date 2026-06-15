"""Pure helpers for shared exploration/combat local maps."""

from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable
from math import ceil, floor
from typing import Any

SCENE_ELEMENT_KINDS = {
    "wall",
    "door",
    "window",
    "furniture",
    "cover",
    "hazard",
    "light",
    "stairs",
    "terrain",
    "decor",
}
SCENE_ELEMENT_GEOMETRIES = {"line", "rect", "ellipse"}
VISUAL_ASSET_STATUSES = {"prompt_ready", "generating", "ready", "failed"}
TERRAIN_TYPES = {"road", "street", "path", "plaza_paving", "water", "mud"}
EXIT_PLACEMENTS = {"edge", "embedded"}
SCENE_AMBIANCE_LIGHTS = {"day", "dusk", "night", "torchlit", "overcast"}
SCENE_ELEMENT_FACINGS = {"north", "east", "south", "west"}
SCENE_ELEMENT_VERTICAL_DIRECTIONS = {"up", "down", "level"}
SCENE_ASSET_KEYS = {
    "prop/wall",
    "prop/wall_corner",
    "prop/door",
    "prop/table_medium",
    "prop/table_long",
    "prop/table_small",
    "prop/chair",
    "prop/stool",
    "prop/keg",
    "prop/barrel_small",
    "prop/barrel_large",
    "prop/crates_stacked",
    "prop/chest",
    "prop/chest_gold",
    "prop/shelf_large",
    "prop/shelf_small",
    "prop/pillar",
    "prop/rubble_large",
    "prop/bed_frame",
    "prop/stairs",
    "prop/torch_lit",
    "prop/torch_mounted",
    "prop/campfire",
    "prop/tent",
    "prop/pot",
    "prop/statue",
    "prop/obelisk",
    "nature/rock_large_a",
    "nature/rock_large_b",
    "nature/rock_small_a",
    "nature/rock_small_b",
}

# Défauts 3D optionnels — mêmes valeurs que le fallback client
# (frontend/src/engine3d/adapters/sceneAdapter.ts) pour rester cohérent.
ELEMENT_DEFAULT_HEIGHTS_M: dict[str, float] = {
    "wall": 2.5,
    "door": 2.5,  # wall_doorway.glb = panneau de mur complet (découpe de porte interne)
    "window": 1.0,
    "furniture": 0.8,
    "cover": 1.0,
    "hazard": 0.05,
    "light": 1.6,
    "stairs": 0.4,
    "terrain": 0.02,
    "decor": 0.6,
}
_DEFAULT_ELEMENT_HEIGHT_M = 0.6
_EXTERIOR_WALL_HEIGHT_M = 1.2  # muret/palissade en extérieur, pas un mur porteur
_ELEMENT_HEIGHT_MIN_M, _ELEMENT_HEIGHT_MAX_M = 0.2, 8.0
_ELEMENT_ELEVATION_MIN_M, _ELEMENT_ELEVATION_MAX_M = 0.0, 4.0

_THEME_VEGETATION_DENSITY: dict[str, float] = {
    "forest": 0.8,
    "swamp": 0.6,
    "plains": 0.4,
    "beach": 0.3,
    "coastal": 0.3,
    "rocky": 0.25,
    "mountain": 0.25,
    "desert": 0.15,
    "city": 0.05,
    "dungeon": 0.0,
    "cave": 0.0,
}
_DEFAULT_VEGETATION_DENSITY = 0.3

# MIROIR de FOG_BY_THEME (frontend engine3d/adapters/sceneAdapter.ts) — modifier les deux ensemble.
_THEME_FOG_DENSITY: dict[str, float] = {
    "cave": 0.35,
    "swamp": 0.4,
    "dungeon": 0.25,
    "mountain": 0.25,
    "forest": 0.2,
}
_DEFAULT_FOG_DENSITY = 0.15

_NIGHT_TIME_WORDS = ("night", "nuit")
_DUSK_TIME_WORDS = ("dawn", "dusk", "aube", "crépuscule", "crepuscule", "soir")

_INTERIOR_WORDS = {
    "interieur",
    "intérieur",
    "salle",
    "room",
    "piece",
    "pièce",
    "chambre",
    "auberge",
    "taverne",
    "tavern",
    "maison",
    "forge",
    "entrepot",
    "entrepôt",
    "temple",
    "palais",
    "cave",
    "crypte",
    "donjon",
    "sous-sol",
    "cellier",
    "atelier",
    "boutique",
}
_EMBEDDED_EXIT_WORDS = {
    "trappe",
    "égout",
    "egout",
    "échelle",
    "echelle",
    "escalier",
    "puits",
    "cave",
    "porte",
    "portail",
    "quai",
    "ponton",
    "batiment",
    "bâtiment",
    "entrée",
    "entree",
    "ouverture",
}
_PLAZA_WORDS = {
    "place",
    "marché",
    "marche",
    "festival",
    "cour",
    "parvis",
    "plaza",
    "square",
}
_LOCAL_ROAD_CONTEXT_WORDS = {
    "route",
    "rue",
    "avenue",
    "chemin",
    "sentier",
    "piste",
    "carrefour",
    "croisée",
    "croisee",
    "embranchement",
    "intersection",
    "quai",
    "ponton",
    "pont",
    "porte de ville",
}
_EXPLICIT_SUBTERRANEAN_ACCESS_WORDS = {
    "trappe",
    "égout",
    "egout",
    "grille",
    "bouche",
    "ouverture",
    "échelle",
    "echelle",
    "escalier",
    "puits",
    "accès souterrain",
    "acces souterrain",
    "entrée souterraine",
    "entree souterraine",
    "sous-sol",
}
_STAIRS_ACCESS_WORDS = (
    "trappe",
    "égout",
    "egout",
    "échelle",
    "echelle",
    "escalier",
    "stair",
    "stairs",
    "puits",
    "cave",
    "sous-sol",
    "souterrain",
)
_DOOR_ACCESS_WORDS = (
    "porte",
    "portail",
    "gate",
    "door",
    "grille",
    "entrée",
    "entree",
    "ouverture",
)
_UP_ACCESS_WORDS = (
    "monte",
    "montée",
    "montee",
    "remonte",
    "remontée",
    "remontee",
    "surface",
    "ascend",
    "upward",
    "upstairs",
)
_DOWN_ACCESS_WORDS = (
    "descend",
    "descente",
    "descendre",
    "bas",
    "down",
    "downward",
    "downstairs",
    "égout",
    "egout",
    "cave",
    "sous-sol",
    "souterrain",
    "puits",
    "trappe",
)


def normalize_scene_element(raw: Any, cols: int, rows: int) -> dict[str, Any] | None:
    """Validate and clamp one scene element."""
    if not isinstance(raw, dict):
        return None

    element_id = _clean_text(raw.get("id"), max_len=80)
    name = _clean_text(raw.get("name"), max_len=120)
    if not element_id or not name:
        return None

    kind = _clean_text(raw.get("kind"), max_len=32).lower()
    if kind not in SCENE_ELEMENT_KINDS:
        kind = "decor"

    geometry = normalize_scene_geometry(raw.get("geometry"), cols, rows)
    if geometry is None:
        return None

    element: dict[str, Any] = {
        "id": element_id,
        "name": name,
        "kind": kind,
        "geometry": geometry,
    }
    terrain_type = _clean_text(raw.get("terrain_type"), max_len=32).lower()
    if kind == "terrain" and terrain_type in TERRAIN_TYPES:
        element["terrain_type"] = terrain_type
    description = _clean_text(raw.get("description"), max_len=220)
    if description:
        element["description"] = description
    if isinstance(raw.get("blocks_movement"), bool):
        element["blocks_movement"] = raw["blocks_movement"]
    elif kind in {"wall", "furniture", "cover"}:
        element["blocks_movement"] = True
    if isinstance(raw.get("opaque"), bool):
        element["opaque"] = raw["opaque"]
    elif kind in {"wall", "door", "furniture", "cover"}:
        element["opaque"] = True
    if isinstance(raw.get("interactive"), bool):
        element["interactive"] = raw["interactive"]
    elif kind in {"door", "window", "stairs", "furniture", "hazard", "light"}:
        element["interactive"] = True
    visibility = _clean_text(raw.get("visibility"), max_len=24).lower()
    if visibility in {"visible", "subtle", "hidden"}:
        element["visibility"] = visibility
    if isinstance(raw.get("discovered"), bool):
        element["discovered"] = raw["discovered"]
    facing = _clean_text(raw.get("facing"), max_len=16).lower()
    if facing in SCENE_ELEMENT_FACINGS:
        element["facing"] = facing
    vertical_direction = _clean_text(raw.get("vertical_direction"), max_len=16).lower()
    if vertical_direction in SCENE_ELEMENT_VERTICAL_DIRECTIONS:
        element["vertical_direction"] = vertical_direction
    asset_key = normalize_asset_key(raw.get("asset_key"))
    if asset_key:
        element["asset_key"] = asset_key
    height_m = _parse_optional_float(raw.get("height_m"))
    if height_m is not None:
        element["height_m"] = round(
            max(_ELEMENT_HEIGHT_MIN_M, min(height_m, _ELEMENT_HEIGHT_MAX_M)), 3
        )
    elevation_m = _parse_optional_float(raw.get("elevation_m"))
    if elevation_m is not None:
        element["elevation_m"] = round(
            max(_ELEMENT_ELEVATION_MIN_M, min(elevation_m, _ELEMENT_ELEVATION_MAX_M)), 3
        )
    return element


def normalize_asset_key(raw: Any) -> str | None:
    key = _clean_text(raw, max_len=80)
    return key if key in SCENE_ASSET_KEYS else None


def normalize_scene_geometry(raw: Any, cols: int, rows: int) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    geometry_type = _clean_text(raw.get("type"), max_len=24).lower()
    if geometry_type not in SCENE_ELEMENT_GEOMETRIES:
        return None

    if geometry_type == "line":
        start = _geometry_point(
            raw.get("from") or raw.get("start") or {"col": raw.get("x1"), "row": raw.get("y1")},
            cols,
            rows,
            allow_border=True,
        )
        end = _geometry_point(
            raw.get("to") or raw.get("end") or {"col": raw.get("x2"), "row": raw.get("y2")},
            cols,
            rows,
            allow_border=True,
        )
        if start is None or end is None or start == end:
            return None
        return {"type": "line", "from": start, "to": end}

    if geometry_type == "rect":
        col = _clamp_float(raw.get("col", raw.get("x")), 0.0, float(cols), 0.0)
        row = _clamp_float(raw.get("row", raw.get("y")), 0.0, float(rows), 0.0)
        width = _clamp_float(raw.get("width", raw.get("w")), 0.1, float(cols), 1.0)
        height = _clamp_float(raw.get("height", raw.get("h")), 0.1, float(rows), 1.0)
        width = min(width, max(0.1, float(cols) - col))
        height = min(height, max(0.1, float(rows) - row))
        return {
            "type": "rect",
            "col": round(col, 3),
            "row": round(row, 3),
            "width": round(width, 3),
            "height": round(height, 3),
        }

    col = _clamp_float(raw.get("col", raw.get("cx")), 0.0, float(cols), float(cols) / 2)
    row = _clamp_float(raw.get("row", raw.get("cy")), 0.0, float(rows), float(rows) / 2)
    radius_col = _clamp_float(raw.get("radius_col", raw.get("rx")), 0.1, float(cols), 0.5)
    radius_row = _clamp_float(raw.get("radius_row", raw.get("ry")), 0.1, float(rows), 0.5)
    return {
        "type": "ellipse",
        "col": round(col, 3),
        "row": round(row, 3),
        "radius_col": round(radius_col, 3),
        "radius_row": round(radius_row, 3),
    }


def normalize_visual_asset(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    provider = _clean_text(raw.get("provider"), max_len=48)
    model = _clean_text(raw.get("model"), max_len=120)
    status = _clean_text(raw.get("status"), max_len=24).lower()
    prompt = _clean_text(raw.get("prompt"), max_len=2400)
    if not provider or not model or status not in VISUAL_ASSET_STATUSES:
        return None

    asset: dict[str, Any] = {
        "provider": provider,
        "model": model,
        "status": status,
        "prompt": prompt,
        "prompt_hash": _clean_text(raw.get("prompt_hash"), max_len=64) or _prompt_hash(prompt),
    }
    for key, max_len in (("url", 1000), ("generated_at", 80), ("error", 280)):
        value = _clean_text(raw.get(key), max_len=max_len)
        if value:
            asset[key] = value
    return asset


def enrich_scene_layout(
    layout: dict[str, Any],
    *,
    time_of_day: str | None = None,
) -> dict[str, Any]:
    """Add deterministic local-map elements where the GM supplied only POIs/exits.

    ``time_of_day`` (journal wording, free-form) only drives the default
    ambiance light when the GM did not provide a valid one.
    """
    cols = int(layout.get("cols") or 12)
    rows = int(layout.get("rows") or 12)
    elements = [
        element
        for element in layout.get("elements", [])
        if isinstance(element, dict) and element.get("id")
    ]
    by_id = {str(element["id"]): element for element in elements}

    _normalize_exits(layout, by_id, cols, rows)

    interior = _is_interior_scene(layout)
    if interior:
        _add_boundary_walls(by_id, cols, rows)
        _add_exit_access_elements(by_id, layout, cols, rows, interior=True)
        _add_windows(by_id, layout, cols, rows)
        _add_default_furniture(by_id, layout, cols, rows)
    else:
        _add_exit_access_elements(by_id, layout, cols, rows, interior=False)
        if _is_plaza_scene(layout):
            _add_plaza_elements(by_id, layout, cols, rows)

    _add_poi_elements(by_id, layout, cols, rows)
    _strip_unrevealed_subterranean_access(by_id, layout)
    _carve_wall_openings(by_id)
    for element in by_id.values():
        _apply_element_3d_defaults(element, interior=interior)
    _apply_scene_3d_defaults(layout, time_of_day=time_of_day)
    layout["elements"] = list(by_id.values())[:96]
    return layout


def build_scene_visual_asset(
    scene: dict[str, Any],
    *,
    provider: str,
    model: str,
) -> dict[str, Any]:
    prompt = build_scene_visual_prompt(scene)
    return {
        "provider": provider,
        "model": model,
        "status": "prompt_ready",
        "prompt": prompt,
        "prompt_hash": _prompt_hash(prompt),
    }


def build_graph_map_visual_asset(
    map_data: dict[str, Any],
    *,
    map_kind: str,
    provider: str,
    model: str,
) -> dict[str, Any]:
    prompt = build_graph_map_visual_prompt(map_data, map_kind=map_kind)
    return {
        "provider": provider,
        "model": model,
        "status": "prompt_ready",
        "prompt": prompt,
        "prompt_hash": _prompt_hash(prompt),
    }


def build_graph_map_visual_prompt(map_data: dict[str, Any], *, map_kind: str) -> str:
    """Build a public prompt for city/region top-down map backings."""
    label = "regional wilderness" if map_kind == "region" else "fantasy city"
    parts = [
        f"Top-down illustrated {label} map for a tabletop RPG.",
        f"Map name: {_clean_text(map_data.get('name'), max_len=160) or map_kind}",
    ]
    nodes = [
        f"{node.get('kind')}:{node.get('name')}"
        for node in map_data.get("nodes", [])[:32]
        if isinstance(node, dict)
    ]
    if nodes:
        parts.append("Visible landmarks: " + ", ".join(nodes))
    edges = [
        f"{edge.get('kind')} route"
        for edge in map_data.get("edges", [])[:24]
        if isinstance(edge, dict)
    ]
    if edges:
        parts.append("Connections: " + ", ".join(edges))
    decor = map_data.get("decor") if isinstance(map_data.get("decor"), dict) else {}
    if decor:
        decor_parts = [
            key
            for key in ("forests", "mountains", "coastline", "river", "decorative_roads")
            if decor.get(key)
        ]
        if decor_parts:
            parts.append("Natural features: " + ", ".join(decor_parts))
    parts.append("No labels, no UI, no hidden locations, leave room for clickable markers.")
    return " ".join(parts)


def build_scene_visual_prompt(scene: dict[str, Any]) -> str:
    """Build a public, player-visible image prompt for a top-down local map."""
    parts = [
        "Top-down fantasy tabletop RPG battle map, orthographic view.",
        f"Theme: {_clean_text(scene.get('scene_theme'), max_len=60) or 'fantasy'}",
        f"Terrain: {_clean_text(scene.get('terrain'), max_len=120) or 'unknown'}",
    ]
    description = _clean_text(scene.get("description"), max_len=500)
    if description:
        parts.append(f"Visible scene: {description}")

    element_bits = [
        _element_prompt_bit(element)
        for element in scene.get("elements", [])[:24]
        if isinstance(element, dict) and element.get("visibility") != "hidden"
    ]
    if element_bits:
        parts.append("Physical layout: " + ", ".join(element_bits))

    poi_bits = [
        f"{poi.get('kind')}:{poi.get('name')}"
        for poi in scene.get("pois", [])[:16]
        if isinstance(poi, dict)
    ]
    if poi_bits:
        parts.append("Important visible points: " + ", ".join(poi_bits))

    exit_bits = [
        str(exit_.get("label") or exit_.get("leads_to"))
        for exit_ in scene.get("exits", [])[:8]
        if isinstance(exit_, dict)
    ]
    if exit_bits:
        parts.append("Visible exits: " + ", ".join(exit_bits))

    if _is_plaza_scene(scene) and not _has_explicit_local_road(scene):
        parts.append(
            "Open paved town square with stalls, crowd flow and civic decor; "
            "do not draw a traversing road or path unless it is listed as terrain."
        )
    parts.append("No labels, no text, no UI, keep doors and obstacles aligned to a square grid.")
    return " ".join(part for part in parts if part)


def element_grid_cells(element: dict[str, Any], cols: int, rows: int) -> list[dict[str, int]]:
    geometry = element.get("geometry") if isinstance(element, dict) else None
    if not isinstance(geometry, dict):
        return []
    if geometry.get("type") == "rect":
        start_col = max(0, floor(float(geometry.get("col", 0))))
        start_row = max(0, floor(float(geometry.get("row", 0))))
        end_col = min(
            cols - 1,
            ceil(float(geometry.get("col", 0)) + float(geometry.get("width", 1))) - 1,
        )
        end_row = min(
            rows - 1,
            ceil(float(geometry.get("row", 0)) + float(geometry.get("height", 1))) - 1,
        )
        return [
            {"col": col, "row": row}
            for row in range(start_row, end_row + 1)
            for col in range(start_col, end_col + 1)
        ]
    if geometry.get("type") == "ellipse":
        col = int(round(float(geometry.get("col", 0))))
        row = int(round(float(geometry.get("row", 0))))
        if 0 <= col < cols and 0 <= row < rows:
            return [{"col": col, "row": row}]
    return []


def _add_boundary_walls(by_id: dict[str, dict[str, Any]], cols: int, rows: int) -> None:
    walls = {
        "wall_north": (
            "Mur nord",
            {"type": "line", "from": {"col": 0, "row": 0}, "to": {"col": cols, "row": 0}},
        ),
        "wall_east": (
            "Mur est",
            {
                "type": "line",
                "from": {"col": cols, "row": 0},
                "to": {"col": cols, "row": rows},
            },
        ),
        "wall_south": (
            "Mur sud",
            {
                "type": "line",
                "from": {"col": cols, "row": rows},
                "to": {"col": 0, "row": rows},
            },
        ),
        "wall_west": (
            "Mur ouest",
            {"type": "line", "from": {"col": 0, "row": rows}, "to": {"col": 0, "row": 0}},
        ),
    }
    for element_id, (name, geometry) in walls.items():
        by_id.setdefault(
            element_id,
            {
                "id": element_id,
                "name": name,
                "kind": "wall",
                "geometry": geometry,
                "blocks_movement": True,
                "opaque": True,
                "asset_key": "prop/wall",
            },
        )
    corners = {
        "wall_corner_nw": (0.0, 0.0),
        "wall_corner_ne": (cols - 0.6, 0.0),
        "wall_corner_se": (cols - 0.6, rows - 0.6),
        "wall_corner_sw": (0.0, rows - 0.6),
    }
    for element_id, (col, row) in corners.items():
        by_id.setdefault(
            element_id,
            {
                "id": element_id,
                "name": "Angle de mur",
                "kind": "wall",
                "geometry": {
                    "type": "rect",
                    "col": round(max(0.0, col), 3),
                    "row": round(max(0.0, row), 3),
                    "width": 0.6,
                    "height": 0.6,
                },
                "blocks_movement": True,
                "opaque": True,
                "asset_key": "prop/wall_corner",
            },
        )


def _add_exit_access_elements(
    by_id: dict[str, dict[str, Any]],
    layout: dict[str, Any],
    cols: int,
    rows: int,
    *,
    interior: bool,
) -> None:
    for exit_ in layout.get("exits", []):
        if not isinstance(exit_, dict):
            continue
        pos = exit_.get("position")
        if not isinstance(pos, dict):
            continue
        corpus = _exit_corpus(exit_)
        if not _exit_needs_access_element(exit_, corpus, interior=interior):
            continue

        kind = _exit_access_kind(corpus)
        element_id = _clean_text(exit_.get("element_id"), max_len=80)
        if element_id and element_id in by_id:
            _apply_exit_access_defaults(by_id[element_id], exit_, cols, rows)
            continue
        if not element_id:
            element_id = f"element_{exit_.get('id')}_{kind}"
            exit_["element_id"] = element_id
        by_id.setdefault(
            element_id,
            {
                "id": element_id,
                "name": exit_.get("label") or ("Escalier" if kind == "stairs" else "Porte"),
                "kind": kind,
                "geometry": _access_geometry(exit_, kind, cols, rows),
                "description": exit_.get("description") or exit_.get("leads_to") or "",
                "blocks_movement": False,
                "opaque": False,
                "interactive": True,
                "asset_key": "prop/stairs" if kind == "stairs" else "prop/door",
                **_access_orientation_fields(exit_, kind, cols, rows),
            },
        )


def _exit_needs_access_element(exit_: dict[str, Any], corpus: str, *, interior: bool) -> bool:
    placement = _clean_text(exit_.get("placement"), max_len=24).lower()
    if placement == "embedded":
        return True
    if interior:
        return True
    return _exit_access_kind(corpus) == "stairs" or any(
        word in corpus for word in _DOOR_ACCESS_WORDS
    )


def _apply_exit_access_defaults(
    element: dict[str, Any],
    exit_: dict[str, Any],
    cols: int,
    rows: int,
) -> None:
    kind = str(element.get("kind") or "").lower()
    if kind not in {"door", "stairs"}:
        return
    element.setdefault("blocks_movement", False)
    element.setdefault("opaque", False)
    element.setdefault("interactive", True)
    element.setdefault("asset_key", "prop/stairs" if kind == "stairs" else "prop/door")
    for key, value in _access_orientation_fields(exit_, kind, cols, rows).items():
        element.setdefault(key, value)


def _access_orientation_fields(
    exit_: dict[str, Any],
    kind: str,
    cols: int,
    rows: int,
) -> dict[str, str]:
    fields: dict[str, str] = {}
    facing = _infer_exit_facing(exit_, cols, rows)
    if facing:
        fields["facing"] = facing
    explicit_vertical = _clean_text(exit_.get("vertical_direction"), max_len=16).lower()
    if kind == "stairs":
        fields["vertical_direction"] = (
            explicit_vertical
            if explicit_vertical in SCENE_ELEMENT_VERTICAL_DIRECTIONS
            else _infer_vertical_direction(_exit_corpus(exit_))
        )
    elif "vertical_direction" not in fields:
        fields["vertical_direction"] = "level"
    return fields


def _add_windows(
    by_id: dict[str, dict[str, Any]],
    layout: dict[str, Any],
    cols: int,
    rows: int,
) -> None:
    if any(element.get("kind") == "window" for element in by_id.values()):
        return
    if not _interior_allows_windows(layout):
        return
    for idx, col in enumerate((max(1, cols * 0.25), min(cols - 2, cols * 0.72)), start=1):
        element_id = f"window_{idx}"
        by_id.setdefault(
            element_id,
            {
                "id": element_id,
                "name": f"Fenêtre {idx}",
                "kind": "window",
                "geometry": {
                    "type": "rect",
                    "col": round(float(col), 3),
                    "row": 0.0,
                    "width": 1.4,
                    "height": 0.18,
                },
                "description": "Une ouverture laisse filtrer la lumière extérieure.",
                "blocks_movement": True,
                "opaque": False,
                "interactive": True,
            },
        )


def _add_default_furniture(
    by_id: dict[str, dict[str, Any]],
    layout: dict[str, Any],
    cols: int,
    rows: int,
) -> None:
    if any(element.get("kind") in {"furniture", "cover"} for element in by_id.values()):
        return
    if cols < 6 or rows < 6:
        return
    by_id.setdefault(
        "table_centrale",
        {
            "id": "table_centrale",
            "name": "Table centrale",
            "kind": "furniture",
            "geometry": {
                "type": "rect",
                "col": max(2, cols / 2 - 1.25),
                "row": max(2, rows / 2 - 0.75),
                "width": 2.5,
                "height": 1.5,
            },
            "description": "Un meuble massif structure l'espace et peut servir de couvert.",
            "blocks_movement": True,
            "opaque": False,
            "asset_key": "prop/table_medium",
        },
    )
    if _clean_text(layout.get("scene_theme"), max_len=40) != "cave":
        by_id.setdefault(
            "etagere_murale",
            {
                "id": "etagere_murale",
                "name": "Étagère murale",
                "kind": "furniture",
                "geometry": {
                    "type": "rect",
                    "col": 1.0,
                    "row": max(1, rows * 0.35),
                    "width": 0.7,
                    "height": 2.2,
                },
                "description": "Un élément de décor assez haut pour masquer une partie de la vue.",
                "blocks_movement": True,
                "opaque": True,
                "asset_key": "prop/shelf_large",
            },
        )


def _add_poi_elements(
    by_id: dict[str, dict[str, Any]],
    layout: dict[str, Any],
    cols: int,
    rows: int,
) -> None:
    for poi in layout.get("pois", []):
        if not isinstance(poi, dict):
            continue
        pos = poi.get("position")
        if not isinstance(pos, dict):
            continue
        kind = str(poi.get("kind") or "").lower()
        if kind not in {"cover", "hazard", "loot", "clue", "light"}:
            continue
        element_id = _clean_text(poi.get("element_id"), max_len=80)
        if not element_id or element_id not in by_id:
            element_id = f"element_{poi.get('id')}"
            poi["element_id"] = element_id
        element_kind = {
            "cover": "cover",
            "hazard": "hazard",
            "light": "light",
            "loot": "furniture",
            "clue": "decor",
        }.get(kind, "decor")
        by_id.setdefault(
            element_id,
            {
                "id": element_id,
                "name": poi.get("name") or poi.get("id") or "Repère",
                "kind": element_kind,
                "geometry": {
                    "type": "ellipse" if element_kind in {"hazard", "light"} else "rect",
                    **(
                        {
                            "col": float(pos.get("col", 0)) + 0.5,
                            "row": float(pos.get("row", 0)) + 0.5,
                            "radius_col": 0.45,
                            "radius_row": 0.45,
                        }
                        if element_kind in {"hazard", "light"}
                        else {
                            "col": float(pos.get("col", 0)) + 0.15,
                            "row": float(pos.get("row", 0)) + 0.15,
                            "width": 0.7,
                            "height": 0.7,
                        }
                    ),
                },
                "description": poi.get("description") or "",
                "blocks_movement": element_kind in {"cover", "furniture"},
                "opaque": element_kind in {"cover", "furniture"},
                "interactive": True,
                **_default_asset_for_poi_element(poi, element_kind),
            },
        )


def _default_asset_for_poi_element(poi: dict[str, Any], element_kind: str) -> dict[str, str]:
    explicit = normalize_asset_key(poi.get("asset_key"))
    if explicit:
        return {"asset_key": explicit}
    corpus = " ".join(
        str(poi.get(key) or "") for key in ("name", "description", "action_hint", "icon")
    ).casefold()
    if element_kind == "light":
        if any(word in corpus for word in ("murale", "applique", "wall", "mounted")):
            return {"asset_key": "prop/torch_mounted"}
        return {"asset_key": "prop/torch_lit"}
    if element_kind == "furniture":
        if any(word in corpus for word in ("or", "doré", "dore", "trésor", "tresor")):
            return {"asset_key": "prop/chest_gold"}
        return {"asset_key": "prop/chest"}
    if element_kind == "cover":
        if any(word in corpus for word in ("pilier", "colonne", "pillar")):
            return {"asset_key": "prop/pillar"}
        if any(word in corpus for word in ("gravat", "débris", "debris", "éboulis", "eboulis")):
            return {"asset_key": "prop/rubble_large"}
        if any(word in corpus for word in ("tonneau", "baril", "barrel")):
            return {"asset_key": "prop/barrel_large"}
        return {"asset_key": "prop/crates_stacked"}
    return {}


def _normalize_exits(
    layout: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    cols: int,
    rows: int,
) -> None:
    for exit_ in layout.get("exits", []):
        if not isinstance(exit_, dict):
            continue
        pos = exit_.get("position")
        if not isinstance(pos, dict):
            continue

        placement = _infer_exit_placement(exit_, by_id, cols, rows)
        exit_["placement"] = placement
        if placement == "embedded":
            _ensure_embedded_exit_element(by_id, exit_, cols, rows)
        else:
            exit_["position"] = _edge_exit_position(pos, _exit_corpus(exit_), cols, rows)


def _infer_exit_placement(
    exit_: dict[str, Any],
    by_id: dict[str, dict[str, Any]],
    cols: int,
    rows: int,
) -> str:
    explicit = _clean_text(exit_.get("placement"), max_len=24).lower()
    if explicit in EXIT_PLACEMENTS:
        return explicit

    pos = exit_.get("position")
    if isinstance(pos, dict) and _is_border_position(pos, cols, rows):
        return "edge"

    element_id = _clean_text(exit_.get("element_id"), max_len=80)
    element = by_id.get(element_id)
    if isinstance(element, dict) and element.get("kind") in {"door", "stairs"}:
        return "embedded"

    corpus = _exit_corpus(exit_)
    if any(word in corpus for word in _EMBEDDED_EXIT_WORDS):
        return "embedded"
    return "edge"


def _ensure_embedded_exit_element(
    by_id: dict[str, dict[str, Any]],
    exit_: dict[str, Any],
    cols: int,
    rows: int,
) -> None:
    pos = exit_.get("position")
    if not isinstance(pos, dict):
        return
    element_id = _clean_text(exit_.get("element_id"), max_len=80)
    if element_id and element_id in by_id:
        return

    corpus = _exit_corpus(exit_)
    if not element_id:
        suffix = "stairs" if _exit_access_kind(corpus) == "stairs" else "door"
        element_id = f"element_{exit_.get('id')}_{suffix}"
        exit_["element_id"] = element_id

    kind = _exit_access_kind(corpus)
    by_id.setdefault(
        element_id,
        {
            "id": element_id,
            "name": exit_.get("label") or "Accès",
            "kind": kind,
            "geometry": _embedded_exit_geometry(pos, cols, rows),
            "description": exit_.get("description") or exit_.get("leads_to") or "",
            "blocks_movement": False,
            "opaque": False,
            "interactive": True,
            "asset_key": "prop/stairs" if kind == "stairs" else "prop/door",
            **_access_orientation_fields(exit_, kind, cols, rows),
        },
    )


def _exit_access_kind(corpus: str) -> str:
    if any(word in corpus for word in _STAIRS_ACCESS_WORDS):
        return "stairs"
    return "door"


def _infer_vertical_direction(corpus: str) -> str:
    if any(word in corpus for word in _DOWN_ACCESS_WORDS):
        return "down"
    if any(word in corpus for word in _UP_ACCESS_WORDS):
        return "up"
    return "level"


def _infer_exit_facing(exit_: dict[str, Any], cols: int, rows: int) -> str | None:
    explicit = _clean_text(exit_.get("facing"), max_len=16).lower()
    if explicit in SCENE_ELEMENT_FACINGS:
        return explicit

    corpus = _exit_corpus(exit_)
    if any(word in corpus for word in ("ouest", "west", "gauche")):
        return "west"
    if any(word in corpus for word in ("est", "east", "droite")):
        return "east"
    if any(word in corpus for word in ("nord", "north", "haut")):
        return "north"
    if any(word in corpus for word in ("sud", "south", "bas")):
        return "south"

    pos = exit_.get("position")
    if not isinstance(pos, dict):
        return None
    col = _clamp_float(pos.get("col"), 0.0, float(cols - 1), 0.0)
    row = _clamp_float(pos.get("row"), 0.0, float(rows - 1), 0.0)
    distances = [
        (row, "north"),
        (cols - 1 - col, "east"),
        (rows - 1 - row, "south"),
        (col, "west"),
    ]
    distance, facing = min(distances, key=lambda item: item[0])
    return facing if distance <= 0.001 else None


def _access_geometry(
    exit_: dict[str, Any],
    kind: str,
    cols: int,
    rows: int,
) -> dict[str, Any]:
    pos = exit_.get("position")
    if not isinstance(pos, dict):
        pos = {}
    placement = _clean_text(exit_.get("placement"), max_len=24).lower()
    if placement == "edge" and _is_border_position(pos, cols, rows):
        return _edge_access_geometry(
            pos,
            kind,
            cols,
            rows,
            facing=_infer_exit_facing(exit_, cols, rows),
        )
    return _embedded_exit_geometry(pos, cols, rows)


def _edge_access_geometry(
    pos: dict[str, Any],
    kind: str,
    cols: int,
    rows: int,
    *,
    facing: str | None = None,
) -> dict[str, Any]:
    col = int(_clamp_float(pos.get("col"), 0.0, float(cols - 1), 0.0))
    row = int(_clamp_float(pos.get("row"), 0.0, float(rows - 1), 0.0))
    if kind == "stairs":
        if facing == "west" or (facing is None and col <= 0):
            return {"type": "rect", "col": 0.0, "row": float(row), "width": 1.0, "height": 1.0}
        if facing == "east" or (facing is None and col >= cols - 1):
            return {
                "type": "rect",
                "col": float(cols - 1),
                "row": float(row),
                "width": 1.0,
                "height": 1.0,
            }
        if facing == "north" or (facing is None and row <= 0):
            return {"type": "rect", "col": float(col), "row": 0.0, "width": 1.0, "height": 1.0}
        return {
            "type": "rect",
            "col": float(col),
            "row": float(rows - 1),
            "width": 1.0,
            "height": 1.0,
        }
    return _door_geometry(pos, cols, rows, facing=facing)


def _embedded_exit_geometry(pos: dict[str, Any], cols: int, rows: int) -> dict[str, Any]:
    col = _clamp_float(pos.get("col"), 0.0, float(cols - 1), 0.0)
    row = _clamp_float(pos.get("row"), 0.0, float(rows - 1), 0.0)
    return {
        "type": "rect",
        "col": round(max(0.0, min(float(cols) - 0.75, col + 0.125)), 3),
        "row": round(max(0.0, min(float(rows) - 0.75, row + 0.125)), 3),
        "width": 0.75,
        "height": 0.75,
    }


def _edge_exit_position(
    pos: dict[str, Any],
    corpus: str,
    cols: int,
    rows: int,
) -> dict[str, int]:
    col = int(_clamp_float(pos.get("col"), 0.0, float(cols - 1), cols - 1))
    row = int(_clamp_float(pos.get("row"), 0.0, float(rows - 1), rows // 2))
    if _is_border_position({"col": col, "row": row}, cols, rows):
        return {"col": col, "row": row}

    if any(word in corpus for word in ("ouest", "west", "gauche")):
        return {"col": 0, "row": row}
    if any(word in corpus for word in ("est", "east", "droite")):
        return {"col": cols - 1, "row": row}
    if any(word in corpus for word in ("nord", "north", "haut")):
        return {"col": col, "row": 0}
    if any(word in corpus for word in ("sud", "south", "bas")):
        return {"col": col, "row": rows - 1}

    distances = [
        (col, {"col": 0, "row": row}),
        (cols - 1 - col, {"col": cols - 1, "row": row}),
        (row, {"col": col, "row": 0}),
        (rows - 1 - row, {"col": col, "row": rows - 1}),
    ]
    return min(distances, key=lambda item: item[0])[1]


def _is_border_position(pos: dict[str, Any], cols: int, rows: int) -> bool:
    try:
        col = int(pos.get("col", -1))
        row = int(pos.get("row", -1))
    except (TypeError, ValueError):
        return False
    return col <= 0 or row <= 0 or col >= cols - 1 or row >= rows - 1


def _exit_corpus(exit_: dict[str, Any]) -> str:
    return " ".join(
        str(exit_.get(key) or "")
        for key in ("id", "label", "description", "leads_to", "kind", "type")
    ).casefold()


def _add_plaza_elements(
    by_id: dict[str, dict[str, Any]],
    layout: dict[str, Any],
    cols: int,
    rows: int,
) -> None:
    corpus = _layout_public_corpus(layout)
    by_id.setdefault(
        "pavage_place",
        {
            "id": "pavage_place",
            "name": "Pavés de la place",
            "kind": "terrain",
            "terrain_type": "plaza_paving",
            "geometry": {"type": "rect", "col": 0, "row": 0, "width": cols, "height": rows},
            "description": "Un sol pavé ouvert, sans route traversante dédiée.",
            "blocks_movement": False,
            "opaque": False,
        },
    )
    if any(word in corpus for word in ("marché", "marche", "étal", "etal", "festival")):
        by_id.setdefault(
            "etals_marche_ouest",
            {
                "id": "etals_marche_ouest",
                "name": "Étals du marché",
                "kind": "furniture",
                "geometry": {"type": "rect", "col": 2.0, "row": 5.6, "width": 1.6, "height": 0.7},
                "description": "Des tréteaux encombrés structurent la circulation.",
                "blocks_movement": True,
                "opaque": False,
            },
        )
        by_id.setdefault(
            "etals_marche_est",
            {
                "id": "etals_marche_est",
                "name": "Étal couvert",
                "kind": "furniture",
                "geometry": {
                    "type": "rect",
                    "col": max(4.0, cols - 3.6),
                    "row": 4.2,
                    "width": 1.5,
                    "height": 0.7,
                },
                "description": "Une table de marchand offre un couvert léger.",
                "blocks_movement": True,
                "opaque": False,
            },
        )
    if any(word in corpus for word in ("pavillon", "festival", "festivités", "festivites")):
        by_id.setdefault(
            "pavillon_festivites",
            {
                "id": "pavillon_festivites",
                "name": "Pavillon des festivités",
                "kind": "cover",
                "geometry": {
                    "type": "rect",
                    "col": max(1.0, cols - 4.2),
                    "row": 2.8,
                    "width": 2.2,
                    "height": 1.4,
                },
                "description": "Une estrade textile visible sert de repère et de couvert.",
                "blocks_movement": True,
                "opaque": False,
            },
        )
    if "fontaine" in corpus:
        by_id.setdefault(
            "fontaine_place",
            {
                "id": "fontaine_place",
                "name": "Fontaine",
                "kind": "cover",
                "geometry": {
                    "type": "ellipse",
                    "col": cols / 2,
                    "row": rows / 2,
                    "radius_col": 0.75,
                    "radius_row": 0.75,
                },
                "description": "Un bassin de pierre occupe la place.",
                "blocks_movement": True,
                "opaque": False,
            },
        )
    if any(word in corpus for word in ("foule", "festival", "liesse")):
        by_id.setdefault(
            "foule_place",
            {
                "id": "foule_place",
                "name": "Foule dense",
                "kind": "hazard",
                "geometry": {
                    "type": "ellipse",
                    "col": max(2.0, cols * 0.62),
                    "row": max(2.0, rows * 0.58),
                    "radius_col": 1.0,
                    "radius_row": 0.75,
                },
                "description": "Les passants rendent les mouvements brusques incertains.",
                "blocks_movement": False,
                "opaque": False,
            },
        )
    if _has_explicit_subterranean_access(corpus):
        by_id.setdefault(
            "grille_egout",
            {
                "id": "grille_egout",
                "name": "Grille d'égout",
                "kind": "stairs",
                "geometry": {
                    "type": "rect",
                    "col": max(1.0, cols * 0.62),
                    "row": max(1.0, rows * 0.72),
                    "width": 0.8,
                    "height": 0.8,
                },
                "description": "Une ouverture métallique suggère un accès sous la ville.",
                "blocks_movement": False,
                "opaque": False,
                "interactive": True,
            },
        )


def _has_explicit_subterranean_access(corpus: str) -> bool:
    if any(word in corpus for word in _EXPLICIT_SUBTERRANEAN_ACCESS_WORDS):
        return True
    return bool(
        re.search(
            r"(acc[eè]s|entrée|entree|ouverture).{0,32}"
            r"(souterrain|sous-sol|sous la ville|égout|egout)",
            corpus,
        )
    )


def _strip_unrevealed_subterranean_access(
    by_id: dict[str, dict[str, Any]],
    layout: dict[str, Any],
) -> None:
    element = by_id.get("grille_egout")
    if not isinstance(element, dict):
        return
    if element.get("discovered") is True or element.get("visibility") == "visible":
        return
    if _is_element_linked(layout, "grille_egout"):
        return
    if _has_explicit_subterranean_access(_layout_public_corpus(layout)):
        return
    by_id.pop("grille_egout", None)


def _carve_wall_openings(by_id: dict[str, dict[str, Any]]) -> None:
    openings = [
        element
        for element in by_id.values()
        if element.get("kind") in {"door", "window", "stairs"}
        and isinstance(element.get("geometry"), dict)
        and element["geometry"].get("type") == "rect"
    ]
    if not openings:
        return

    replacements: dict[str, dict[str, Any]] = {}
    removed: list[str] = []
    for wall_id, wall in list(by_id.items()):
        if wall.get("kind") != "wall":
            continue
        geometry = wall.get("geometry")
        if not isinstance(geometry, dict) or geometry.get("type") != "line":
            continue
        segments = _wall_segments_after_openings(geometry, openings)
        if segments is None:
            continue

        removed.append(wall_id)
        for idx, segment_geometry in enumerate(segments):
            segment_id = (
                wall_id if idx == 0 else _unique_wall_segment_id(by_id, replacements, wall_id, idx)
            )
            segment = dict(wall)
            segment["id"] = segment_id
            if idx > 0:
                segment["name"] = f"{wall.get('name') or 'Mur'} {idx + 1}"
            segment["geometry"] = segment_geometry
            replacements[segment_id] = segment

    for wall_id in removed:
        by_id.pop(wall_id, None)
    by_id.update(replacements)


def _unique_wall_segment_id(
    by_id: dict[str, dict[str, Any]],
    replacements: dict[str, dict[str, Any]],
    base_id: str,
    idx: int,
) -> str:
    candidate = f"{base_id}_seg_{idx + 1}"
    suffix = idx + 1
    while candidate in by_id or candidate in replacements:
        suffix += 1
        candidate = f"{base_id}_seg_{suffix}"
    return candidate


def _wall_segments_after_openings(
    wall_geometry: dict[str, Any],
    openings: list[dict[str, Any]],
) -> list[dict[str, Any]] | None:
    start = wall_geometry.get("from")
    end = wall_geometry.get("to")
    if not isinstance(start, dict) or not isinstance(end, dict):
        return None

    start_col = _parse_optional_float(start.get("col"))
    start_row = _parse_optional_float(start.get("row"))
    end_col = _parse_optional_float(end.get("col"))
    end_row = _parse_optional_float(end.get("row"))
    if start_col is None or start_row is None or end_col is None or end_row is None:
        return None

    epsilon = 0.001
    horizontal = abs(start_row - end_row) <= epsilon
    vertical = abs(start_col - end_col) <= epsilon
    if not horizontal and not vertical:
        return None

    fixed = start_row if horizontal else start_col
    wall_min = min(start_col, end_col) if horizontal else min(start_row, end_row)
    wall_max = max(start_col, end_col) if horizontal else max(start_row, end_row)
    spans: list[tuple[float, float]] = []
    for opening in openings:
        span = _opening_span_on_wall(opening, horizontal=horizontal, fixed=fixed)
        if span is None:
            continue
        span_start = max(wall_min, span[0])
        span_end = min(wall_max, span[1])
        if span_end - span_start > 0.05:
            spans.append((span_start, span_end))
    if not spans:
        return None

    segments: list[tuple[float, float]] = []
    cursor = wall_min
    for span_start, span_end in _merge_opening_spans(spans):
        if span_start - cursor > 0.05:
            segments.append((cursor, span_start))
        cursor = max(cursor, span_end)
    if wall_max - cursor > 0.05:
        segments.append((cursor, wall_max))

    if horizontal:
        forward = start_col <= end_col
        return [
            _line_geometry(
                a if forward else b,
                fixed,
                b if forward else a,
                fixed,
            )
            for a, b in segments
        ]

    forward = start_row <= end_row
    return [
        _line_geometry(
            fixed,
            a if forward else b,
            fixed,
            b if forward else a,
        )
        for a, b in segments
    ]


def _opening_span_on_wall(
    opening: dict[str, Any],
    *,
    horizontal: bool,
    fixed: float,
) -> tuple[float, float] | None:
    geometry = opening.get("geometry")
    if not isinstance(geometry, dict) or geometry.get("type") != "rect":
        return None
    col = _parse_optional_float(geometry.get("col"))
    row = _parse_optional_float(geometry.get("row"))
    width = _parse_optional_float(geometry.get("width"))
    height = _parse_optional_float(geometry.get("height"))
    if col is None or row is None or width is None or height is None:
        return None
    if horizontal:
        if not (row - 0.001 <= fixed <= row + height + 0.001):
            return None
        return (col, col + width)
    if not (col - 0.001 <= fixed <= col + width + 0.001):
        return None
    return (row, row + height)


def _merge_opening_spans(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start, end in sorted(spans):
        if not merged or start > merged[-1][1] + 0.001:
            merged.append((start, end))
        else:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
    return merged


def _line_geometry(
    from_col: float, from_row: float, to_col: float, to_row: float
) -> dict[str, Any]:
    return {
        "type": "line",
        "from": {"col": round(from_col, 3), "row": round(from_row, 3)},
        "to": {"col": round(to_col, 3), "row": round(to_row, 3)},
    }


def _is_element_linked(layout: dict[str, Any], element_id: str) -> bool:
    for collection_name in ("pois", "exits"):
        for item in layout.get(collection_name, []) or []:
            if isinstance(item, dict) and item.get("element_id") == element_id:
                return True
    return False


def _door_geometry(
    pos: dict[str, Any],
    cols: int,
    rows: int,
    *,
    facing: str | None = None,
) -> dict[str, Any]:
    col = int(_clamp_float(pos.get("col"), 0.0, float(cols - 1), 0.0))
    row = int(_clamp_float(pos.get("row"), 0.0, float(rows - 1), 0.0))
    if facing == "west" or (facing is None and col <= 0):
        return {
            "type": "rect",
            "col": 0.0,
            "row": float(row),
            "width": 0.24,
            "height": 1.0,
        }
    if facing == "east" or (facing is None and col >= cols - 1):
        return {
            "type": "rect",
            "col": cols - 0.24,
            "row": float(row),
            "width": 0.24,
            "height": 1.0,
        }
    if facing == "north" or (facing is None and row <= 0):
        return {
            "type": "rect",
            "col": float(col),
            "row": 0.0,
            "width": 1.0,
            "height": 0.24,
        }
    if facing == "south" or (facing is None and row >= rows - 1):
        return {
            "type": "rect",
            "col": float(col),
            "row": rows - 0.24,
            "width": 1.0,
            "height": 0.24,
        }
    return {"type": "rect", "col": col + 0.15, "row": row + 0.15, "width": 0.7, "height": 0.7}


def _is_interior_scene(layout: dict[str, Any]) -> bool:
    corpus = " ".join(
        str(part or "")
        for part in (
            layout.get("scene_theme"),
            layout.get("terrain"),
            layout.get("description"),
            *[poi.get("name") for poi in layout.get("pois", []) if isinstance(poi, dict)],
        )
    ).casefold()
    normalized = re.sub(r"[^a-z0-9àâçéèêëîïôûùüÿñæœ -]+", " ", corpus)
    return any(word in normalized for word in _INTERIOR_WORDS) or layout.get("scene_theme") in {
        "dungeon",
        "cave",
    }


def _apply_element_3d_defaults(element: dict[str, Any], *, interior: bool) -> None:
    """Guarantee concrete ``height_m``/``elevation_m`` on one element (3D hints)."""
    kind = str(element.get("kind") or "")
    facing = _clean_text(element.get("facing"), max_len=16).lower()
    if facing in SCENE_ELEMENT_FACINGS:
        element["facing"] = facing
    else:
        element.pop("facing", None)
    vertical_direction = _clean_text(element.get("vertical_direction"), max_len=16).lower()
    if vertical_direction in SCENE_ELEMENT_VERTICAL_DIRECTIONS:
        element["vertical_direction"] = vertical_direction
    elif kind == "stairs":
        element["vertical_direction"] = _infer_vertical_direction(_element_corpus(element))
    else:
        element.pop("vertical_direction", None)
    height_m = _parse_optional_float(element.get("height_m"))
    if height_m is not None:
        element["height_m"] = round(
            max(_ELEMENT_HEIGHT_MIN_M, min(height_m, _ELEMENT_HEIGHT_MAX_M)), 3
        )
    elif kind == "wall" and not interior:
        element["height_m"] = _EXTERIOR_WALL_HEIGHT_M
    else:
        element["height_m"] = ELEMENT_DEFAULT_HEIGHTS_M.get(kind, _DEFAULT_ELEMENT_HEIGHT_M)
    elevation_m = _parse_optional_float(element.get("elevation_m"))
    if elevation_m is not None:
        element["elevation_m"] = round(
            max(_ELEMENT_ELEVATION_MIN_M, min(elevation_m, _ELEMENT_ELEVATION_MAX_M)), 3
        )
    else:
        element["elevation_m"] = 0.0


def _element_corpus(element: dict[str, Any]) -> str:
    return " ".join(
        str(element.get(key) or "")
        for key in ("id", "name", "description", "kind", "state", "physical_state")
    ).casefold()


def _apply_scene_3d_defaults(layout: dict[str, Any], *, time_of_day: str | None) -> None:
    """Guarantee concrete ``vegetation_density`` and ``ambiance`` on the layout."""
    theme = str(layout.get("scene_theme") or "").strip().lower()

    vegetation = _parse_optional_float(layout.get("vegetation_density"))
    if vegetation is None:
        vegetation = _THEME_VEGETATION_DENSITY.get(theme, _DEFAULT_VEGETATION_DENSITY)
    layout["vegetation_density"] = round(max(0.0, min(vegetation, 1.0)), 3)

    raw_ambiance = layout.get("ambiance")
    raw_ambiance = raw_ambiance if isinstance(raw_ambiance, dict) else {}
    light = str(raw_ambiance.get("light") or "").strip().lower()
    if light not in SCENE_AMBIANCE_LIGHTS:
        light = _default_ambiance_light(theme, time_of_day)
    fog = _parse_optional_float(raw_ambiance.get("fog_density"))
    if fog is None:
        fog = _THEME_FOG_DENSITY.get(theme, _DEFAULT_FOG_DENSITY)
    layout["ambiance"] = {"light": light, "fog_density": round(max(0.0, min(fog, 1.0)), 3)}


def _default_ambiance_light(theme: str, time_of_day: str | None) -> str:
    if theme in {"dungeon", "cave"}:
        return "torchlit"
    moment = str(time_of_day or "").strip().lower()
    if any(word in moment for word in _NIGHT_TIME_WORDS):
        return "night"
    if any(word in moment for word in _DUSK_TIME_WORDS):
        return "dusk"
    return "day"


def _is_plaza_scene(layout: dict[str, Any]) -> bool:
    corpus = _layout_corpus(layout)
    return any(word in corpus for word in _PLAZA_WORDS)


def _has_explicit_local_road(scene: dict[str, Any]) -> bool:
    for element in scene.get("elements", []) or []:
        if not isinstance(element, dict):
            continue
        if element.get("kind") == "terrain" and element.get("terrain_type") in {
            "road",
            "street",
            "path",
        }:
            return True
    return any(
        word in _layout_corpus(scene) for word in _LOCAL_ROAD_CONTEXT_WORDS
    ) and not _is_plaza_scene(scene)


def _layout_corpus(layout: dict[str, Any]) -> str:
    parts = _layout_public_corpus_parts(layout)
    for element in layout.get("elements", []) or []:
        if isinstance(element, dict):
            parts.extend(
                [
                    element.get("name"),
                    element.get("description"),
                    element.get("terrain_type"),
                ]
            )
    return " ".join(str(part or "") for part in parts).casefold()


def _layout_public_corpus(layout: dict[str, Any]) -> str:
    return " ".join(str(part or "") for part in _layout_public_corpus_parts(layout)).casefold()


def _layout_public_corpus_parts(layout: dict[str, Any]) -> list[Any]:
    parts: list[Any] = [
        layout.get("scene_theme"),
        layout.get("terrain"),
        layout.get("description"),
    ]
    for poi in layout.get("pois", []) or []:
        if isinstance(poi, dict):
            parts.extend([poi.get("name"), poi.get("description"), poi.get("action_hint")])
    for exit_ in layout.get("exits", []) or []:
        if isinstance(exit_, dict):
            parts.extend([exit_.get("label"), exit_.get("description"), exit_.get("leads_to")])
    return parts


def _element_prompt_bit(element: dict[str, Any]) -> str:
    kind = element.get("kind")
    terrain_type = element.get("terrain_type")
    name = element.get("name")
    if kind == "terrain" and terrain_type:
        return f"{kind}:{terrain_type}:{name}"
    return f"{kind}:{name}"


def _interior_allows_windows(layout: dict[str, Any]) -> bool:
    corpus = " ".join(
        str(part or "")
        for part in (layout.get("scene_theme"), layout.get("terrain"), layout.get("description"))
    ).casefold()
    if any(word in corpus for word in ("donjon", "dungeon", "crypte", "crypt", "cave", "grotte")):
        return False
    return True


def _geometry_point(
    raw: Any,
    cols: int,
    rows: int,
    *,
    allow_border: bool,
) -> dict[str, float] | None:
    if not isinstance(raw, dict):
        return None
    max_col = float(cols if allow_border else cols - 1)
    max_row = float(rows if allow_border else rows - 1)
    return {
        "col": round(_clamp_float(raw.get("col", raw.get("x")), 0.0, max_col, 0.0), 3),
        "row": round(_clamp_float(raw.get("row", raw.get("y")), 0.0, max_row, 0.0), 3),
    }


def _clamp_float(value: Any, minimum: float, maximum: float, default: float) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))


def _parse_optional_float(value: Any) -> float | None:
    """Parse a float-ish value; ``None`` when absent or invalid (bools rejected)."""
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _clean_text(value: Any, *, max_len: int) -> str:
    if value is None:
        return ""
    text = " ".join(str(value).split())
    return text[:max_len]


def _prompt_hash(prompt: str) -> str:
    return hashlib.sha1(prompt.encode("utf-8")).hexdigest()[:16]


def _positions(cells: Iterable[dict[str, int]]) -> list[dict[str, int]]:
    seen: set[tuple[int, int]] = set()
    result: list[dict[str, int]] = []
    for cell in cells:
        key = (int(cell.get("col", 0)), int(cell.get("row", 0)))
        if key in seen:
            continue
        seen.add(key)
        result.append({"col": key[0], "row": key[1]})
    return result
