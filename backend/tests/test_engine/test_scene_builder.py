"""build_scene — SceneSpec + seed -> scene 12x12 canonique deterministe."""

from __future__ import annotations

from typing import get_args

import pytest

from app.engine.scene_builder import build_scene
from app.engine.theme_packs import THEME_PACKS
from app.schemas.scene_spec import SceneExitSpec, SceneFeatureSpec, SceneSpec, SceneThemeName
from app.services.local_map_service import SCENE_ASSET_KEYS


def _feature(kind: str, name: str = "Element", **kwargs: object) -> SceneFeatureSpec:
    return SceneFeatureSpec(kind=kind, name=name, **kwargs)  # type: ignore[arg-type]


def test_build_scene_is_deterministic() -> None:
    spec = SceneSpec(
        theme="forest",
        enclosure="exterior",
        features=[_feature("cover", "Rocher", zone="nw"), _feature("hazard", "Ronces", zone="se")],
        exits=[SceneExitSpec(label="Sentier", direction="south", leads_to="campement_1")],
    )
    first = build_scene(spec, seed="meme-graine")
    second = build_scene(spec, seed="meme-graine")
    assert first == second


def test_build_scene_different_seed_changes_layout() -> None:
    spec = SceneSpec(
        theme="forest",
        enclosure="exterior",
        features=[
            _feature("cover", "Rocher", zone="center"),
            _feature("hazard", "Ronces", zone="center"),
        ],
    )
    first = build_scene(spec, seed="graine-a")
    second = build_scene(spec, seed="graine-b")
    assert [p["position"] for p in first["pois"]] != [p["position"] for p in second["pois"]]


def test_build_scene_canonical_shape() -> None:
    scene = build_scene(SceneSpec(theme="forest", enclosure="exterior"), seed="shape")

    assert scene["cols"] == 12
    assert scene["rows"] == 12
    assert isinstance(scene["cell_size_m"], float)
    assert isinstance(scene["terrain"], str) and scene["terrain"]
    assert scene["scene_theme"] == "forest"
    assert isinstance(scene["pois"], list)
    assert isinstance(scene["exits"], list)
    assert isinstance(scene["elements"], list)
    assert scene["party_positions"] == {}
    assert set(scene["ambiance"]) >= {"light", "fog_density"}
    assert isinstance(scene["vegetation_density"], float)


def test_build_scene_ensures_minimum_tactical_features() -> None:
    scene = build_scene(SceneSpec(), seed="vide")

    kinds = [poi["kind"] for poi in scene["pois"]]
    assert kinds.count("cover") >= 1
    assert kinds.count("hazard") >= 1
    assert len(scene["pois"]) + len(scene["exits"]) >= 3


def test_build_scene_caps_features_at_four() -> None:
    spec = SceneSpec(
        theme="forest",
        enclosure="exterior",
        features=[
            _feature("cover", "Rocher 1", zone="nw"),
            _feature("hazard", "Ronces", zone="se"),
            _feature("clue", "Empreintes", zone="east"),
            _feature("loot", "Coffre", zone="west"),
            _feature("npc", "Eclaireur", zone="north"),
        ],
    )
    scene = build_scene(spec, seed="cinq-features")
    # decor n'apparait jamais en poi ; toutes les autres features demandees sont conservees.
    assert len(scene["pois"]) == 5


def test_build_scene_exits_on_grid_edge_per_direction() -> None:
    spec = SceneSpec(
        theme="plains",
        enclosure="exterior",
        exits=[
            SceneExitSpec(label="Nord", direction="north", leads_to="nord"),
            SceneExitSpec(label="Sud", direction="south", leads_to="sud"),
            SceneExitSpec(label="Est", direction="east", leads_to="est"),
            SceneExitSpec(label="Ouest", direction="west", leads_to="ouest"),
        ],
    )
    scene = build_scene(spec, seed="bords")
    by_label = {exit_data["label"]: exit_data["position"] for exit_data in scene["exits"]}

    assert by_label["Nord"]["row"] == 0
    assert by_label["Sud"]["row"] == 11
    assert by_label["Ouest"]["col"] == 0
    assert by_label["Est"]["col"] == 11
    for position in by_label.values():
        assert 0 <= position["col"] <= 11
        assert 0 <= position["row"] <= 11


def test_build_scene_embedded_exit_sets_placement_and_element_id() -> None:
    spec = SceneSpec(
        theme="dungeon",
        enclosure="interior",
        exits=[
            SceneExitSpec(
                label="Trappe",
                direction="south",
                leads_to="cave_basse",
                embedded_element="trappe_1",
            )
        ],
    )
    scene = build_scene(spec, seed="trappe")
    exit_data = scene["exits"][0]

    assert exit_data["placement"] == "embedded"
    assert exit_data["element_id"] == "trappe_1"


def test_build_scene_cover_and_hazard_link_elements_and_interactions() -> None:
    spec = SceneSpec(
        theme="forest",
        enclosure="exterior",
        features=[
            _feature("cover", "Tronc renverse", zone="nw"),
            _feature("hazard", "Fondriere", zone="se"),
        ],
    )
    scene = build_scene(spec, seed="couvert-danger")
    pois_by_kind = {poi["kind"]: poi for poi in scene["pois"]}
    elements_by_id = {element["id"]: element for element in scene["elements"]}

    cover = pois_by_kind["cover"]
    assert cover["element_id"] in elements_by_id
    assert elements_by_id[cover["element_id"]]["kind"] == "cover"
    cover_intents = {i["intent"] for i in cover["interactions"]}
    assert {"examine", "use"} <= cover_intents

    hazard = pois_by_kind["hazard"]
    assert hazard["element_id"] in elements_by_id
    assert elements_by_id[hazard["element_id"]]["kind"] == "hazard"
    assert {i["intent"] for i in hazard["interactions"]} == {"examine"}


def test_build_scene_npc_feature_offers_talk_interaction() -> None:
    spec = SceneSpec(
        theme="city",
        enclosure="exterior",
        features=[
            _feature("cover", "Etal", zone="nw"),
            _feature("hazard", "Pave descelle", zone="se"),
            _feature("npc", "Marchande", zone="center"),
        ],
    )
    scene = build_scene(spec, seed="pnj")
    npc_poi = next(poi for poi in scene["pois"] if poi["kind"] == "npc")

    intents = {i["intent"] for i in npc_poi["interactions"]}
    assert "talk" in intents


def test_build_scene_decor_feature_becomes_element_not_poi() -> None:
    spec = SceneSpec(
        theme="forest",
        enclosure="exterior",
        features=[
            _feature("cover", "Rocher", zone="nw"),
            _feature("hazard", "Ronces", zone="se"),
            _feature("decor", "Statue moussue", zone="center"),
        ],
    )
    scene = build_scene(spec, seed="decor")

    assert all(poi["kind"] != "decor" for poi in scene["pois"])
    assert any(element["kind"] == "decor" for element in scene["elements"])


def test_build_scene_interior_non_dungeon_terrain_gets_interior_suffix() -> None:
    interior_city = build_scene(SceneSpec(theme="city", enclosure="interior"), seed="ville-int")
    exterior_city = build_scene(SceneSpec(theme="city", enclosure="exterior"), seed="ville-ext")
    interior_dungeon = build_scene(SceneSpec(theme="dungeon", enclosure="interior"), seed="donjon")

    assert interior_city["terrain"].endswith("interieur")
    assert not exterior_city["terrain"].endswith("interieur")
    assert not interior_dungeon["terrain"].endswith("interieur")


def test_theme_packs_cover_all_scene_theme_names() -> None:
    """Piste B.1 — chaque thème de ``SceneSpec`` a un pack dédié dans THEME_PACKS."""
    assert set(get_args(SceneThemeName)) <= set(THEME_PACKS)


@pytest.mark.parametrize("theme", get_args(SceneThemeName))
def test_build_scene_each_theme_produces_valid_grid_with_pack_ambiance(theme: str) -> None:
    """Piste B.5 — chaque pack produit une grille valide, exits sur bords, ambiance cohérente."""
    enclosure = "interior" if theme in {"dungeon", "cave"} else "exterior"
    pack = THEME_PACKS[theme]
    scene = build_scene(SceneSpec(theme=theme, enclosure=enclosure), seed=f"pack-{theme}")

    assert scene["cols"] == 12
    assert scene["rows"] == 12
    assert scene["scene_theme"] == theme
    assert scene["ambiance"] == pack.ambiance

    expected_vegetation = 0.0 if enclosure == "interior" else pack.vegetation_density
    assert scene["vegetation_density"] == expected_vegetation

    kinds = [poi["kind"] for poi in scene["pois"]]
    assert kinds.count("cover") >= 1
    assert kinds.count("hazard") >= 1
    assert len(scene["pois"]) + len(scene["exits"]) >= 3

    elements_by_id = {element["id"]: element for element in scene["elements"]}
    cover_poi = next(poi for poi in scene["pois"] if poi["kind"] == "cover")
    cover_element = elements_by_id[cover_poi["element_id"]]
    assert cover_element["asset_key"] in SCENE_ASSET_KEYS


def test_build_scene_variety_across_seeds_for_same_theme() -> None:
    """Piste B.5 — acceptation : 10 seeds différentes => dispositions différentes."""
    spec = SceneSpec(theme="forest", enclosure="exterior")
    layouts = {
        tuple(
            (poi["kind"], poi["position"]["col"], poi["position"]["row"]) for poi in scene["pois"]
        )
        for scene in (build_scene(spec, seed=f"variete-{i}") for i in range(10))
    }
    assert len(layouts) > 1


def test_dungeon_theme_pack_assets_match_dungeon_generator_expectations() -> None:
    """Piste B.3 — le pack 'dungeon' reste la source des asset_key du donjon procédural."""
    pack = THEME_PACKS["dungeon"]
    assert pack.cover_assets == ("prop/pillar", "prop/rubble_large", "prop/crates_stacked")
    assert pack.decor_assets[0] == "prop/barrel_large"
    assert pack.ambiance == {"light": "torchlit", "fog_density": 0.25}
    assert pack.vegetation_density == 0.0
