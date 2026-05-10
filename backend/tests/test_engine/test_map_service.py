import pytest

from app.services.map_service import (
    MapPatchError,
    merge_city_map_patch,
    merge_region_map_patch,
    public_region_map,
)


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
