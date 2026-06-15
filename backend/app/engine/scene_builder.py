"""Builder pur — transforme un ``SceneSpec`` en scène 12x12 déterministe.

Aucune I/O. ``build_scene`` ne fait que de la géométrie : aucune coordonnée
n'est demandée au LLM, tout est dérivé de ``SceneSpec`` + une seed textuelle.
La sortie respecte le schéma canonique attendu par
``GMResponseExecutor._normalize_scene_layout`` (cf. ``room_scene_skeleton``
pour la référence côté donjon).
"""

from __future__ import annotations

import itertools
import random
from typing import Any

from app.engine.scene_primitives import asset_element, ellipse, rect, seed_int
from app.engine.tactical_grid import GridPosition, nearest_free_cell
from app.engine.theme_packs import ThemePack, resolve_theme_pack
from app.schemas.scene_spec import (
    SCENE_FEATURE_ICONS,
    SceneExitSpec,
    SceneFeatureSpec,
    SceneSpec,
    SceneZone,
)

_COLS = 12
_ROWS = 12
_CELL_SIZE_M_BY_SIZE: dict[str, float] = {"small": 1.2, "medium": 1.5, "large": 2.0}

# Ordre de remplissage déterministe pour les features injectées (cover/hazard
# manquants, ou indices pour atteindre le minimum de 3 prises jouables).
_INJECTED_ZONES: tuple[SceneZone, ...] = ("ne", "sw", "se", "nw", "center")

# Position relative (0..1) du centre de chaque zone dans la grille.
_ZONE_BASE: dict[SceneZone, tuple[float, float]] = {
    "center": (0.5, 0.5),
    "north": (0.5, 0.15),
    "south": (0.5, 0.85),
    "east": (0.85, 0.5),
    "west": (0.15, 0.5),
    "ne": (0.85, 0.15),
    "nw": (0.15, 0.15),
    "se": (0.85, 0.85),
    "sw": (0.15, 0.85),
}


def build_scene(spec: SceneSpec, *, seed: str) -> dict[str, Any]:
    """Construit une scène canonique 12x12 à partir de ``spec`` et ``seed``.

    Déterministe : même ``spec`` + même ``seed`` ⇒ scène identique.
    """
    rng = random.Random(seed_int(seed))
    pack = resolve_theme_pack(spec.theme, spec.enclosure)

    occupied: set[tuple[int, int]] = set()
    exits: list[dict[str, Any]] = []
    for idx, exit_spec in enumerate(spec.exits):
        exit_data, position = _build_exit(exit_spec, idx, occupied, rng)
        occupied.add(position)
        exits.append(exit_data)

    pois: list[dict[str, Any]] = []
    elements: list[dict[str, Any]] = []
    for idx, feature in enumerate(_ensure_features(spec.features, len(exits), pack)):
        _place_feature(feature, idx, occupied, pack, rng, pois, elements)

    layout: dict[str, Any] = {
        "cols": _COLS,
        "rows": _ROWS,
        "cell_size_m": _CELL_SIZE_M_BY_SIZE.get(spec.size, 1.5),
        "terrain": _terrain_label(spec, pack),
        "scene_theme": spec.theme,
        "pois": pois,
        "exits": exits,
        "elements": elements,
        "party_positions": {},
        "ambiance": dict(pack.ambiance),
        "vegetation_density": 0.0 if spec.enclosure == "interior" else pack.vegetation_density,
    }
    if spec.description:
        layout["description"] = spec.description
    return layout


def _terrain_label(spec: SceneSpec, pack: ThemePack) -> str:
    if spec.enclosure == "interior" and spec.theme not in {"dungeon", "cave"}:
        return f"{pack.terrain} interieur"
    return pack.terrain


def _ensure_features(
    features: list[SceneFeatureSpec],
    exits_count: int,
    pack: ThemePack,
) -> list[SceneFeatureSpec]:
    """Garantit 2-4 features tactiques (cover/hazard) et >= 3 prises jouables."""
    result = list(features)
    zones = itertools.cycle(_INJECTED_ZONES)

    tactical = sum(1 for f in result if f.kind in ("cover", "hazard"))
    while tactical < 2:
        if tactical == 0:
            result.append(SceneFeatureSpec(kind="cover", name=pack.cover_label, zone=next(zones)))
        else:
            result.append(SceneFeatureSpec(kind="hazard", name=pack.hazard_label, zone=next(zones)))
        tactical += 1

    while len(result) + exits_count < 3:
        result.append(SceneFeatureSpec(kind="clue", name="Détail curieux", zone=next(zones)))

    return result


def _exit_base_position(direction: str, rng: random.Random) -> tuple[int, int]:
    jitter = rng.randint(-2, 2)
    if direction == "north":
        return (_clamp(_COLS // 2 + jitter, 1, _COLS - 2), 0)
    if direction == "south":
        return (_clamp(_COLS // 2 + jitter, 1, _COLS - 2), _ROWS - 1)
    if direction == "west":
        return (0, _clamp(_ROWS // 2 + jitter, 1, _ROWS - 2))
    return (_COLS - 1, _clamp(_ROWS // 2 + jitter, 1, _ROWS - 2))  # east


def _place_on_edge(
    direction: str,
    base_col: int,
    base_row: int,
    occupied: set[tuple[int, int]],
) -> tuple[int, int]:
    """Première cellule libre le long du bord visé, en partant de la base."""
    if direction in ("north", "south"):
        for offset in range(0, _COLS):
            for col in (base_col - offset, base_col + offset):
                if 1 <= col <= _COLS - 2 and (col, base_row) not in occupied:
                    return (col, base_row)
        return (base_col, base_row)
    for offset in range(0, _ROWS):
        for row in (base_row - offset, base_row + offset):
            if 1 <= row <= _ROWS - 2 and (base_col, row) not in occupied:
                return (base_col, row)
    return (base_col, base_row)


def _build_exit(
    spec: SceneExitSpec,
    idx: int,
    occupied: set[tuple[int, int]],
    rng: random.Random,
) -> tuple[dict[str, Any], tuple[int, int]]:
    base_col, base_row = _exit_base_position(spec.direction, rng)
    col, row = _place_on_edge(spec.direction, base_col, base_row, occupied)
    exit_data: dict[str, Any] = {
        "id": f"exit_{idx + 1}",
        "label": spec.label,
        "position": {"col": col, "row": row},
        "leads_to": spec.leads_to,
    }
    if spec.description:
        exit_data["description"] = spec.description
    if spec.embedded_element:
        exit_data["placement"] = "embedded"
        exit_data["element_id"] = spec.embedded_element
    return exit_data, (col, row)


def _zone_to_cell(zone: SceneZone, rng: random.Random) -> GridPosition:
    fx, fy = _ZONE_BASE[zone]
    col = _clamp(round(fx * (_COLS - 1)) + rng.randint(-1, 1), 1, _COLS - 2)
    row = _clamp(round(fy * (_ROWS - 1)) + rng.randint(-1, 1), 1, _ROWS - 2)
    return GridPosition(col=col, row=row)


def _pick_asset(assets: tuple[str, ...], rng: random.Random) -> str:
    return rng.choice(assets) if assets else ""


# Interactions par défaut injectées sur les POI générés (pas de coordonnées,
# juste label/intent/prompt) — enrichies ensuite par
# ``enrich_scene_poi_mechanics`` (jets de Investigation/Arcana/sauvegarde
# selon le kind et le texte du POI).
_DEFAULT_INTERACTIONS_BY_KIND: dict[str, tuple[dict[str, str], ...]] = {
    "cover": (
        {"label": "Examiner", "intent": "examine", "prompt": "J'examine {name}."},
        {
            "label": "Se mettre à couvert",
            "intent": "use",
            "prompt": "Je me mets à couvert derrière {name}.",
        },
    ),
    "hazard": (
        {"label": "Examiner", "intent": "examine", "prompt": "J'examine {name} avec prudence."},
    ),
    "clue": (
        {"label": "Examiner", "intent": "examine", "prompt": "J'examine {name} de plus près."},
    ),
    "loot": ({"label": "Fouiller", "intent": "search", "prompt": "Je fouille {name}."},),
    "enemy": ({"label": "Observer", "intent": "examine", "prompt": "J'observe {name}."},),
    "npc": (
        {
            "label": "Parler",
            "intent": "talk",
            "prompt": "Je m'approche de {name} et lui adresse la parole.",
        },
        {"label": "Examiner", "intent": "examine", "prompt": "J'observe {name}."},
    ),
}


def _default_interactions(kind: str, name: str) -> list[dict[str, str]]:
    templates = _DEFAULT_INTERACTIONS_BY_KIND.get(kind, ())
    return [
        {"label": tpl["label"], "intent": tpl["intent"], "prompt": tpl["prompt"].format(name=name)}
        for tpl in templates
    ]


def _place_feature(
    feature: SceneFeatureSpec,
    idx: int,
    occupied: set[tuple[int, int]],
    pack: ThemePack,
    rng: random.Random,
    pois: list[dict[str, Any]],
    elements: list[dict[str, Any]],
) -> None:
    base = _zone_to_cell(feature.zone, rng)
    cell = nearest_free_cell(base, occupied, _COLS, _ROWS)
    occupied.add((cell.col, cell.row))
    feature_id = f"feature_{idx + 1}"

    if feature.kind == "decor":
        elements.append(
            asset_element(
                f"element_{feature_id}",
                feature.name,
                "decor",
                rect(cell.col + 0.1, cell.row + 0.1, 0.8, 0.8),
                _pick_asset(pack.decor_assets, rng),
            )
        )
        return

    poi: dict[str, Any] = {
        "id": feature_id,
        "name": feature.name,
        "kind": feature.kind,
        "position": cell.to_dict(),
        "icon": SCENE_FEATURE_ICONS.get(feature.kind, "marker"),
    }
    if feature.note:
        poi["description"] = feature.note

    if feature.kind == "cover":
        element_id = f"element_{feature_id}"
        elements.append(
            asset_element(
                element_id,
                feature.name,
                "cover",
                rect(cell.col + 0.1, cell.row + 0.1, 0.8, 0.8),
                _pick_asset(pack.cover_assets, rng),
            )
        )
        poi["element_id"] = element_id
    elif feature.kind == "hazard":
        element_id = f"element_{feature_id}"
        elements.append(
            asset_element(
                element_id,
                feature.name,
                "hazard",
                ellipse(cell.col + 0.5, cell.row + 0.5, 0.5, 0.5),
                _pick_asset(pack.hazard_assets, rng),
                blocks_movement=False,
                opaque=False,
                interactive=True,
            )
        )
        poi["element_id"] = element_id

    interactions = _default_interactions(feature.kind, feature.name)
    if interactions:
        poi["interactions"] = interactions

    pois.append(poi)


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))
