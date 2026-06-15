"""Layout et décor déterministes pour les cartes région/ville.

Pur : aucune I/O, aucun accès DB/réseau, aucun appel LLM. Complète les cartes
``RegionMap``/``CityMap`` (cf. ``app.schemas.map``) quand le MJ ne fournit que
des noms/types/liens :

- ``layout_region_nodes`` assigne une position x/y (0..100) aux nœuds qui
  n'en ont pas, via un placement radial déterministe.
- ``build_region_decor`` génère un ``MapDecor`` (forêts, montagnes, côte,
  rivière, routes décoratives) cohérent avec le biome.

Les plages de valeurs par biome reprennent celles des générateurs frontend
``frontend/src/composables/useMapDecor.ts`` (generateRegionDecor,
generateCoastalRegionDecor, generateDesertRegionDecor,
generateMountainRegionDecor, generateCityDecor) ; le PRNG diffère
(``random.Random`` seedé par chaîne, déterministe quel que soit
``PYTHONHASHSEED``) mais le résultat reste tout aussi reproductible.
"""

from __future__ import annotations

import math
import random
from typing import Any

_MIN_COORD = 6.0
_MAX_COORD = 94.0
_MIN_NODE_SEPARATION = 12.0
_MIN_DECOR_SEPARATION = 9.0


# ─── Placement des nœuds ──────────────────────────────────────────────────────


def layout_region_nodes(nodes: list[dict[str, Any]], *, seed: str) -> list[dict[str, Any]]:
    """Complète la position (``{"x","y"}``, 0..100) des nœuds qui n'en ont pas.

    Les nœuds qui ont déjà une position numérique ne sont jamais modifiés.
    Placement radial déterministe : si aucun nœud n'est positionné, le premier
    nœud sans position devient l'ancre au centre (50,50) ; les suivants sont
    disposés sur un anneau autour du centroïde des nœuds déjà placés, à un
    angle/rayon dérivés de ``seed`` + l'id du nœud, avec quelques tentatives de
    repli pour éviter un chevauchement grossier avec les nœuds déjà placés.
    """
    result = [dict(node) for node in nodes]
    placed: list[tuple[float, float]] = []
    pending: list[int] = []

    for index, entry in enumerate(result):
        position = _position_of(entry)
        if position is None:
            pending.append(index)
        else:
            placed.append(position)

    if not pending:
        return result

    if not placed:
        anchor_index = pending.pop(0)
        result[anchor_index]["position"] = {"x": 50.0, "y": 50.0}
        placed.append((50.0, 50.0))

    center_x = sum(p[0] for p in placed) / len(placed)
    center_y = sum(p[1] for p in placed) / len(placed)

    for index in pending:
        node_id = str(result[index].get("id") or index)
        rng = random.Random(f"{seed}:layout:{node_id}")
        angle = rng.uniform(0.0, 2 * math.pi)
        radius = rng.uniform(18.0, 38.0)
        x, y = _polar_offset(center_x, center_y, angle, radius)

        for _attempt in range(8):
            if all(math.hypot(x - px, y - py) >= _MIN_NODE_SEPARATION for px, py in placed):
                break
            angle += math.pi / 3
            radius += 6.0
            x, y = _polar_offset(center_x, center_y, angle, radius)

        position = (_clamp(x), _clamp(y))
        result[index]["position"] = {"x": position[0], "y": position[1]}
        placed.append(position)

    return result


def _position_of(node: dict[str, Any]) -> tuple[float, float] | None:
    position = node.get("position")
    if not isinstance(position, dict):
        return None
    x, y = position.get("x"), position.get("y")
    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
        return float(x), float(y)
    return None


def _polar_offset(cx: float, cy: float, angle: float, radius: float) -> tuple[float, float]:
    return cx + radius * math.cos(angle), cy + radius * math.sin(angle)


def _clamp(value: float, lo: float = _MIN_COORD, hi: float = _MAX_COORD) -> float:
    return round(max(lo, min(hi, value)), 1)


# ─── Décor ─────────────────────────────────────────────────────────────────────


def build_region_decor(nodes: list[dict[str, Any]], biome: str, *, seed: str) -> dict[str, Any]:
    """Décor ``MapDecor`` déterministe selon le biome (même forme que le frontend).

    ``biome`` est l'une des valeurs de ``app.services.biome.RegionBiome``
    (``"coastal"``/``"mountain"``/``"desert"``/``"default"``) pour une région,
    ou ``"city"`` pour une ville (décor périphérique, indépendant du biome —
    cf. ``generateCityDecor``). Toute autre valeur retombe sur le décor par
    défaut. ``nodes`` (positions déjà résolues) est utilisé pour éviter de
    placer des forêts/montagnes directement sur un nœud de la carte.
    """
    avoid = [pos for pos in (_position_of(node) for node in nodes) if pos is not None]
    if biome == "coastal":
        return _coastal_region_decor(seed, avoid)
    if biome == "desert":
        return _desert_region_decor(seed, avoid)
    if biome == "mountain":
        return _mountain_region_decor(seed, avoid)
    if biome == "city":
        return _city_decor(seed, avoid)
    return _default_region_decor(seed, avoid)


def _default_region_decor(seed: str, avoid: list[tuple[float, float]]) -> dict[str, Any]:
    rng = random.Random(f"{seed}:region")
    forests = [
        _forest_spot(
            rng, avoid, x_range=(5, 95), y_range=(5, 95), radius=(2.5, 4.5), opacity=(0.3, 0.5)
        )
        for _ in range(10 + rng.randrange(6))
    ]
    mountains = [
        _mountain_spot(rng, x_range=(60, 95), y_range=(5, 45), height=(4.0, 9.0))
        for _ in range(3 + rng.randrange(4))
    ]
    decor: dict[str, Any] = {
        "forests": forests,
        "mountains": mountains,
        "decorative_roads": _decorative_roads(rng, 2 + rng.randrange(2)),
    }
    if rng.random() > 0.6:
        decor["river"] = _river_path(rng)
    return decor


def _coastal_region_decor(seed: str, avoid: list[tuple[float, float]]) -> dict[str, Any]:
    rng = random.Random(f"{seed}:coastal")
    # Quelques forêts limitées, surtout à l'intérieur des terres (haut de carte).
    forests = [
        _forest_spot(
            rng, avoid, x_range=(5, 95), y_range=(5, 45), radius=(2.0, 4.0), opacity=(0.25, 0.45)
        )
        for _ in range(3 + rng.randrange(4))
    ]
    # Côté ouest/nord/est — pas "south" pour éviter le polygone mal orienté
    # de la version frontend (cf. _coastline_points).
    side = rng.choice(("west", "north", "east"))
    coastline = {"side": side, "points": _coastline_points(side, rng)}
    return {
        "forests": forests,
        "coastline": coastline,
        "decorative_roads": _decorative_roads(rng, 1 + rng.randrange(2)),
    }


def _desert_region_decor(seed: str, avoid: list[tuple[float, float]]) -> dict[str, Any]:
    rng = random.Random(f"{seed}:desert")
    # "Forêts" = touffes de végétation désertique, très petites et discrètes.
    forests = [
        _forest_spot(
            rng, avoid, x_range=(5, 95), y_range=(5, 95), radius=(1.2, 2.7), opacity=(0.15, 0.27)
        )
        for _ in range(4 + rng.randrange(4))
    ]
    return {
        "forests": forests,
        "decorative_roads": _decorative_roads(rng, 1 + rng.randrange(2)),
    }


def _mountain_region_decor(seed: str, avoid: list[tuple[float, float]]) -> dict[str, Any]:
    rng = random.Random(f"{seed}:mountain")
    # Forêts dans les vallées (bas de carte).
    forests = [
        _forest_spot(
            rng, avoid, x_range=(5, 95), y_range=(50, 95), radius=(2.5, 4.5), opacity=(0.30, 0.45)
        )
        for _ in range(4 + rng.randrange(5))
    ]
    # Beaucoup de montagnes, sur toute la moitié supérieure.
    mountains = [
        _mountain_spot(rng, x_range=(5, 95), y_range=(5, 60), height=(5.0, 12.0))
        for _ in range(7 + rng.randrange(5))
    ]
    return {
        "forests": forests,
        "mountains": mountains,
        "decorative_roads": _decorative_roads(rng, 2 + rng.randrange(2)),
    }


def _city_decor(seed: str, avoid: list[tuple[float, float]]) -> dict[str, Any]:
    rng = random.Random(f"{seed}:city")
    forests = []
    for _ in range(6 + rng.randrange(6)):
        on_vertical = rng.random() > 0.5
        if on_vertical:
            x = rng.uniform(0, 15) if rng.random() > 0.5 else rng.uniform(85, 100)
            y = rng.uniform(5, 95)
        else:
            x = rng.uniform(5, 95)
            y = rng.uniform(0, 15) if rng.random() > 0.5 else rng.uniform(85, 100)
        forests.append(_avoiding(rng, avoid, x, y, radius=(2.0, 4.5), opacity=(0.35, 0.5)))

    decor: dict[str, Any] = {
        "forests": forests,
        "decorative_roads": _decorative_roads(rng, 2 + rng.randrange(2)),
    }
    if rng.random() > 0.65:
        decor["river"] = _river_path(rng)
    return decor


# ─── Helpers internes ─────────────────────────────────────────────────────────


def _forest_spot(
    rng: random.Random,
    avoid: list[tuple[float, float]],
    *,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    radius: tuple[float, float],
    opacity: tuple[float, float],
) -> dict[str, float]:
    x, y = _scatter_point(rng, avoid, x_range=x_range, y_range=y_range)
    return _decor_circle(x, y, rng.uniform(*radius), rng.uniform(*opacity))


def _avoiding(
    rng: random.Random,
    avoid: list[tuple[float, float]],
    x: float,
    y: float,
    *,
    radius: tuple[float, float],
    opacity: tuple[float, float],
) -> dict[str, float]:
    for _attempt in range(4):
        if all(math.hypot(x - ax, y - ay) >= _MIN_DECOR_SEPARATION for ax, ay in avoid):
            break
        x = max(0.0, min(100.0, x + rng.uniform(-8, 8)))
        y = max(0.0, min(100.0, y + rng.uniform(-8, 8)))
    return _decor_circle(x, y, rng.uniform(*radius), rng.uniform(*opacity))


def _decor_circle(x: float, y: float, radius: float, opacity: float) -> dict[str, float]:
    return {
        "x": round(max(0.0, min(100.0, x)), 1),
        "y": round(max(0.0, min(100.0, y)), 1),
        "radius": round(radius, 1),
        "opacity": round(opacity, 2),
    }


def _scatter_point(
    rng: random.Random,
    avoid: list[tuple[float, float]],
    *,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
) -> tuple[float, float]:
    x, y = rng.uniform(*x_range), rng.uniform(*y_range)
    for _attempt in range(6):
        if all(math.hypot(x - ax, y - ay) >= _MIN_DECOR_SEPARATION for ax, ay in avoid):
            break
        x, y = rng.uniform(*x_range), rng.uniform(*y_range)
    return x, y


def _mountain_spot(
    rng: random.Random,
    *,
    x_range: tuple[float, float],
    y_range: tuple[float, float],
    height: tuple[float, float],
) -> dict[str, float]:
    return {
        "x": round(rng.uniform(*x_range), 1),
        "y": round(rng.uniform(*y_range), 1),
        "height": round(rng.uniform(*height), 1),
    }


def _decorative_roads(rng: random.Random, count: int) -> list[str]:
    return [_road_path(rng) for _ in range(count)]


def _road_path(rng: random.Random) -> str:
    start_x = 0.0 if rng.random() > 0.5 else rng.uniform(0, 30)
    start_y = rng.uniform(0, 100)
    end_x = 100.0 if rng.random() > 0.5 else rng.uniform(70, 100)
    end_y = rng.uniform(0, 100)
    mid_x = rng.uniform(30, 70)
    mid_y = (start_y + end_y) / 2 + rng.uniform(-10, 10)
    return f"M {start_x:.0f} {start_y:.0f} Q {mid_x:.0f} {mid_y:.0f} {end_x:.0f} {end_y:.0f}"


def _river_path(rng: random.Random) -> dict[str, Any]:
    y1 = 30 + rng.uniform(0, 40)
    y2 = y1 + rng.uniform(-10, 10)
    y3 = y1 + rng.uniform(-7.5, 7.5)
    qx = 20 + rng.uniform(0, 20)
    tx = 50 + rng.uniform(0, 10)
    path = f"M 0 {y1:.0f} Q {qx:.0f} {y2:.0f} {tx:.0f} {(y1 + y2) / 2:.0f} T 100 {y3:.0f}"
    return {"path": path, "width": round(1.2 + rng.uniform(0, 1), 2)}


def _coastline_points(side: str, rng: random.Random) -> list[dict[str, float]]:
    if side == "west":
        indent = 8 + rng.uniform(0, 12)
        return [
            {"x": 0.0, "y": 0.0},
            {"x": round(indent, 1), "y": 0.0},
            {"x": round(indent - rng.uniform(0, 6), 1), "y": 30.0},
            {"x": round(indent + rng.uniform(0, 4), 1), "y": 60.0},
            {"x": round(indent, 1), "y": 100.0},
            {"x": 0.0, "y": 100.0},
        ]
    if side == "east":
        indent = 88 - rng.uniform(0, 12)
        return [
            {"x": 100.0, "y": 0.0},
            {"x": round(indent, 1), "y": 0.0},
            {"x": round(indent + rng.uniform(0, 6), 1), "y": 30.0},
            {"x": round(indent - rng.uniform(0, 4), 1), "y": 60.0},
            {"x": round(indent, 1), "y": 100.0},
            {"x": 100.0, "y": 100.0},
        ]
    # north
    indent = 8 + rng.uniform(0, 12)
    return [
        {"x": 0.0, "y": 0.0},
        {"x": 0.0, "y": round(indent, 1)},
        {"x": 30.0, "y": round(indent - rng.uniform(0, 4), 1)},
        {"x": 70.0, "y": round(indent + rng.uniform(0, 4), 1)},
        {"x": 100.0, "y": round(indent, 1)},
        {"x": 100.0, "y": 0.0},
    ]
