from app.game.scene_theme import coerce_scene_theme, infer_scene_theme
from app.services.visual_coherence_service import repair_state_visual_coherence


def test_infer_scene_theme_prefers_desert_for_bare_sand() -> None:
    assert infer_scene_theme("La Piste d'Ambre", "sable brûlant", "Canicule extrême") == "desert"


def test_infer_scene_theme_keeps_beach_when_sea_context_exists() -> None:
    assert infer_scene_theme("plage de sable", "la mer roule contre le rivage") == "beach"


def test_infer_scene_theme_detects_coastal_without_beach() -> None:
    assert infer_scene_theme("port de brume", "falaises au-dessus de la mer") == "coastal"


def test_infer_scene_theme_falls_back_without_signal() -> None:
    assert infer_scene_theme("un lieu étrange", fallback="forest") == "forest"


def test_coerce_scene_theme_repairs_beach_desert_contradiction() -> None:
    assert coerce_scene_theme("beach", "dunes", "oasis", "canicule") == "desert"


def test_visual_coherence_repairs_saved_desert_opening() -> None:
    state_data = {
        "adventure_journal": {
            "location_region": "Les Sables de la Corruption",
            "location_place": "La Piste d'Ambre",
            "weather": "Canicule extrême",
        },
        "current_scene": {
            "scene_theme": "beach",
            "terrain": "landmark",
            "description": "Le sable doré s'insinue partout.",
            "pois": [],
            "exits": [],
        },
        "world_maps": {
            "region_map": {
                "decor": {
                    "coastline": {
                        "side": "west",
                        "points": [{"x": 0, "y": 0}, {"x": 8, "y": 100}],
                    }
                }
            }
        },
    }

    assert repair_state_visual_coherence(state_data) is True
    assert state_data["current_scene"]["scene_theme"] == "desert"
    assert "coastline" not in state_data["world_maps"]["region_map"]["decor"]
