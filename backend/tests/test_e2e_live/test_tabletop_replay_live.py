"""Live LLM replay tests for tabletop-fidelity invariants.

These tests intentionally do not mock the LLM. If the configured provider is
unavailable, the suite fails through the normal ERROR event path.
"""
from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

import pytest

from app.agents.gm_agent import _FALLBACK_NARRATION, GMAgent
from app.game.action_pipeline import ActionPipeline, ActionRequest
from app.game.event_bus import EventType
from app.game.session_manager import ActiveSession
from app.game.travel_detection import detect_travel_intent, travel_intent_as_dict
from app.models.session import SessionStatus

SESSION_ID = "live-tabletop-replay"


class _CollectBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def publish_to_session(self, session_id, event_type, payload, source=None):
        self.events.append((event_type, payload))


def _base_state() -> dict[str, Any]:
    return {
        "characters": {
            "thorvald": {
                "name": "Thorvald",
                "level": 1,
                "is_ai": False,
                "ability_scores": {"int": 12, "wis": 12, "cha": 10},
            },
            "elara": {"name": "Elara", "is_ai": True, "class_name": "Wizard"},
            "solana": {"name": "Solana", "is_ai": True, "class_name": "Cleric"},
        },
        "adventure_journal": {
            "location_region": "Désert d'Akhdar",
            "location_place": "Oasis corrompue",
            "time_of_day": "afternoon",
            "day_number": 3,
            "weather": "Chaleur sèche",
        },
        "current_scene": {
            "scene_id": "oasis_corrompue",
            "cols": 12,
            "rows": 12,
            "cell_size_m": 1.5,
            "terrain": "oasis_corrompue",
            "scene_theme": "desert",
            "description": "Une oasis basse, noircie par endroits, où l'eau dort sans reflet.",
            "pois": [
                {
                    "id": "bassin_noir",
                    "name": "Bassin noir",
                    "kind": "hazard",
                    "icon": "trap-danger",
                    "position": {"col": 5, "row": 5},
                    "description": "L'eau sombre frissonne malgré l'absence de vent.",
                    "physical_state": "eau opaque, surface huileuse",
                    "interactions": [
                        {
                            "id": "examine_surface",
                            "label": "Observer",
                            "intent": "examine",
                            "mechanics": {
                                "safe_observation": True,
                                "reveal_tier": "surface",
                            },
                        }
                    ],
                },
                {
                    "id": "journal_cache",
                    "name": "Journal caché",
                    "kind": "clue",
                    "icon": "clue",
                    "position": {"col": 7, "row": 6},
                    "description": "Une dalle plus claire dépasse entre les roseaux secs.",
                    "visibility": "hidden",
                    "discovered": False,
                    "interactions": [
                        {
                            "id": "search_journal",
                            "label": "Fouiller",
                            "intent": "search",
                            "mechanics": {
                                "roll": {
                                    "type": "check",
                                    "ability": "int",
                                    "skill": "Investigation",
                                    "dc": 1,
                                    "reason": "trouver l'objet caché",
                                },
                                "safe_observation": True,
                                "reveal_tier": "deep",
                            },
                        },
                        {
                            "id": "fail_search",
                            "label": "Inspecter vite",
                            "intent": "search",
                            "mechanics": {
                                "roll": {
                                    "type": "check",
                                    "ability": "int",
                                    "skill": "Investigation",
                                    "dc": 99,
                                    "reason": "comprendre les traces brouillées",
                                },
                                "safe_observation": True,
                                "reveal_tier": "interpreted",
                            },
                        },
                    ],
                },
            ],
            "exits": [
                {
                    "id": "vers_dunes",
                    "label": "Dunes basses",
                    "position": {"col": 11, "row": 7},
                    "leads_to": "dunes_basses",
                }
            ],
            "party_positions": {
                "thorvald": {"col": 5, "row": 7},
                "elara": {"col": 4, "row": 7},
                "solana": {"col": 5, "row": 8},
            },
        },
        "npc_states": {
            "khalid_guide": {
                "name": "Khalid le Guide",
                "status": "missing",
                "last_location": "",
                "known_to_party": True,
                "notes": ["Ses traces cessent près du bassin."],
            }
        },
    }


SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "oasis_corrompue",
        "content": "J'observe l'eau noire et les roseaux sans rien toucher.",
    },
    {
        "id": "disparition_guide",
        "content": "J'appelle Khalid et je cherche des traces autour du bassin.",
    },
    {
        "id": "objet_cache",
        "content": "Je fouille près de la dalle claire pour trouver ce qui est caché.",
        "scene_poi_id": "journal_cache",
        "scene_interaction_id": "search_journal",
        "expect_roll": True,
        "expect_scene_update": True,
    },
    {
        "id": "discussion_compagnons",
        "content": "Elara, Solana, je veux vos avis : on fouille la dalle ou on suit les traces ?",
    },
    {
        "id": "echec_investigation",
        "content": "J'inspecte rapidement les traces brouillées près de la dalle.",
        "scene_poi_id": "journal_cache",
        "scene_interaction_id": "fail_search",
        "expect_roll": True,
        "expect_failure": True,
        "expect_scene_update": True,
    },
]


@pytest.mark.live_llm
async def test_live_llm_provider_responds_with_structured_gm_json() -> None:
    response = await GMAgent().narrate(
        game_state=_base_state(),
        player_action="Décris seulement l'ambiance immédiate de l'oasis.",
    )

    assert response.narration != _FALLBACK_NARRATION, (
        "Le LLM configuré ne répond pas : les replays live doivent échouer explicitement."
    )
    assert response.narration.strip()


@pytest.mark.live_llm
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[scenario["id"] for scenario in SCENARIOS])
async def test_live_llm_tabletop_replay_scenario(scenario: dict[str, Any]) -> None:
    active = ActiveSession(
        session_id=SESSION_ID,
        phase=SessionStatus.EXPLORATION,
        state_data=deepcopy(_base_state()),
    )
    bus = _CollectBus()
    pipeline = ActionPipeline(GMAgent(), bus)

    await pipeline.resolve_and_publish(
        ActionRequest(
            session_id=SESSION_ID,
            actor_id="thorvald",
            actor_name="Thorvald",
            actor_kind="player",
            action_type="free_text",
            content=scenario["content"],
            target_id=None,
            scene_poi_id=scenario.get("scene_poi_id"),
            scene_interaction_id=scenario.get("scene_interaction_id"),
        ),
        active,
        db=None,
    )

    errors = [payload for event_type, payload in bus.events if event_type == EventType.ERROR]
    assert not errors, f"{scenario['id']} a produit une erreur système live LLM : {errors!r}"

    visible_text = "\n".join(
        str(payload.get("text") or payload.get("message") or "")
        for event_type, payload in bus.events
        if event_type in {EventType.NARRATION, EventType.DIALOGUE, EventType.ERROR}
    )
    assert visible_text.strip(), f"{scenario['id']} n'a produit aucune sortie visible."
    assert not _contains_diegetic_llm_error(visible_text)
    assert isinstance(active.state_data.get("current_scene"), dict)

    if scenario.get("expect_roll"):
        rolls = [
            payload
            for event_type, payload in bus.events
            if event_type == EventType.ROLL_RESULT
        ]
        assert rolls, f"{scenario['id']} devait résoudre un jet mécanique."
        roll = rolls[-1]
        assert roll["actor_id"] == "thorvald"
        assert roll["actor_name"] == "Thorvald"
        assert roll["actor_kind"] == "player"
        assert roll["scene_poi_id"] == scenario["scene_poi_id"]
        assert roll["dc"] is not None
        assert roll["margin"] == roll["total"] - roll["dc"]
        if scenario.get("expect_failure"):
            assert roll["success"] is False

    if scenario.get("expect_scene_update"):
        scene_events = [
            payload
            for event_type, payload in bus.events
            if event_type == EventType.SCENE_LAYOUT_CHANGED
        ]
        assert scene_events, f"{scenario['id']} devait publier une scène mise à jour."

    if scenario["id"] == "disparition_guide":
        khalid_dialogue = [
            payload
            for event_type, payload in bus.events
            if event_type == EventType.DIALOGUE and payload.get("speaker") == "Khalid le Guide"
        ]
        assert not khalid_dialogue

    assert _wrong_actor_discovery(visible_text) is None


def _contains_diegetic_llm_error(text: str) -> bool:
    lowered = text.casefold()
    markers = (
        "ollama",
        "provider llm",
        "serveur llm",
        "service ia indisponible",
        "n'a pas pu répondre",
        "injoignable",
    )
    return any(marker in lowered for marker in markers)


def _wrong_actor_discovery(text: str) -> str | None:
    if "Thorvald".casefold() in text.casefold():
        return None
    pattern = re.compile(
        r"\b(Elara|Solana)\b[^.!?\n]*(découvre|decouvre|trouve|repère|repere|comprend)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    return match.group(1) if match else None


def _travel_state() -> dict[str, Any]:
    """Party on the amber trail with Khalid *accompanying*, an exit to the oasis."""
    return {
        "characters": {
            "thorvald": {
                "name": "Thorvald",
                "level": 1,
                "is_ai": False,
                "ability_scores": {"int": 12, "wis": 12, "cha": 10},
            },
            "elara": {"name": "Elara", "is_ai": True, "class_name": "Wizard"},
        },
        "adventure_journal": {
            "location_region": "Désert d'Akhdar",
            "location_place": "Piste d'Ambre",
            "time_of_day": "morning",
            "day_number": 1,
            "weather": "Chaleur sèche",
        },
        "current_scene": {
            "scene_id": "piste_ambre",
            "cols": 12,
            "rows": 12,
            "cell_size_m": 1.5,
            "terrain": "desert",
            "scene_theme": "desert",
            "description": "Une piste de sable bordée de carcasses desséchées de chameaux.",
            "pois": [
                {
                    "id": "khalid_guide",
                    "name": "Khalid le Guide",
                    "kind": "npc",
                    "icon": "npc",
                    "position": {"col": 5, "row": 6},
                    "known_to_party": True,
                }
            ],
            "exits": [
                {
                    "id": "vers_oasis",
                    "label": "Oasis d'Émeraude",
                    "position": {"col": 11, "row": 6},
                    "leads_to": "oasis_emeraude",
                }
            ],
            "party_positions": {
                "thorvald": {"col": 5, "row": 7},
                "elara": {"col": 4, "row": 7},
            },
        },
        "npc_states": {
            "khalid_guide": {
                "name": "Khalid le Guide",
                "status": "present",
                "disposition": "accompanying",
                "known_to_party": True,
                "last_location": "piste_ambre",
            }
        },
    }


@pytest.mark.live_llm
async def test_live_llm_guide_survives_travel_transition() -> None:
    """P1+P2 acceptance: an imperative travel phrase moves the scene, and the
    accompanying guide is carried across the transition rather than vanishing.

    Holds regardless of LLM whim: the deterministic travel fallback guarantees a
    SCENE_LAYOUT_CHANGED, and carry_accompanying_npcs guarantees the guide stays.
    """
    active = ActiveSession(
        session_id=SESSION_ID,
        phase=SessionStatus.EXPLORATION,
        state_data=deepcopy(_travel_state()),
    )
    bus = _CollectBus()
    pipeline = ActionPipeline(GMAgent(), bus)

    content = "Très bien, rendons-nous à l'oasis d'Émeraude, ouvrez la route Khalid."
    travel = travel_intent_as_dict(detect_travel_intent(content, active.state_data))
    assert travel and travel["is_travel"], "le marqueur impératif doit être détecté"

    await pipeline.resolve_and_publish(
        ActionRequest(
            session_id=SESSION_ID,
            actor_id="thorvald",
            actor_name="Thorvald",
            actor_kind="player",
            action_type="free_text",
            content=content,
            travel_intent=travel,
        ),
        active,
        db=None,
    )

    errors = [payload for event_type, payload in bus.events if event_type == EventType.ERROR]
    assert not errors, f"erreur système live LLM : {errors!r}"

    # Acceptance #2 — the imperative travel produced a real scene change.
    scene_changes = [
        payload for event_type, payload in bus.events
        if event_type == EventType.SCENE_LAYOUT_CHANGED
    ]
    assert scene_changes, "le voyage (« rendons-nous à… ») doit publier une nouvelle scène"

    # Acceptance #1 — the guide is carried, never frozen as "missing" in canon.
    khalid = active.state_data["npc_states"]["khalid_guide"]
    assert khalid["status"] == "present", "le guide ne doit pas disparaître au voyage"
    scene = active.state_data["current_scene"]
    assert any(p.get("id") == "khalid_guide" for p in scene.get("pois", []) or []), (
        "le guide doit rester un POI visible dans la nouvelle scène"
    )
