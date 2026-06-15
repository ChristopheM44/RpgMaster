"""layout_region_nodes + build_region_decor — placement et décor déterministes (Piste C.2)."""

from __future__ import annotations

import math

import pytest

from app.engine.worldmap_builder import build_region_decor, layout_region_nodes
from app.schemas.map import MapDecor

# ─────────────────────────── layout_region_nodes ──────────────────────────────


def _unpositioned_nodes(count: int) -> list[dict]:
    return [{"id": f"n{i}", "name": f"Node {i}"} for i in range(count)]


def test_layout_region_nodes_assigns_positions_within_bounds() -> None:
    result = layout_region_nodes(_unpositioned_nodes(6), seed="bornes")

    for node in result:
        position = node["position"]
        assert 0.0 <= position["x"] <= 100.0
        assert 0.0 <= position["y"] <= 100.0


def test_layout_region_nodes_is_deterministic() -> None:
    nodes = _unpositioned_nodes(5)

    first = layout_region_nodes(nodes, seed="meme-graine")
    second = layout_region_nodes(nodes, seed="meme-graine")

    assert first == second


def test_layout_region_nodes_different_seed_changes_layout() -> None:
    nodes = _unpositioned_nodes(5)

    first = layout_region_nodes(nodes, seed="graine-a")
    second = layout_region_nodes(nodes, seed="graine-b")

    assert [n["position"] for n in first] != [n["position"] for n in second]


def test_layout_region_nodes_avoids_gross_overlap() -> None:
    result = layout_region_nodes(_unpositioned_nodes(5), seed="chevauchement")

    positions = [(n["position"]["x"], n["position"]["y"]) for n in result]
    for i in range(len(positions)):
        for j in range(i + 1, len(positions)):
            distance = math.hypot(
                positions[i][0] - positions[j][0], positions[i][1] - positions[j][1]
            )
            assert distance >= 8.0


def test_layout_region_nodes_preserves_existing_positions() -> None:
    nodes = [
        {"id": "fixe", "name": "Fixe", "position": {"x": 20.0, "y": 30.0}},
        {"id": "nouveau1", "name": "Nouveau 1"},
        {"id": "nouveau2", "name": "Nouveau 2"},
    ]

    result = layout_region_nodes(nodes, seed="ancrage")
    by_id = {n["id"]: n for n in result}

    assert by_id["fixe"]["position"] == {"x": 20.0, "y": 30.0}
    assert "position" in by_id["nouveau1"]
    assert "position" in by_id["nouveau2"]
    assert by_id["nouveau1"]["position"] != by_id["nouveau2"]["position"]


def test_layout_region_nodes_returns_copies_when_all_positioned() -> None:
    nodes = [
        {"id": "a", "name": "A", "position": {"x": 10.0, "y": 10.0}},
        {"id": "b", "name": "B", "position": {"x": 90.0, "y": 90.0}},
    ]

    result = layout_region_nodes(nodes, seed="inchange")

    assert result == nodes
    assert result is not nodes


def test_layout_region_nodes_empty_list_returns_empty() -> None:
    assert layout_region_nodes([], seed="vide") == []


# ─────────────────────────── build_region_decor ───────────────────────────────


@pytest.mark.parametrize("biome", ["default", "coastal", "desert", "mountain", "city"])
def test_build_region_decor_matches_map_decor_schema(biome: str) -> None:
    nodes = layout_region_nodes(_unpositioned_nodes(4), seed=f"decor-{biome}")

    decor = build_region_decor(nodes, biome, seed="decor-seed")

    validated = MapDecor.model_validate(decor)
    assert validated.forests  # tous les biomes ont au moins des forets/buissons


def test_build_region_decor_is_deterministic() -> None:
    nodes = layout_region_nodes(_unpositioned_nodes(4), seed="decor-determinisme")

    first = build_region_decor(nodes, "mountain", seed="meme-graine-decor")
    second = build_region_decor(nodes, "mountain", seed="meme-graine-decor")

    assert first == second


def test_build_region_decor_coastal_uses_valid_coastline_side() -> None:
    nodes = layout_region_nodes(_unpositioned_nodes(4), seed="decor-cote")

    for i in range(10):
        decor = build_region_decor(nodes, "coastal", seed=f"cote-{i}")
        assert decor["coastline"]["side"] in {"west", "north", "east"}


def test_build_region_decor_mountain_biome_includes_mountains() -> None:
    nodes = layout_region_nodes(_unpositioned_nodes(4), seed="decor-montagne")

    decor = build_region_decor(nodes, "mountain", seed="decor-seed")

    assert len(decor["mountains"]) >= 7


def test_build_region_decor_desert_biome_has_no_mountains_or_coastline() -> None:
    nodes = layout_region_nodes(_unpositioned_nodes(4), seed="decor-desert")

    decor = build_region_decor(nodes, "desert", seed="decor-seed")

    assert "mountains" not in decor
    assert "coastline" not in decor


def test_build_region_decor_unknown_biome_falls_back_to_default() -> None:
    nodes = layout_region_nodes(_unpositioned_nodes(4), seed="decor-fallback")

    unknown = build_region_decor(nodes, "swamp", seed="meme-graine")
    default = build_region_decor(nodes, "default", seed="meme-graine")

    assert unknown == default


def test_build_region_decor_city_decor_does_not_depend_on_region_biome_keywords() -> None:
    """Les villes utilisent toujours le décor périphérique 'city', quel que soit le biome régional."""
    nodes = layout_region_nodes(_unpositioned_nodes(4), seed="decor-ville")

    city_decor = build_region_decor(nodes, "city", seed="ville-seed")

    MapDecor.model_validate(city_decor)
    assert "mountains" not in city_decor
    assert "coastline" not in city_decor
