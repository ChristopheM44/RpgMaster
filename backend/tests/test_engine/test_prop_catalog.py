"""Catalogue sémantique des props (refonte cartes, lot 4) : nom → modèle + teinte."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.engine.prop_catalog import (
    PROCEDURAL_PROP_KEYS,
    catalog_asset_keys,
    match_prop,
    match_tint,
    normalize_words,
    render_typescript,
)
from app.engine.theme_packs import THEME_PACKS
from app.services.local_map_service import SCENE_ASSET_KEYS, enrich_scene_layout

GENERATED_TS = (
    Path(__file__).resolve().parents[3]
    / "frontend"
    / "src"
    / "engine3d"
    / "assets"
    / "propCatalog.generated.ts"
)


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        # Les contresens constatés sur les 3 scènes de test.
        ("Arbre pétrifié massif", "nature/tree_dark"),
        ("Fontaine tarie", "proc/fountain"),
        ("Rochers érodés", "nature/rock_large_a"),
        ("Traces de bottes", "proc/footprints"),
        ("Lutrin", "proc/lectern"),
        ("Rayonnage d'Histoire", "proc/bookcase"),
        ("Étagère murale", "prop/shelf_large"),
        ("Coffre à rouleaux", "prop/chest"),
        ("Stèle effacée", "prop/obelisk"),
        # Spécifique avant générique.
        ("Coffre d'or", "prop/chest_gold"),
        ("Tronc renversé", "nature/log"),
        ("Bloc de pierre effondré", "prop/rubble_large"),
        ("Dune affaissée", "proc/mound"),
        ("Étal renversé", "prop/table_medium"),
        ("Autel marqué", "proc/altar"),
    ],
)
def test_match_prop_follows_the_name(name: str, expected: str) -> None:
    assert match_prop(name) == expected


@pytest.mark.parametrize("name", ["Litière souillée", "Orée du bois", "Sable traître", "Murmure"])
def test_match_prop_respects_word_boundaries(name: str) -> None:
    assert match_prop(name) is None


def test_normalize_words_strips_accents_and_punctuation() -> None:
    assert normalize_words("Coffre d'Or — Étagère!") == " coffre d or etagere "


@pytest.mark.parametrize(
    ("text", "tint"),
    [
        ("Arbre pétrifié massif", "petrified"),
        ("Ronces de pierre", "petrified"),
        ("Poutre calcinée", "charred"),
        ("Rochers érodés", "sand"),
        ("Souche moussue", "moss"),
        ("Arbre mort", "deadwood"),
        ("Table", None),
    ],
)
def test_match_tint(text: str, tint: str | None) -> None:
    assert match_tint(text) == tint


def test_catalog_keys_are_accepted_scene_asset_keys() -> None:
    assert catalog_asset_keys() <= SCENE_ASSET_KEYS
    assert set(PROCEDURAL_PROP_KEYS) <= SCENE_ASSET_KEYS


@pytest.mark.parametrize("theme", sorted(THEME_PACKS))
def test_theme_pack_labels_are_known_to_the_catalog(theme: str) -> None:
    """Les features injectées par défaut reçoivent un modèle cohérent avec leur nom."""
    pack = THEME_PACKS[theme]
    assert match_prop(pack.cover_label), pack.cover_label
    assert match_prop(pack.decor_label), pack.decor_label


def test_generated_typescript_catalog_is_up_to_date() -> None:
    assert GENERATED_TS.read_text(encoding="utf-8") == render_typescript(), (
        "Régénérer : cd backend && .venv/bin/python scripts/export_prop_catalog.py"
    )


def _scene(elements: list[dict]) -> dict:
    return {
        "scene_id": "s",
        "scene_theme": "forest",
        "cols": 12,
        "rows": 12,
        "pois": [],
        "exits": [],
        "elements": elements,
    }


def _rect_element(element_id: str, name: str, kind: str, **extra: object) -> dict:
    return {
        "id": element_id,
        "name": name,
        "kind": kind,
        "geometry": {"type": "rect", "col": 5, "row": 5, "width": 1, "height": 1},
        **extra,
    }


def test_enrich_replaces_a_random_pack_asset_with_the_named_model() -> None:
    """Scène sauvegardée : l'ancien tirage (« Arbre pétrifié » → caisses) est corrigé."""
    layout = enrich_scene_layout(
        _scene(
            [
                _rect_element(
                    "tree", "Arbre pétrifié massif", "cover", asset_key="prop/crates_stacked"
                ),
                _rect_element("fountain", "Fontaine tarie", "decor", asset_key="prop/barrel_large"),
            ]
        )
    )
    by_id = {element["id"]: element for element in layout["elements"]}
    assert by_id["tree"]["asset_key"] == "nature/tree_dark"
    assert by_id["tree"]["tint"] == "petrified"
    assert by_id["fountain"]["asset_key"] == "proc/fountain"


def test_enrich_drops_an_asset_the_name_does_not_support() -> None:
    layout = enrich_scene_layout(
        _scene([_rect_element("odd", "Vieux mécanisme", "cover", asset_key="prop/crates_stacked")])
    )
    odd = next(element for element in layout["elements"] if element["id"] == "odd")
    assert "asset_key" not in odd


def test_enrich_leaves_walls_and_doors_alone() -> None:
    layout = enrich_scene_layout(
        _scene([_rect_element("w", "Mur de caisses", "wall", asset_key="prop/wall")])
    )
    wall = next(element for element in layout["elements"] if element["id"] == "w")
    assert wall["asset_key"] == "prop/wall"
