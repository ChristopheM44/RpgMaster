"""Habillage par type de lieu (refonte cartes, lot 4)."""

from __future__ import annotations

import copy

import pytest

from app.engine.scene_dressing import (
    DRESSING_ID_PREFIX,
    detect_place_type,
    dress_scene,
)
from app.services.local_map_service import element_grid_cells, enrich_scene_layout


def _library(**extra: object) -> dict:
    """Bibliothèque réelle (session d24164e5) : AUCUNE description, le lieu se lit
    dans les repères et le mobilier."""
    return {
        "scene_id": "scene_dd4cda0bb023",
        "scene_theme": "dungeon",
        "terrain": "interior",
        "cols": 12,
        "rows": 12,
        "pois": [
            {
                "id": "lutrin",
                "name": "Lutrin du catalogue",
                "kind": "clue",
                "position": {"col": 5, "row": 5},
            },
            {
                "id": "rayon",
                "name": "Rayonnage d'Histoire",
                "kind": "clue",
                "position": {"col": 2, "row": 8},
            },
            {
                "id": "coffre",
                "name": "Coffre à rouleaux",
                "kind": "loot",
                "position": {"col": 9, "row": 3},
            },
        ],
        "exits": [
            {"id": "sortie", "label": "Couloir", "position": {"col": 11, "row": 6}},
        ],
        "party_positions": {"hero": {"col": 10, "row": 6}},
        "elements": [],
        **extra,
    }


def _cells(element: dict) -> set[tuple[int, int]]:
    return {(cell["col"], cell["row"]) for cell in element_grid_cells(element, 12, 12)}


def _dressing(layout: dict) -> list[dict]:
    return [e for e in layout["elements"] if e["id"].startswith(DRESSING_ID_PREFIX)]


def test_library_is_recognised_from_its_content_without_description() -> None:
    assert detect_place_type(_library(), interior=True) == "library"


def test_a_door_naming_another_place_is_not_enough() -> None:
    """« Porte de la bibliothèque » dans un couloir : la sortie nomme un AUTRE lieu."""
    corridor = {
        "description": "Un couloir humide.",
        "pois": [],
        "exits": [{"id": "e", "label": "Porte de la bibliothèque"}],
        "elements": [],
    }
    assert detect_place_type(corridor, interior=True) is None


def test_exterior_types_are_not_used_indoors() -> None:
    camp = {"description": "Un campement de nomades au pied des dunes.", "pois": [], "exits": []}
    assert detect_place_type(camp, interior=False) == "camp"
    assert detect_place_type(camp, interior=True) is None


def test_library_dressing_lines_the_walls_with_shelves_facing_the_room() -> None:
    layout = enrich_scene_layout(_library())
    dressing = _dressing(layout)
    shelves = [e for e in dressing if e["asset_key"] == "proc/bookcase"]
    assert len(shelves) >= 3
    inward = {"north": "south", "south": "north", "west": "east", "east": "west"}
    for shelf in shelves:
        geometry = shelf["geometry"]
        touching = {
            "north": geometry["row"] < 0.1,
            "south": geometry["row"] + geometry["height"] > 11.9,
            "west": geometry["col"] < 0.1,
            "east": geometry["col"] + geometry["width"] > 11.9,
        }
        wall = next(side for side, hit in touching.items() if hit)
        assert shelf["facing"] == inward[wall]
    assert any(e["asset_key"] == "prop/table_long" for e in dressing)


def test_dressing_never_covers_exits_pois_party_or_their_surroundings() -> None:
    layout = enrich_scene_layout(_library())
    important = {(5, 5), (2, 8), (9, 3), (11, 6), (10, 6)}
    for element in _dressing(layout):
        for col, row in _cells(element):
            assert all(max(abs(col - c), abs(row - r)) > 1 for c, r in important), element


def test_dressing_keeps_every_important_cell_reachable() -> None:
    layout = enrich_scene_layout(_library())
    blocked = set()
    for element in layout["elements"]:
        if element.get("blocks_movement"):
            blocked |= _cells(element)
    important = {(5, 5), (2, 8), (9, 3), (11, 6), (10, 6)}
    start = (10, 6)
    seen, stack = {start}, [start]
    while stack:
        col, row = stack.pop()
        for nxt in ((col + 1, row), (col - 1, row), (col, row + 1), (col, row - 1)):
            if (
                0 <= nxt[0] < 12
                and 0 <= nxt[1] < 12
                and nxt not in seen
                and (nxt not in blocked or nxt in important)
            ):
                seen.add(nxt)
                stack.append(nxt)
    assert important <= seen


def test_dressing_is_idempotent_and_deterministic() -> None:
    first = enrich_scene_layout(_library())
    again = enrich_scene_layout(copy.deepcopy(first))
    assert again == first
    other = enrich_scene_layout(_library())
    assert _dressing(other) == _dressing(first)


def test_an_already_furnished_place_is_left_as_authored() -> None:
    shelves = [
        {
            "id": f"shelf_{i}",
            "name": "Rayonnage",
            "kind": "furniture",
            "geometry": {"type": "rect", "col": 1 + 2 * i, "row": 0.1, "width": 1.5, "height": 0.5},
        }
        for i in range(3)
    ]
    layout = _library(elements=shelves)
    assert (
        dress_scene(layout, interior=True, occupied=set(), access_cells=set(), blocking=set()) == []
    )


def test_unknown_place_gets_no_dressing() -> None:
    layout = enrich_scene_layout(
        {
            "scene_id": "x",
            "scene_theme": "forest",
            "description": "Une clairière.",
            "cols": 12,
            "rows": 12,
            "pois": [],
            "exits": [],
            "elements": [],
        }
    )
    assert _dressing(layout) == []


@pytest.mark.parametrize(
    ("description", "asset"),
    [
        ("Une crypte voûtée.", "proc/sarcophagus"),
        ("La salle commune de la taverne.", "prop/table_small"),
        ("Le choeur d'une chapelle.", "proc/altar"),
        ("La forge du village.", "proc/anvil"),
    ],
)
def test_place_types_bring_their_signature_piece(description: str, asset: str) -> None:
    layout = enrich_scene_layout(
        {
            "scene_id": f"s-{asset}",
            "scene_theme": "dungeon",
            "description": description,
            "cols": 12,
            "rows": 12,
            "pois": [],
            "exits": [{"id": "e", "label": "Sortie", "position": {"col": 6, "row": 11}}],
            "elements": [],
        }
    )
    assert asset in {e["asset_key"] for e in _dressing(layout)}


def test_garden_dressing_inherits_the_scene_material() -> None:
    """Le Jardin pétrifié : les arbres ajoutés sont eux aussi de pierre."""
    layout = enrich_scene_layout(
        {
            "scene_id": "scene_f6f69c90c091",
            "scene_theme": "dungeon",
            "description": "Une serre monumentale où la flore est devenue de la pierre grise.",
            "cols": 12,
            "rows": 12,
            "pois": [
                {
                    "id": "a",
                    "name": "Arbre pétrifié massif",
                    "kind": "cover",
                    "position": {"col": 6, "row": 6},
                },
            ],
            "exits": [],
            "elements": [],
        }
    )
    trees = [e for e in _dressing(layout) if e["asset_key"] == "nature/tree_dark"]
    assert trees and all(tree.get("tint") == "petrified" for tree in trees)


def test_no_dressing_on_the_hero_fallback_row_without_party_positions() -> None:
    """Sans party_positions, le client aligne les héros sur la rangée centrale."""
    layout = enrich_scene_layout(_library(party_positions={}))
    for element in _dressing(layout):
        assert all(row != 6 for _, row in _cells(element)), element


def test_load_repair_does_not_dress_a_scene_mid_combat() -> None:
    from app.services.visual_coherence_service import repair_state_visual_coherence

    in_combat = {"current_scene": _library(), "grid_positions": {"hero": {"col": 5, "row": 3}}}
    repair_state_visual_coherence(in_combat)
    assert _dressing(in_combat["current_scene"]) == []

    after_combat = {"current_scene": _library()}
    repair_state_visual_coherence(after_combat)
    assert _dressing(after_combat["current_scene"])
