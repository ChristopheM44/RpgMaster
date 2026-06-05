import pytest

from app.services.map_service import (
    MapPatchError,
    build_seed_region_map,
    compact_map_context,
    merge_city_map_patch,
    merge_region_map_patch,
    public_region_map,
)

ENDPOINT = {
    "name": "Les Profondeurs noyées",
    "kind": "dungeon",
    "hint": "plus bas, là où l'eau disparaît",
}


def node(node_id: str, kind: str = "settlement", status: str = "known") -> dict:
    return {
        "id": node_id,
        "name": node_id.upper(),
        "kind": kind,
        "position": {"x": 10, "y": 10},
        "status": status,
    }


def test_merge_region_map_patch_upserts_dedupes_and_clamps_positions() -> None:
    merged = merge_region_map_patch(
        None,
        {
            "name": "Vallee",
            "current_node_id": "village",
            "nodes_upsert": [
                {
                    "id": "village",
                    "name": "Village",
                    "kind": "settlement",
                    "position": {"x": -10, "y": 140},
                    "status": "current",
                },
                {
                    "id": "village",
                    "name": "Village repris",
                    "kind": "settlement",
                    "position": {"x": 42, "y": 58},
                    "status": "visited",
                },
            ],
            "edges_upsert": [],
        },
    )

    assert merged["name"] == "Vallee"
    assert len(merged["nodes"]) == 1
    assert merged["nodes"][0]["name"] == "Village repris"
    assert merged["nodes"][0]["position"] == {"x": 42.0, "y": 58.0}
    assert merged["current_node_id"] == "village"
    assert merged["updated_at"]


def test_merge_region_map_patch_removes_incident_edges() -> None:
    existing = merge_region_map_patch(
        None,
        {
            "nodes_upsert": [
                node("a"),
                {**node("b", "ruin"), "position": {"x": 30, "y": 30}},
            ],
            "edges_upsert": [{"id": "ab", "from": "a", "to": "b", "kind": "road"}],
        },
    )

    merged = merge_region_map_patch(existing, {"nodes_remove": ["b"]})

    assert [node["id"] for node in merged["nodes"]] == ["a"]
    assert merged["edges"] == []


def test_merge_region_map_patch_rejects_orphan_edges() -> None:
    with pytest.raises(MapPatchError):
        merge_region_map_patch(
            None,
            {
                "nodes_upsert": [
                    node("a"),
                ],
                "edges_upsert": [{"id": "ab", "from": "a", "to": "b", "kind": "road"}],
            },
        )


def test_city_map_patch_preserves_existing_nodes() -> None:
    existing = merge_city_map_patch(
        None,
        {
            "city_id": "port",
            "region_node_id": "port",
            "name": "Port",
            "nodes_upsert": [
                {**node("docks", "docks"), "name": "Docks", "position": {"x": 20, "y": 70}},
            ],
        },
    )

    merged = merge_city_map_patch(
        existing,
        {
            "city_id": "port",
            "region_node_id": "port",
            "nodes_upsert": [
                {
                    **node("temple", "temple", "rumored"),
                    "name": "Temple",
                    "position": {"x": 70, "y": 30},
                },
            ],
        },
    )

    assert {node["id"] for node in merged["nodes"]} == {"docks", "temple"}


def _decor_payload() -> dict:
    """Fixture : un décor complet pour les tests."""
    return {
        "forests": [{"x": 24, "y": 18, "radius": 3.2, "opacity": 0.4}],
        "mountains": [{"x": 80, "y": 28, "height": 5.0}],
        "coastline": {
            "side": "west",
            "points": [
                {"x": 0, "y": 0},
                {"x": 18, "y": 0},
                {"x": 12, "y": 100},
                {"x": 0, "y": 100},
            ],
        },
        "river": {"path": "M 0 76 Q 30 80 60 78 T 100 80", "width": 1.5},
        "decorative_roads": ["M 12 60 L 88 60"],
    }


def _visual_asset_payload() -> dict:
    return {
        "provider": "openai_compatible",
        "model": "gpt-image-1",
        "status": "prompt_ready",
        "prompt": "Top-down city map.",
        "prompt_hash": "abc123",
    }


def test_region_map_decor_is_set_on_first_patch() -> None:
    """Un premier patch avec decor le stocke correctement."""
    merged = merge_region_map_patch(
        None,
        {
            "nodes_upsert": [
                {"id": "a", "name": "A", "kind": "settlement", "position": {"x": 50, "y": 50}}
            ],
            "decor": _decor_payload(),
        },
    )

    assert "decor" in merged
    assert len(merged["decor"]["forests"]) == 1
    assert merged["decor"]["forests"][0]["x"] == 24.0
    assert merged["decor"]["river"]["path"] == "M 0 76 Q 30 80 60 78 T 100 80"


def test_region_map_decor_preserved_when_patch_has_no_decor() -> None:
    """Un patch narratif sans décor ne doit PAS effacer le décor existant (set-once)."""
    initial = merge_region_map_patch(
        None,
        {
            "nodes_upsert": [
                {"id": "a", "name": "A", "kind": "settlement", "position": {"x": 50, "y": 50}}
            ],
            "decor": _decor_payload(),
        },
    )

    # Patch ultérieur (narratif) sans champ decor
    updated = merge_region_map_patch(
        initial,
        {
            "current_node_id": "a",
        },
    )

    assert "decor" in updated
    assert len(updated["decor"]["forests"]) == 1  # inchangé


def test_region_map_decor_replaced_when_patch_provides_decor() -> None:
    """Un patch avec un nouveau decor remplace l'ancien."""
    initial = merge_region_map_patch(
        None,
        {
            "nodes_upsert": [
                {"id": "a", "name": "A", "kind": "settlement", "position": {"x": 50, "y": 50}}
            ],
            "decor": _decor_payload(),
        },
    )

    new_decor = {"forests": [{"x": 10, "y": 20}, {"x": 30, "y": 40}]}
    updated = merge_region_map_patch(
        initial,
        {"decor": new_decor},
    )

    assert len(updated["decor"]["forests"]) == 2
    assert updated["decor"]["forests"][0]["x"] == 10.0
    # Ancien river effacé car nouveau decor ne l'inclut pas
    assert updated["decor"].get("river") is None


def test_city_map_decor_set_once_semantics() -> None:
    """Idem pour CityMap : patch sans decor préserve l'existant."""
    from app.services.map_service import merge_city_map_patch

    initial = merge_city_map_patch(
        None,
        {
            "city_id": "phandalin",
            "region_node_id": "phandalin",
            "name": "Phandalin",
            "nodes_upsert": [
                {
                    "id": "inn",
                    "name": "Stonehill Inn",
                    "kind": "tavern",
                    "position": {"x": 38, "y": 52},
                }
            ],
            "decor": _decor_payload(),
        },
    )

    # Patch narratif sans decor
    updated = merge_city_map_patch(
        initial,
        {
            "city_id": "phandalin",
            "region_node_id": "phandalin",
            "current_node_id": "inn",
        },
    )

    assert updated["decor"]["forests"][0]["x"] == 24.0  # préservé


def test_region_map_visual_asset_is_preserved_without_patch_value() -> None:
    initial = merge_region_map_patch(
        None,
        {
            "nodes_upsert": [{"id": "a", "name": "A", "kind": "settlement"}],
            "visual_asset": _visual_asset_payload(),
        },
    )

    updated = merge_region_map_patch(initial, {"current_node_id": "a"})

    assert updated["visual_asset"]["model"] == "gpt-image-1"
    assert updated["visual_asset"]["status"] == "prompt_ready"


def test_public_region_map_filters_hidden_edges() -> None:
    merged = merge_region_map_patch(
        None,
        {
            "nodes_upsert": [
                node("a"),
                {**node("b", "ruin"), "position": {"x": 30, "y": 30}},
            ],
            "edges_upsert": [
                {"id": "shown", "from": "a", "to": "b", "kind": "road"},
                {"id": "secret", "from": "a", "to": "b", "kind": "secret", "hidden": True},
            ],
        },
    )

    public = public_region_map(merged)

    assert public is not None
    assert [edge["id"] for edge in public["edges"]] == ["shown"]


# ─────────────────────────── build_seed_region_map (N3) ──────────────────────


def test_build_seed_region_map_links_start_to_rumored_endpoint() -> None:
    seed = build_seed_region_map("Oasis d'Émeraude", ENDPOINT)

    assert seed is not None
    nodes = {n["id"]: n for n in seed["nodes"]}
    assert len(nodes) == 2
    start = next(n for n in seed["nodes"] if n["status"] == "current")
    endpoint = next(n for n in seed["nodes"] if n["status"] == "rumored")
    assert start["name"] == "Oasis d'Émeraude"
    assert endpoint["name"] == "Les Profondeurs noyées"
    assert endpoint["kind"] == "dungeon"
    # current_node_id pointe sur le départ → nearby_map_nodes peut router.
    assert seed["current_node_id"] == start["id"]
    # Distinct ids ET positions distinctes (pas de carte dégénérée 1-nœud).
    assert start["id"] != endpoint["id"]
    assert start["position"] != endpoint["position"]
    # Une seule arête, VISIBLE (le choix design : piste flou mais visible).
    assert len(seed["edges"]) == 1
    edge = seed["edges"][0]
    assert edge["from"] == start["id"]
    assert edge["to"] == endpoint["id"]
    assert edge.get("hidden", False) is False


def test_build_seed_region_map_returns_none_without_endpoint() -> None:
    assert build_seed_region_map("Oasis", None) is None
    assert build_seed_region_map("Oasis", {}) is None
    assert build_seed_region_map("Oasis", {"kind": "dungeon", "hint": "x"}) is None


def test_build_seed_region_map_defaults_unknown_kind_and_start() -> None:
    seed = build_seed_region_map(None, {"name": "Le Sanctuaire", "kind": "spaceship"})
    assert seed is not None
    endpoint = next(n for n in seed["nodes"] if n["status"] == "rumored")
    start = next(n for n in seed["nodes"] if n["status"] == "current")
    assert endpoint["kind"] == "landmark"  # genre inconnu → fallback
    assert start["name"] == "Point de départ"  # nom de départ manquant → générique


def test_build_seed_region_map_keeps_distinct_ids_when_names_collide() -> None:
    seed = build_seed_region_map("La Source", {"name": "La Source", "kind": "wilderness"})
    assert seed is not None
    ids = [n["id"] for n in seed["nodes"]]
    assert len(set(ids)) == 2  # pas d'auto-arête / nœud unique


def test_seed_endpoint_visible_to_player_as_lead() -> None:
    """Option A : le joueur voit la piste (arête visible), via public_region_map."""
    seed = build_seed_region_map("Oasis", ENDPOINT)
    public = public_region_map(seed)

    assert public is not None
    # L'arête visible survit → le joueur a une direction (nom flou, non-spoiler).
    assert len(public["edges"]) == 1
    assert any(n["status"] == "rumored" for n in public["nodes"])


def test_seed_endpoint_reaches_gm_through_compacted_context() -> None:
    """Le contexte carte du MJ passe par compact_map_context : l'arête doit survivre."""
    seed = build_seed_region_map("Oasis", ENDPOINT)
    compacted = compact_map_context(seed, {}, None)

    region = compacted["region_map"]
    assert region is not None
    # L'arête (visible) survit à la compaction → nearby_map_nodes la verra côté MJ.
    assert len(region["edges"]) == 1
    assert region["current_node_id"] == seed["current_node_id"]
