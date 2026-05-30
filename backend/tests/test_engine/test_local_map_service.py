from app.services.local_map_service import (
    build_graph_map_visual_prompt,
    build_scene_visual_prompt,
    element_grid_cells,
    enrich_scene_layout,
    normalize_scene_element,
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


def test_plaza_enrichment_does_not_create_local_roads() -> None:
    layout = {
        "cols": 12,
        "rows": 12,
        "terrain": "settlement",
        "scene_theme": "city",
        "description": (
            "Place du Marché Central pendant le festival. La foule entoure le "
            "Pavillon des Festivités et le sol vibre sous les pavés."
        ),
        "pois": [],
        "exits": [
            {
                "id": "quitter_place",
                "label": "Quitter la place",
                "position": {"col": 6, "row": 6},
                "leads_to": "rues_voisines",
            },
            {
                "id": "allee_est",
                "label": "Allée est",
                "position": {"col": 8, "row": 6},
                "leads_to": "quartier_est",
            },
        ],
    }

    enrich_scene_layout(layout)

    road_elements = [
        element
        for element in layout["elements"]
        if element.get("kind") == "terrain"
        and element.get("terrain_type") in {"road", "street", "path"}
    ]
    assert road_elements == []
    assert any(element["id"] == "pavage_place" for element in layout["elements"])
    assert any(element["id"] == "pavillon_festivites" for element in layout["elements"])
    assert not any(element["id"] == "grille_egout" for element in layout["elements"])
    assert all(exit_["placement"] == "edge" for exit_ in layout["exits"])
    assert all(
        exit_["position"]["col"] in {0, 11} or exit_["position"]["row"] in {0, 11}
        for exit_ in layout["exits"]
    )


def test_plaza_enrichment_keeps_explicit_sewer_access_visible() -> None:
    layout = {
        "cols": 12,
        "rows": 12,
        "terrain": "settlement",
        "scene_theme": "city",
        "description": (
            "Place du Marché Central pendant le festival. Une grille d'égout disjointe "
            "frémit près du bord de la place."
        ),
        "pois": [],
        "exits": [],
    }

    enrich_scene_layout(layout)

    linked = next(element for element in layout["elements"] if element["id"] == "grille_egout")
    assert linked["kind"] == "stairs"
    assert linked["interactive"] is True


def test_plaza_enrichment_strips_legacy_inferred_sewer_access() -> None:
    layout = {
        "cols": 12,
        "rows": 12,
        "terrain": "settlement",
        "scene_theme": "city",
        "description": "La foule du festival s'agite et le sol vibre sous les pavés.",
        "pois": [
            {
                "id": "vibration_sol",
                "name": "Vibration anormale",
                "kind": "clue",
                "position": {"col": 4, "row": 4},
                "description": "Une onde légère parcourt le sol.",
            },
        ],
        "exits": [],
        "elements": [
            {
                "id": "grille_egout",
                "name": "Grille d'égout",
                "kind": "stairs",
                "geometry": {"type": "rect", "col": 7, "row": 8, "width": 0.8, "height": 0.8},
                "description": "Une ouverture métallique suggère un accès sous la ville.",
                "interactive": True,
            },
        ],
    }

    enrich_scene_layout(layout)

    assert not any(element["id"] == "grille_egout" for element in layout["elements"])
    assert any(element["id"] == "element_vibration_sol" for element in layout["elements"])


def test_embedded_exit_stays_internal_and_gets_element_link() -> None:
    layout = {
        "cols": 12,
        "rows": 12,
        "terrain": "settlement",
        "scene_theme": "city",
        "description": "Une petite place avec une trappe menant aux égouts.",
        "pois": [],
        "exits": [
            {
                "id": "trappe_egouts",
                "label": "Trappe vers les égouts",
                "position": {"col": 6, "row": 7},
                "leads_to": "egouts",
            },
        ],
    }

    enrich_scene_layout(layout)

    exit_ = layout["exits"][0]
    assert exit_["placement"] == "embedded"
    assert exit_["position"] == {"col": 6, "row": 7}
    assert exit_["element_id"]
    linked = next(element for element in layout["elements"] if element["id"] == exit_["element_id"])
    assert linked["kind"] == "stairs"
    assert linked["interactive"] is True


def test_explicit_terrain_path_is_preserved() -> None:
    element = normalize_scene_element(
        {
            "id": "sentier_cotier",
            "name": "Sentier côtier",
            "kind": "terrain",
            "terrain_type": "path",
            "geometry": {
                "type": "line",
                "from": {"col": 0, "row": 6},
                "to": {"col": 11, "row": 6},
            },
        },
        12,
        12,
    )

    assert element is not None
    assert element["kind"] == "terrain"
    assert element["terrain_type"] == "path"


def test_plaza_visual_prompt_discourages_traversing_road() -> None:
    layout = {
        "cols": 12,
        "rows": 12,
        "terrain": "settlement",
        "scene_theme": "city",
        "description": "Place du Marché Central, foule et pavillon des festivités.",
        "pois": [],
        "exits": [],
    }
    enrich_scene_layout(layout)

    prompt = build_scene_visual_prompt(layout)

    assert "Pavés de la place" in prompt
    assert "Pavillon des festivités" in prompt
    assert "traversing road" in prompt
