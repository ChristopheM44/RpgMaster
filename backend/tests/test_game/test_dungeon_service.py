from __future__ import annotations

import pytest

from app.agents.schemas import AgentResponse, GMAction, GMResponse
from app.game.action_pipeline import ActionPipeline, ActionRequest
from app.game.event_bus import EventType
from app.game.gm_response_executor import GMResponseExecutor
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus
from app.services import dungeon_service


def _active() -> ActiveSession:
    return ActiveSession(
        session_id="dungeon-session",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "phase": "exploration",
            "characters": {
                "hero": {
                    "name": "Aria",
                    "level": 1,
                    "hp": 12,
                    "hp_max": 12,
                    "dex": 12,
                    "equipment": [],
                }
            },
            "campaign_context": {
                "active_chapter": {
                    "id": "chapter_1",
                    "possible_srd_encounters": ["goblin"],
                    "possible_custom_encounters": [],
                },
                "custom_monsters": [],
            },
            "world_maps": {"region_map": None, "city_maps": {}, "active_city_id": None},
        },
    )


def _config() -> dict:
    return {
        "seed": "chronicle:chapter_1",
        "params": {"size": "small", "theme": "crypt", "branchiness": 0.25},
        "endpoint_node_id": "la_crypte",
        "name": "La Crypte",
    }


def test_ensure_dungeon_city_map_is_idempotent() -> None:
    active = _active()

    first, first_bp = dungeon_service.ensure_dungeon_city_map(active, _config())
    second, second_bp = dungeon_service.ensure_dungeon_city_map(active, _config())

    assert first == second
    assert first_bp.to_dict() == second_bp.to_dict()
    assert active.state_data["world_maps"]["active_city_id"] == first_bp.id
    assert active.state_data["world_maps"]["active_dungeon_id"] == first_bp.id
    assert active.state_data["dungeon_runtime"][first_bp.id]["current_room_id"] == (
        first_bp.entry_room_id
    )


def test_cleared_room_does_not_repopulate_on_backtrack() -> None:
    active = _active()
    _, bp = dungeon_service.ensure_dungeon_city_map(active, _config())

    scene = dungeon_service.transition_to_room(active, bp.id, "room_01_chamber")

    assert scene["scene_id"] == "room_01_chamber"
    assert active.state_data["pending_phase_transition"] == "COMBAT"
    assert active.state_data["pending_encounter"]["monster_ids"] == ["goblin"]

    assert dungeon_service.mark_room_cleared(active) is True
    assert active.state_data["dungeon_runtime"][bp.id]["rooms"]["room_01_chamber"]["cleared"]

    dungeon_service.transition_to_room(active, bp.id, bp.entry_room_id)
    scene_again = dungeon_service.transition_to_room(active, bp.id, "room_01_chamber")

    assert scene_again["state"] == "cleared"
    assert "pending_encounter" not in active.state_data
    assert "pending_phase_transition" not in active.state_data


def test_action_pipeline_dungeon_transition_only_when_active_and_adjacent() -> None:
    inactive = _active()
    request = ActionRequest(
        session_id="dungeon-session",
        action_type="free_text",
        content="Nous allons vers la salle de garde.",
        travel_intent={
            "is_travel": True,
            "destination": "salle de garde",
            "destination_node_id": "room_01_chamber",
        },
    )
    untouched = ActionPipeline._with_dungeon_room_transition(
        AgentResponse(content="D'accord.", actions=[]),
        request,
        inactive,
    )
    assert untouched.actions == []

    active = _active()
    _, bp = dungeon_service.ensure_dungeon_city_map(active, _config())
    moved = ActionPipeline._with_dungeon_room_transition(
        AgentResponse(content="D'accord.", actions=[]),
        request,
        active,
    )
    assert moved.actions[0].type == "scene_layout"
    assert moved.actions[0].params["scene_id"] == "room_01_chamber"
    assert active.state_data["dungeon_runtime"][bp.id]["current_room_id"] == "room_01_chamber"

    blocked = ActionPipeline._with_dungeon_room_transition(
        AgentResponse(content="D'accord.", actions=[]),
        ActionRequest(
            session_id="dungeon-session",
            action_type="free_text",
            travel_intent={
                "is_travel": True,
                "destination": "antre",
                "destination_node_id": "room_03_lair",
            },
        ),
        _active_with_entry_dungeon(),
    )
    assert blocked.actions == []


@pytest.mark.asyncio
async def test_executor_enters_dungeon_when_region_endpoint_becomes_current() -> None:
    active = _active()
    active.state_data["world_maps"]["region_map"] = {
        "id": "region",
        "name": "Région",
        "current_node_id": "camp",
        "nodes": [
            {
                "id": "camp",
                "name": "Camp",
                "kind": "settlement",
                "position": {"x": 20, "y": 50},
                "status": "visited",
            },
            {
                "id": "la_crypte",
                "name": "La Crypte",
                "kind": "dungeon",
                "position": {"x": 70, "y": 40},
                "status": "known",
            },
        ],
        "edges": [{"id": "route", "from": "camp", "to": "la_crypte", "kind": "path"}],
        "updated_at": "1970-01-01T00:00:00+00:00",
    }
    active.state_data["dungeons"] = {"crypt": _config()}
    bus = _FakeBus()
    executor = GMResponseExecutor(bus)

    await executor.execute_gm_response(
        GMResponse(
            narration="Vous atteignez la crypte.",
            actions=[
                GMAction(
                    type="node_status_update",
                    params={"scope": "region", "node_id": "la_crypte", "status": "current"},
                )
            ],
        ),
        active,
        db=None,
        session_id="dungeon-session",
    )

    event_types = [event_type for event_type, _ in bus.published]
    assert EventType.CITY_MAP_UPDATED in event_types
    assert EventType.SCENE_LAYOUT_CHANGED in event_types
    assert active.state_data["current_scene"]["scene_id"] == "room_00_gateway"
    assert active.state_data["world_maps"]["active_dungeon_id"]


def _active_with_entry_dungeon() -> ActiveSession:
    active = _active()
    dungeon_service.ensure_dungeon_city_map(active, _config())
    return active


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[EventType, dict]] = []

    async def publish_to_session(self, session_id, event_type, payload, source=None):
        self.published.append((event_type, payload))
