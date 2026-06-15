"""Primitives géométriques pures partagées par les builders de scène.

Aucune I/O. Utilisé par ``dungeon_generator`` et ``scene_builder`` pour
construire les ``elements`` d'une scène (cf. schéma canonique dans
``_normalize_scene_layout``).
"""

from __future__ import annotations

import hashlib
from typing import Any


def seed_int(seed: str) -> int:
    """Hash déterministe d'une seed textuelle vers un entier."""
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest()[:8], 16)


def rect(col: float, row: float, width: float, height: float) -> dict[str, Any]:
    """Géométrie rectangulaire en coordonnées de grille."""
    return {"type": "rect", "col": col, "row": row, "width": width, "height": height}


def ellipse(col: float, row: float, radius_col: float, radius_row: float) -> dict[str, Any]:
    """Géométrie elliptique en coordonnées de grille."""
    return {
        "type": "ellipse",
        "col": col,
        "row": row,
        "radius_col": radius_col,
        "radius_row": radius_row,
    }


def asset_element(
    element_id: str,
    name: str,
    kind: str,
    geometry: dict[str, Any],
    asset_key: str,
    *,
    blocks_movement: bool = True,
    opaque: bool = True,
    interactive: bool = False,
    facing: str | None = None,
    vertical_direction: str | None = None,
) -> dict[str, Any]:
    """Construit un ``element`` de scène avec asset 3D optionnel."""
    element: dict[str, Any] = {
        "id": element_id,
        "name": name,
        "kind": kind,
        "geometry": geometry,
        "blocks_movement": blocks_movement,
        "opaque": opaque,
        "interactive": interactive,
    }
    if asset_key:
        element["asset_key"] = asset_key
    if facing:
        element["facing"] = facing
    if vertical_direction:
        element["vertical_direction"] = vertical_direction
    return element
