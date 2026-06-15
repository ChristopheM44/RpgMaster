"""Tests d'intégration — action `scene_request` via GMResponseExecutor.

`scene_request` décrit l'INTENTION d'une scène (thème, features, exits) ;
``scene_builder.build_scene`` calcule ensuite la géométrie 12x12. Ces tests
vérifient le câblage complet : validation `SceneSpec`, repli déterministe sur
`_fallback_scene_spec` si les params sont invalides, et publication des
événements attendus par le frontend.
"""

from __future__ import annotations

from app.agents.schemas import AgentResponse, GMAction
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
