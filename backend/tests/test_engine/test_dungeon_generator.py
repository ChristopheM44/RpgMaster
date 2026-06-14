from __future__ import annotations

from collections import deque

from app.engine.dungeon_generator import (
    DungeonParams,
    blueprint_to_city_map,
    generate_dungeon,
    room_scene_skeleton,
)
from app.schemas.map import CityMap
from app.services.local_map_service import enrich_scene_layout
from app.services.map_service import public_city_map


def test_generate_dungeon_is_deterministic_and_stably_ordered() -> None:
    first = generate_dungeon("chronicle:chapter_1", DungeonParams(size="medium"))
    second = generate_dungeon("chronicle:chapter_1", DungeonParams(size="medium"))

    assert first.to_dict() == second.to_dict()
    assert [room.id for room in first.rooms] == sorted(room.id for room in first.rooms)
    assert [corridor.id for corridor in first.corridors] == sorted(
        corridor.id for corridor in first.corridors
    )


def test_generate_dungeon_is_connected_and_boss_is_deepest() -> None:
    bp = generate_dungeon("deep-crypt", {"size": "large", "branchiness": 0.8})
    graph: dict[str, set[str]] = {room.id: set() for room in bp.rooms}
    for corridor in bp.corridors:
        graph[corridor.from_room].add(corridor.to_room)
        graph[corridor.to_room].add(corridor.from_room)

    seen = {bp.entry_room_id}
    queue = deque([bp.entry_room_id])
    while queue:
        current = queue.popleft()
        for nxt in graph[current]:
            if nxt not in seen:
                seen.add(nxt)
                queue.append(nxt)

    assert seen == set(graph)
    boss = next(room for room in bp.rooms if room.id == bp.boss_room_id)
    assert boss.kind == "lair"
    assert boss.depth == max(room.depth for room in bp.rooms)


def test_blueprint_to_city_map_validates_and_survives_public_projection() -> None:
    bp = generate_dungeon("crypt-map", {"size": "small"})
    city_map = blueprint_to_city_map(bp, "La Crypte du Sel")

    parsed = CityMap.model_validate(city_map)
    projected = public_city_map(parsed.model_dump(mode="json", by_alias=True))

    assert projected is not None
    assert projected["id"] == bp.id
    assert projected["current_node_id"] == bp.entry_room_id
    assert {node["kind"] for node in projected["nodes"]} >= {"gateway", "lair"}


def test_room_scene_skeleton_enriches_as_dungeon_room() -> None:
    bp = generate_dungeon("crypt-scene", {"size": "small"})
    scene = room_scene_skeleton(bp, bp.entry_room_id)

    enrich_scene_layout(scene)

    wall_ids = {element["id"] for element in scene["elements"] if element.get("kind") == "wall"}
    door_count = sum(1 for element in scene["elements"] if element.get("kind") == "door")
    asset_keys = {element.get("asset_key") for element in scene["elements"]}
    assert {"wall_north", "wall_east", "wall_south", "wall_west"} <= wall_ids
    assert door_count == len(scene["exits"])
    assert {"prop/wall", "prop/wall_corner", "prop/stairs", "prop/torch_mounted"} <= asset_keys
    assert all(
        element.get("asset_key") == "prop/door"
        for element in scene["elements"]
        if element.get("kind") == "door"
    )
    assert scene["ambiance"] == {"light": "torchlit", "fog_density": 0.25}
    assert scene["vegetation_density"] == 0.0


def test_room_scene_skeleton_adds_kaykit_presets_by_room_kind() -> None:
    bp = generate_dungeon("crypt-scene-assets", {"size": "large"})
    assets_by_kind: dict[str, set[str]] = {}

    for room in bp.rooms:
        scene = room_scene_skeleton(bp, room.id)
        assets = {
            str(element["asset_key"])
            for element in scene["elements"]
            if isinstance(element.get("asset_key"), str)
        }
        assets_by_kind.setdefault(room.kind, set()).update(assets)

    assert {"prop/stairs", "prop/rubble_large", "prop/torch_mounted"} <= assets_by_kind["gateway"]
    assert {"prop/pillar", "prop/crates_stacked"} <= assets_by_kind["chamber"]
    assert "prop/chest_gold" in assets_by_kind["vault"]
    assert {"prop/table_medium", "prop/pillar", "prop/rubble_large"} <= assets_by_kind["lair"]
