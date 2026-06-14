from copy import deepcopy

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
    assert linked["asset_key"] == "prop/stairs"


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


def test_enrich_injects_3d_defaults_for_interior_scene() -> None:
    layout = {
        "cols": 10,
        "rows": 8,
        "terrain": "stone_chamber",
        "scene_theme": "dungeon",
        "pois": [],
        "exits": [
            {
                "id": "stone_door",
                "label": "Porte de pierre",
                "position": {"col": 9, "row": 4},
                "leads_to": "couloir",
            }
        ],
    }

    enrich_scene_layout(layout)

    by_kind = {}
    for element in layout["elements"]:
        by_kind.setdefault(element["kind"], element)
        assert element["elevation_m"] == 0.0
    assert by_kind["wall"]["height_m"] == 2.5
    assert by_kind["door"]["height_m"] == 2.2
    assert by_kind["wall"]["asset_key"] == "prop/wall"
    assert by_kind["door"]["asset_key"] == "prop/door"
    assert any(
        element.get("asset_key") == "prop/wall_corner"
        for element in layout["elements"]
        if element.get("kind") == "wall"
    )
    assert layout["ambiance"] == {"light": "torchlit", "fog_density": 0.25}
    assert layout["vegetation_density"] == 0.0


def test_enrich_clamps_llm_3d_hints() -> None:
    layout = {
        "cols": 12,
        "rows": 12,
        "terrain": "clairière",
        "scene_theme": "forest",
        "vegetation_density": 2.0,
        "ambiance": {"light": "neon", "fog_density": 3.0},
        "pois": [],
        "exits": [],
        "elements": [
            {
                "id": "rocher",
                "name": "Rocher moussu",
                "kind": "cover",
                "geometry": {"type": "rect", "col": 4, "row": 4, "width": 1, "height": 1},
                "height_m": 99,
                "elevation_m": 99,
            }
        ],
    }

    enrich_scene_layout(layout)

    rocher = next(element for element in layout["elements"] if element["id"] == "rocher")
    assert rocher["height_m"] == 8.0
    assert rocher["elevation_m"] == 4.0
    assert layout["vegetation_density"] == 1.0
    assert layout["ambiance"] == {"light": "day", "fog_density": 1.0}


def test_enrich_keeps_valid_torchlit_light_on_forest() -> None:
    layout = {
        "cols": 12,
        "rows": 12,
        "terrain": "sous-bois",
        "scene_theme": "forest",
        "ambiance": {"light": "torchlit"},
        "pois": [],
        "exits": [],
    }

    enrich_scene_layout(layout)

    assert layout["ambiance"] == {"light": "torchlit", "fog_density": 0.2}
    assert layout["vegetation_density"] == 0.8


def test_enrich_dungeon_theme_defaults_to_torchlit_even_at_day() -> None:
    layout = {
        "cols": 8,
        "rows": 8,
        "terrain": "crypte",
        "scene_theme": "dungeon",
        "pois": [],
        "exits": [],
    }

    enrich_scene_layout(layout, time_of_day="day")

    assert layout["ambiance"]["light"] == "torchlit"


def test_enrich_time_of_day_drives_default_ambiance_light() -> None:
    def fresh_layout() -> dict:
        return {
            "cols": 12,
            "rows": 12,
            "terrain": "plaine herbeuse",
            "scene_theme": "plains",
            "pois": [],
            "exits": [],
        }

    night = fresh_layout()
    enrich_scene_layout(night, time_of_day="nuit tombée")
    assert night["ambiance"]["light"] == "night"

    dusk = fresh_layout()
    enrich_scene_layout(dusk, time_of_day="crépuscule")
    assert dusk["ambiance"]["light"] == "dusk"

    day = fresh_layout()
    enrich_scene_layout(day)
    assert day["ambiance"]["light"] == "day"
    assert day["ambiance"]["fog_density"] == 0.15
    assert day["vegetation_density"] == 0.4


def test_enrich_exterior_wall_defaults_to_low_height() -> None:
    layout = {
        "cols": 12,
        "rows": 12,
        "terrain": "lisière",
        "scene_theme": "forest",
        "pois": [],
        "exits": [],
        "elements": [
            {
                "id": "palissade",
                "name": "Palissade effondrée",
                "kind": "wall",
                "geometry": {
                    "type": "line",
                    "from": {"col": 2, "row": 2},
                    "to": {"col": 6, "row": 2},
                },
            }
        ],
    }

    enrich_scene_layout(layout)

    palissade = next(element for element in layout["elements"] if element["id"] == "palissade")
    assert palissade["height_m"] == 1.2


def test_normalize_scene_element_passes_through_clamped_3d_hints() -> None:
    hinted = normalize_scene_element(
        {
            "id": "muret",
            "name": "Muret",
            "kind": "wall",
            "geometry": {"type": "rect", "col": 2, "row": 2, "width": 3, "height": 0.4},
            "height_m": 99,
            "elevation_m": -3,
        },
        12,
        12,
    )
    assert hinted is not None
    assert hinted["height_m"] == 8.0
    assert hinted["elevation_m"] == 0.0

    bare = normalize_scene_element(
        {
            "id": "muret",
            "name": "Muret",
            "kind": "wall",
            "geometry": {"type": "rect", "col": 2, "row": 2, "width": 3, "height": 0.4},
        },
        12,
        12,
    )
    assert bare is not None
    assert "height_m" not in bare
    assert "elevation_m" not in bare


def test_normalize_scene_element_preserves_only_safe_asset_keys() -> None:
    safe = normalize_scene_element(
        {
            "id": "escalier",
            "name": "Escalier de pierre",
            "kind": "stairs",
            "geometry": {"type": "rect", "col": 2, "row": 2, "width": 1, "height": 1},
            "asset_key": "prop/stairs",
        },
        12,
        12,
    )
    assert safe is not None
    assert safe["asset_key"] == "prop/stairs"

    unsafe = normalize_scene_element(
        {
            "id": "mur",
            "name": "Mur",
            "kind": "wall",
            "geometry": {"type": "rect", "col": 2, "row": 2, "width": 1, "height": 1},
            "asset_key": "../../secrets/model.glb",
        },
        12,
        12,
    )
    assert unsafe is not None
    assert "asset_key" not in unsafe


def test_enrich_only_adds_3d_keys_to_legacy_persisted_scene() -> None:
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
            }
        ],
    }
    enrich_scene_layout(layout)

    # Simule une scène persistée AVANT l'ajout des hints 3D.
    legacy = deepcopy(layout)
    legacy.pop("ambiance")
    legacy.pop("vegetation_density")
    for element in legacy["elements"]:
        element.pop("height_m")
        element.pop("elevation_m")

    reenriched = deepcopy(legacy)
    enrich_scene_layout(reenriched)

    new_scene_keys = {"ambiance", "vegetation_density"}
    new_element_keys = {"height_m", "elevation_m"}
    scene_skip = new_scene_keys | {"elements"}
    assert {key: value for key, value in reenriched.items() if key not in scene_skip} == {
        key: value for key, value in legacy.items() if key != "elements"
    }
    for legacy_element, new_element in zip(legacy["elements"], reenriched["elements"], strict=True):
        assert {
            key: value for key, value in new_element.items() if key not in new_element_keys
        } == legacy_element
        assert new_element_keys <= set(new_element)
    assert new_scene_keys <= set(reenriched)
