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

# Défauts 3D optionnels — mêmes valeurs que le fallback client
# (frontend/src/engine3d/adapters/sceneAdapter.ts) pour rester cohérent.
ELEMENT_DEFAULT_HEIGHTS_M: dict[str, float] = {
    "wall": 2.5,
    "door": 2.2,
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
        _add_exit_doors(by_id, layout, cols, rows)
        _add_windows(by_id, layout, cols, rows)
        _add_default_furniture(by_id, layout, cols, rows)
    elif _is_plaza_scene(layout):
        _add_plaza_elements(by_id, layout, cols, rows)

    _add_poi_elements(by_id, layout, cols, rows)
    _strip_unrevealed_subterranean_access(by_id, layout)
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
            },
        )


def _add_exit_doors(
    by_id: dict[str, dict[str, Any]],
    layout: dict[str, Any],
    cols: int,
    rows: int,
) -> None:
    for exit_ in layout.get("exits", []):
        if not isinstance(exit_, dict):
            continue
        pos = exit_.get("position")
        if not isinstance(pos, dict):
            continue
        element_id = _clean_text(exit_.get("element_id"), max_len=80)
        if not element_id or element_id not in by_id:
            element_id = f"element_{exit_.get('id')}_door"
            exit_["element_id"] = element_id
        by_id.setdefault(
            element_id,
            {
                "id": element_id,
                "name": exit_.get("label") or "Porte",
                "kind": "door",
                "geometry": _door_geometry(pos, cols, rows),
                "description": exit_.get("description") or exit_.get("leads_to") or "",
                "blocks_movement": False,
                "opaque": False,
                "interactive": True,
            },
        )


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
            },
        )


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
        },
    )


def _exit_access_kind(corpus: str) -> str:
    if any(
        word in corpus
        for word in ("trappe", "égout", "egout", "échelle", "echelle", "escalier", "puits", "cave")
    ):
        return "stairs"
    return "door"


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


def _is_element_linked(layout: dict[str, Any], element_id: str) -> bool:
    for collection_name in ("pois", "exits"):
        for item in layout.get(collection_name, []) or []:
            if isinstance(item, dict) and item.get("element_id") == element_id:
                return True
    return False


def _door_geometry(pos: dict[str, Any], cols: int, rows: int) -> dict[str, Any]:
    col = int(pos.get("col", 0))
    row = int(pos.get("row", 0))
    if col <= 0:
        return {
            "type": "rect",
            "col": 0.0,
            "row": max(0.0, row + 0.1),
            "width": 0.22,
            "height": 0.8,
        }
    if col >= cols - 1:
        return {
            "type": "rect",
            "col": cols - 0.22,
            "row": max(0.0, row + 0.1),
            "width": 0.22,
            "height": 0.8,
        }
    if row <= 0:
        return {
            "type": "rect",
            "col": max(0.0, col + 0.1),
            "row": 0.0,
            "width": 0.8,
            "height": 0.22,
        }
    if row >= rows - 1:
        return {
            "type": "rect",
            "col": max(0.0, col + 0.1),
            "row": rows - 0.22,
            "width": 0.8,
            "height": 0.22,
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
