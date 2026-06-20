"""Tests d'intégration — action `scene_request` via GMResponseExecutor.

`scene_request` décrit l'INTENTION d'une scène (thème, features, exits) ;
``scene_builder.build_scene`` calcule ensuite la géométrie 12x12. Ces tests
vérifient le câblage complet : validation `SceneSpec`, repli déterministe sur
`_fallback_scene_spec` si les params sont invalides, et publication des
événements attendus par le frontend.
"""

from __future__ import annotations

from app.agents.schemas import AgentResponse, GMAction
from app.game.action_pipeline import ActionPipeline, ActionRequest
from app.game.event_bus import EventType
from app.game.gm_response_executor import GMResponseExecutor
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus

SESSION_ID = "test-scene-request"


class _FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[EventType, dict]] = []

    async def publish_to_session(self, session_id, event_type, payload, source=None):
        self.published.append((event_type, payload))


async def test_executor_scene_request_builds_canonical_scene_and_publishes() -> None:
    active = ActiveSession(
        session_id=SESSION_ID,
        phase=SessionStatus.EXPLORATION,
        state_data={"adventure_journal": {"location_place": "Bois de Lone"}},
    )
    bus = _FakeBus()
    executor = GMResponseExecutor(bus)

    response = AgentResponse(
        content="La clairière s'ouvre devant vous.",
        actions=[
            GMAction(
                type="scene_request",
                params={
                    "theme": "forest",
                    "size": "medium",
                    "enclosure": "exterior",
                    "description": "Une clairière baignée de lumière.",
                    "features": [
                        {"kind": "cover", "name": "Rocher moussu", "zone": "nw"},
                        {"kind": "hazard", "name": "Ronces épaisses", "zone": "se"},
                        {"kind": "npc", "name": "Éclaireuse elfe", "zone": "east"},
                    ],
                    "exits": [
                        {
                            "label": "Sentier vers le campement",
                            "direction": "south",
                            "leads_to": "campement_1",
                        }
                    ],
                    "tactical_intent": "Embuscade possible depuis les ronces.",
                },
            )
        ],
    )

    await executor.execute_gm_response(
        response, active, session_id=SESSION_ID, fallback_actor_id="hero_1"
    )

    scene = active.state_data["current_scene"]
    assert scene["cols"] == 12
    assert scene["rows"] == 12
    assert scene["scene_theme"] == "forest"

    pois_by_kind = {poi["kind"]: poi for poi in scene["pois"]}
    assert "cover" in pois_by_kind
    assert "hazard" in pois_by_kind
    assert "npc" in pois_by_kind

    npc_poi = pois_by_kind["npc"]
    assert "talk" in {interaction["intent"] for interaction in npc_poi["interactions"]}

    assert scene["exits"][0]["leads_to"] == "campement_1"

    scene_events = [
        payload for event, payload in bus.published if event == EventType.SCENE_LAYOUT_CHANGED
    ]
    assert scene_events[-1]["scene"] == scene


async def test_executor_scene_request_invalid_params_falls_back_to_anchor() -> None:
    active = ActiveSession(
        session_id=SESSION_ID,
        phase=SessionStatus.EXPLORATION,
        state_data={
            "adventure_journal": {
                "location_place": "Auberge du Pont",
                "location_venue": "Cave à vin",
                "terrain": "cave en pierre humide",
            },
            "current_scene": {
                "cols": 12,
                "rows": 12,
                "pois": [],
                "exits": [
                    {
                        "id": "exit_escalier",
                        "label": "Escalier de pierre",
                        "leads_to": "salle_commune",
                        "description": "Remonte vers la salle commune.",
                    }
                ],
            },
        },
    )
    bus = _FakeBus()
    executor = GMResponseExecutor(bus)

    response = AgentResponse(
        content="Vous descendez dans la cave.",
        actions=[GMAction(type="scene_request", params={"theme": "forest", "features": "boom"})],
    )

    await executor.execute_gm_response(
        response, active, session_id=SESSION_ID, fallback_actor_id="hero_1"
    )

    scene = active.state_data["current_scene"]
    assert scene["scene_theme"] == "cave"
    assert any(exit_data["leads_to"] == "salle_commune" for exit_data in scene["exits"])


async def test_executor_scene_request_seed_is_stable_for_same_location() -> None:
    params = {
        "theme": "forest",
        "enclosure": "exterior",
        "features": [
            {"kind": "cover", "name": "Rocher moussu", "zone": "nw"},
            {"kind": "hazard", "name": "Ronces épaisses", "zone": "se"},
        ],
        "exits": [{"label": "Sentier", "direction": "south", "leads_to": "campement_1"}],
    }

    scenes = []
    for _ in range(2):
        active = ActiveSession(
            session_id=SESSION_ID,
            phase=SessionStatus.EXPLORATION,
            state_data={"adventure_journal": {"location_place": "Bois de Lone"}},
        )
        bus = _FakeBus()
        response = AgentResponse(
            content="...",
            actions=[GMAction(type="scene_request", params=params)],
        )
        await GMResponseExecutor(bus).execute_gm_response(
            response, active, session_id=SESSION_ID, fallback_actor_id="hero_1"
        )
        scenes.append(active.state_data["current_scene"])

    assert scenes[0]["pois"] == scenes[1]["pois"]
    assert scenes[0]["exits"] == scenes[1]["exits"]


async def test_pipeline_travel_scene_request_prevents_empty_layout_fallback() -> None:
    active = _active_for_depths_travel()
    request = _travel_request_to_depths()
    response = AgentResponse(
        content="Vous descendez sous les dalles froides.",
        actions=[
            GMAction(
                type="scene_request",
                params={
                    "theme": "dungeon",
                    "size": "medium",
                    "enclosure": "interior",
                    "description": "Un sanctuaire souterrain de pierre noire.",
                    "features": [
                        {"kind": "cover", "name": "Pilier fissuré", "zone": "west"},
                        {"kind": "clue", "name": "Autel gravé", "zone": "center"},
                    ],
                    "exits": [
                        {
                            "label": "Escalier vers la nef",
                            "direction": "south",
                            "leads_to": "nef_ancienne",
                        }
                    ],
                },
            )
        ],
    )

    guarded = ActionPipeline._with_travel_scene_fallback(response, request, active)

    assert sum(1 for action in guarded.actions if action.type == "scene_request") == 1
    assert not any(action.type == "scene_layout" for action in guarded.actions)
    journals = [action for action in guarded.actions if action.type == "journal_update"]
    assert len(journals) == 1
    assert journals[0].params["location_place"] == "Descente vers les profondeurs"

    bus = _FakeBus()
    await GMResponseExecutor(bus).execute_gm_response(
        guarded,
        active,
        session_id=SESSION_ID,
        fallback_actor_id="hero_1",
    )

    scene = active.state_data["current_scene"]
    assert scene["scene_theme"] == "dungeon"
    assert scene["exits"]
    assert any(exit_data["leads_to"] == "nef_ancienne" for exit_data in scene["exits"])
    assert active.state_data["adventure_journal"]["location_place"] == (
        "Descente vers les profondeurs"
    )


async def test_pipeline_minimal_travel_fallback_has_theme_and_return_exit() -> None:
    active = _active_for_depths_travel()
    request = _travel_request_to_depths()
    guarded = ActionPipeline._with_travel_scene_fallback(
        AgentResponse(content="Vous progressez.", actions=[]),
        request,
        active,
    )

    layouts = [action for action in guarded.actions if action.type == "scene_layout"]
    assert len(layouts) == 1
    assert layouts[0].params["scene_theme"] == "dungeon"
    assert layouts[0].params["exits"][0]["leads_to"] == "clairiere_depart"

    bus = _FakeBus()
    await GMResponseExecutor(bus).execute_gm_response(
        guarded,
        active,
        session_id=SESSION_ID,
        fallback_actor_id="hero_1",
    )

    scene = active.state_data["current_scene"]
    assert scene["scene_theme"] == "dungeon"
    assert scene["exits"]
    assert scene["exits"][0]["leads_to"] == "clairiere_depart"


def test_pipeline_journal_fallback_treats_scene_request_as_scene_move() -> None:
    active = _active_for_depths_travel()
    active.state_data["adventure_journal"] = {"location_place": "Clairière de départ"}
    response = AgentResponse(
        content="Vous descendez.",
        actions=[
            GMAction(type="scene_request", params={"theme": "dungeon"}),
            GMAction(
                type="journal_update",
                params={"location_place": "Descente vers les profondeurs"},
            ),
        ],
    )

    guarded = ActionPipeline._with_journal_scene_fallback(response, active)

    assert not any(action.type == "scene_layout" for action in guarded.actions)


def test_pipeline_dungeon_transition_treats_scene_request_as_scene_move(monkeypatch) -> None:
    from app.services import dungeon_service

    def fail_if_called(*args, **kwargs):
        raise AssertionError("dungeon fallback must not run after a scene_request")

    monkeypatch.setattr(dungeon_service, "is_room_transition", fail_if_called)
    response = AgentResponse(
        content="Vous franchissez le seuil.",
        actions=[GMAction(type="scene_request", params={"theme": "dungeon"})],
    )

    guarded = ActionPipeline._with_dungeon_room_transition(
        response,
        _travel_request_to_depths(),
        _active_for_depths_travel(),
    )

    assert guarded.actions == response.actions


def _travel_request_to_depths() -> ActionRequest:
    return ActionRequest(
        session_id=SESSION_ID,
        actor_id="hero_1",
        actor_kind="player",
        action_type="free_text",
        content="Descente vers les profondeurs",
        travel_intent={
            "is_travel": True,
            "destination": "Descente vers les profondeurs",
            "destination_node_id": "sanctuaire_profond",
            "confidence": "explicit",
        },
    )


def _active_for_depths_travel() -> ActiveSession:
    return ActiveSession(
        session_id=SESSION_ID,
        phase=SessionStatus.EXPLORATION,
        state_data={
            "adventure_journal": {"location_place": "Clairière de départ"},
            "characters": {"hero_1": {"name": "Thorvald"}},
            "current_scene": {
                "scene_id": "clairiere_depart",
                "scene_theme": "forest",
                "exits": [
                    {
                        "id": "vers_sanctuaire",
                        "label": "Descente vers les profondeurs",
                        "leads_to": "sanctuaire_profond",
                    }
                ],
            },
            "world_maps": {
                "region_map": {
                    "nodes": [
                        {
                            "id": "sanctuaire_profond",
                            "name": "Sanctuaire souterrain",
                            "kind": "dungeon",
                        }
                    ]
                }
            },
        },
    )
