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
        "prompt_hash": _clean_text(raw.get("prompt_hash"), max_len=64)
        or _prompt_hash(prompt),
    }
    for key, max_len in (("url", 1000), ("generated_at", 80), ("error", 280)):
        value = _clean_text(raw.get(key), max_len=max_len)
        if value:
            asset[key] = value
    return asset


def enrich_scene_layout(layout: dict[str, Any]) -> dict[str, Any]:
    """Add deterministic local-map elements where the GM supplied only POIs/exits."""
    cols = int(layout.get("cols") or 12)
    rows = int(layout.get("rows") or 12)
    elements = [
        element
        for element in layout.get("elements", [])
        if isinstance(element, dict) and element.get("id")
    ]
    by_id = {str(element["id"]): element for element in elements}

    interior = _is_interior_scene(layout)
    if interior:
        _add_boundary_walls(by_id, cols, rows)
        _add_exit_doors(by_id, layout, cols, rows)
        _add_windows(by_id, layout, cols, rows)
        _add_default_furniture(by_id, layout, cols, rows)

    _add_poi_elements(by_id, layout, cols, rows)
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
        f"{element.get('kind')}:{element.get('name')}"
        for element in scene.get("elements", [])[:24]
        if isinstance(element, dict)
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
