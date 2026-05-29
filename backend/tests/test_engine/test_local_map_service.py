from app.services.local_map_service import (
    build_graph_map_visual_prompt,
    build_scene_visual_prompt,
    element_grid_cells,
)


def test_scene_visual_prompt_uses_public_visible_fields_only() -> None:
    prompt = build_scene_visual_prompt(
        {
            "scene_theme": "dungeon",
            "terrain": "crypt",
            "description": "Une crypte froide avec un autel fissuré.",
            "elements": [{"id": "altar", "kind": "decor", "name": "Autel fissuré"}],
            "pois": [{"id": "clue", "kind": "clue", "name": "Rune bleue"}],
            "exits": [{"id": "door", "label": "Porte nord", "secret": "ne doit pas sortir"}],
            "secrets": ["dragon caché"],
            "motivations": {"hidden": "trahir le groupe"},
        }
    )

    assert "Autel fissuré" in prompt
    assert "Rune bleue" in prompt
    assert "Porte nord" in prompt
    assert "dragon caché" not in prompt
    assert "trahir le groupe" not in prompt
    assert "ne doit pas sortir" not in prompt


def test_element_grid_cells_projects_rectangles_to_cells() -> None:
    cells = element_grid_cells(
        {
            "kind": "furniture",
            "geometry": {"type": "rect", "col": 2.2, "row": 3.1, "width": 1.4, "height": 1.2},
        },
        8,
        8,
    )

    assert cells == [
        {"col": 2, "row": 3},
        {"col": 3, "row": 3},
        {"col": 2, "row": 4},
        {"col": 3, "row": 4},
    ]


def test_graph_map_visual_prompt_uses_public_graph_only() -> None:
    prompt = build_graph_map_visual_prompt(
        {
            "name": "Val de Brume",
            "nodes": [{"id": "village", "kind": "settlement", "name": "Village"}],
            "edges": [{"id": "road", "kind": "road", "secret": "embuscade"}],
            "gm_secret": "dragon",
        },
        map_kind="region",
    )

    assert "Val de Brume" in prompt
    assert "Village" in prompt
    assert "dragon" not in prompt
    assert "embuscade" not in prompt
