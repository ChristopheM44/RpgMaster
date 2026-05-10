"""Pure campaign map merge/projection helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import ValidationError

from app.schemas.map import (
    CityMap,
    CityMapPatch,
    MapEdge,
    MapNode,
    NodeStatusPatch,
    RegionMap,
    RegionMapPatch,
)


class MapPatchError(ValueError):
    """Raised when a map patch would leave the graph inconsistent."""


def merge_region_map_patch(
    existing: dict[str, Any] | None,
    patch_data: dict[str, Any],
) -> dict[str, Any]:
    patch = _validate_region_patch(patch_data)
    existing_map = _coerce_region_map(existing)

    nodes = _merge_nodes(existing_map.nodes, patch.nodes_upsert, patch.nodes_remove)
    edges = _merge_edges(existing_map.edges, patch.edges_upsert, patch.edges_remove, nodes)
    current_node_id = patch.current_node_id
    if current_node_id is None:
        current_node_id = existing_map.current_node_id
    current_node_id = _valid_current_node_id(current_node_id, nodes)

    merged = RegionMap(
        id=patch.id or existing_map.id or "region",
        name=patch.name or existing_map.name or "Région",
        current_node_id=current_node_id,
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        background_seed=patch.background_seed or existing_map.background_seed,
        updated_at=_now_iso(),
    )
    return _dump(merged)


def merge_city_map_patch(
    existing: dict[str, Any] | None,
    patch_data: dict[str, Any],
) -> dict[str, Any]:
    patch = _validate_city_patch(patch_data)
    existing_map = _coerce_city_map(existing, patch.city_id, patch.region_node_id, patch.name)

    nodes = _merge_nodes(existing_map.nodes, patch.nodes_upsert, patch.nodes_remove)
    edges = _merge_edges(existing_map.edges, patch.edges_upsert, patch.edges_remove, nodes)
    current_node_id = patch.current_node_id
    if current_node_id is None:
        current_node_id = existing_map.current_node_id
    current_node_id = _valid_current_node_id(current_node_id, nodes)

    merged = CityMap(
        id=patch.city_id,
        region_node_id=patch.region_node_id,
        name=patch.name or existing_map.name or "Ville",
        current_node_id=current_node_id,
        nodes=list(nodes.values()),
        edges=list(edges.values()),
        background_seed=patch.background_seed or existing_map.background_seed,
        updated_at=_now_iso(),
    )
    return _dump(merged)


def update_region_node_status(
    existing: dict[str, Any] | None,
    patch_data: dict[str, Any],
) -> dict[str, Any]:
    patch = NodeStatusPatch.model_validate(patch_data)
    region_map = _coerce_region_map(existing)
    nodes = _update_node_status(region_map.nodes, patch.node_id, patch.status)
    merged = RegionMap(
        id=region_map.id,
        name=region_map.name,
        current_node_id=region_map.current_node_id,
        nodes=nodes,
        edges=region_map.edges,
        background_seed=region_map.background_seed,
        updated_at=_now_iso(),
    )
    return _dump(merged)


def update_city_node_status(
    existing: dict[str, Any] | None,
    patch_data: dict[str, Any],
) -> dict[str, Any]:
    patch = NodeStatusPatch.model_validate(patch_data)
    if not patch.city_id:
        raise MapPatchError("city_id is required for city node_status_update.")
    city_map = _coerce_city_map(existing, patch.city_id, "", None)
    nodes = _update_node_status(city_map.nodes, patch.node_id, patch.status)
    merged = CityMap(
        id=city_map.id,
        region_node_id=city_map.region_node_id,
        name=city_map.name,
        current_node_id=city_map.current_node_id,
        nodes=nodes,
        edges=city_map.edges,
        background_seed=city_map.background_seed,
        updated_at=_now_iso(),
    )
    return _dump(merged)


def public_region_map(region_map: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(region_map, dict):
        return None
    parsed = _coerce_region_map(region_map)
    return _dump(parsed.model_copy(update={"edges": [e for e in parsed.edges if not e.hidden]}))


def public_city_map(city_map: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(city_map, dict):
        return None
    parsed = _coerce_city_map(city_map, str(city_map.get("id") or "city"), "", None)
    return _dump(parsed.model_copy(update={"edges": [e for e in parsed.edges if not e.hidden]}))


def public_city_maps(city_maps: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(city_maps, dict):
        return {}
    public: dict[str, dict[str, Any]] = {}
    for city_id, city_map in city_maps.items():
        projected = public_city_map(city_map)
        if projected:
            public[str(city_id)] = projected
    return public


def compact_map_context(
    region_map: dict[str, Any] | None,
    city_maps: dict[str, Any] | None,
    active_city_id: str | None,
) -> dict[str, Any]:
    region = public_region_map(region_map)
    cities = public_city_maps(city_maps)
    return {
        "region_map": _compact_map(region) if region else None,
        "city_maps": {city_id: _compact_map(city) for city_id, city in cities.items()},
        "active_city_id": active_city_id,
    }


def _compact_map(map_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": map_data.get("id"),
        "name": map_data.get("name"),
        "current_node_id": map_data.get("current_node_id"),
        "nodes": [
            {
                "id": node.get("id"),
                "name": node.get("name"),
                "kind": node.get("kind"),
                "status": node.get("status"),
                "city_id": node.get("city_id"),
            }
            for node in map_data.get("nodes", [])
        ],
        "edges": [
            {
                "id": edge.get("id"),
                "from": edge.get("from"),
                "to": edge.get("to"),
                "kind": edge.get("kind"),
            }
            for edge in map_data.get("edges", [])
        ],
    }


def _validate_region_patch(patch_data: dict[str, Any]) -> RegionMapPatch:
    try:
        return RegionMapPatch.model_validate(patch_data)
    except ValidationError as exc:
        raise MapPatchError(str(exc)) from exc


def _validate_city_patch(patch_data: dict[str, Any]) -> CityMapPatch:
    try:
        return CityMapPatch.model_validate(patch_data)
    except ValidationError as exc:
        raise MapPatchError(str(exc)) from exc


def _coerce_region_map(existing: dict[str, Any] | None) -> RegionMap:
    raw = existing if isinstance(existing, dict) else {}
    return RegionMap.model_validate({
        "id": raw.get("id") or "region",
        "name": raw.get("name") or "Région",
        "current_node_id": raw.get("current_node_id"),
        "nodes": raw.get("nodes") or [],
        "edges": raw.get("edges") or [],
        "background_seed": raw.get("background_seed"),
        "updated_at": raw.get("updated_at") or _now_iso(),
    })


def _coerce_city_map(
    existing: dict[str, Any] | None,
    city_id: str,
    region_node_id: str,
    name: str | None,
) -> CityMap:
    raw = existing if isinstance(existing, dict) else {}
    return CityMap.model_validate({
        "id": raw.get("id") or city_id,
        "region_node_id": raw.get("region_node_id") or region_node_id,
        "name": raw.get("name") or name or "Ville",
        "current_node_id": raw.get("current_node_id"),
        "nodes": raw.get("nodes") or [],
        "edges": raw.get("edges") or [],
        "background_seed": raw.get("background_seed"),
        "updated_at": raw.get("updated_at") or _now_iso(),
    })


def _merge_nodes(
    existing_nodes: list[MapNode],
    upserts: list[MapNode],
    remove_ids: list[str],
) -> dict[str, MapNode]:
    removed = {node_id for node_id in remove_ids if node_id}
    nodes = {node.id: node for node in existing_nodes if node.id not in removed}
    for node in upserts:
        nodes[node.id] = node
    if len(nodes) > 64:
        raise MapPatchError("A map cannot contain more than 64 nodes.")
    return nodes


def _merge_edges(
    existing_edges: list[MapEdge],
    upserts: list[MapEdge],
    remove_ids: list[str],
    nodes: dict[str, MapNode],
) -> dict[str, MapEdge]:
    node_ids = set(nodes)
    explicit_removed = {edge_id for edge_id in remove_ids if edge_id}
    edges = {
        edge.id: edge
        for edge in existing_edges
        if edge.id not in explicit_removed
        and edge.from_ in node_ids
        and edge.to in node_ids
    }
    for edge in upserts:
        if edge.from_ not in node_ids or edge.to not in node_ids:
            raise MapPatchError(
                f"Edge '{edge.id}' references unknown node(s): {edge.from_}, {edge.to}."
            )
        edges[edge.id] = edge
    if len(edges) > 128:
        raise MapPatchError("A map cannot contain more than 128 edges.")
    return edges


def _valid_current_node_id(current_node_id: str | None, nodes: dict[str, MapNode]) -> str | None:
    if current_node_id and current_node_id in nodes:
        return current_node_id
    return None


def _update_node_status(
    nodes: list[MapNode],
    node_id: str,
    status: str,
) -> list[MapNode]:
    updated: list[MapNode] = []
    found = False
    for node in nodes:
        if node.id == node_id:
            updated.append(node.model_copy(update={"status": status}))
            found = True
        else:
            updated.append(node)
    if not found:
        raise MapPatchError(f"Node '{node_id}' not found.")
    return updated


def _dump(model: RegionMap | CityMap) -> dict[str, Any]:
    return model.model_dump(mode="json", by_alias=True, exclude_none=True)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
