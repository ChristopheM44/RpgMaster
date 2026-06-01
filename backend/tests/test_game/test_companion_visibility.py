"""A1 regression — companion anonymization derives from npc_states.

The leak: an NPC introduced mid-scene via ``scene_update`` had its real name on
the scene POI while only ``npc_states[id]`` was flagged ``known_to_party=False``.
The companion-visible filter trusted the POI's own (absent) flag and exposed the
real name. Fix: ``npc_states[id].known_to_party`` is the single source of truth.
"""
from __future__ import annotations

from app.game.companion_visibility import companion_visible_game_state
from app.game.scene_state_service import apply_scene_update
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus


def test_companion_anonymizes_poi_from_npc_states() -> None:
    """POI without known_to_party + npc_states unknown → POI anonymized."""
    state = {
        "current_scene": {
            "pois": [
                {
                    "id": "npc_stranger",
                    "name": "Vex la Contrebandière",
                    "kind": "npc",
                    "description": "une silhouette encapuchonnée",
                    # No known_to_party on the POI (the scene_update path)
                },
            ],
        },
        "npc_states": {
            "npc_stranger": {
                "name": "Vex la Contrebandière",
                "description": "une silhouette encapuchonnée",
                "known_to_party": False,
            },
        },
    }
    visible = companion_visible_game_state(state)
    poi = visible["current_scene"]["pois"][0]
    assert poi["name"] == "une silhouette encapuchonnée"
    assert "id" not in poi
    assert visible["npc_states"]["npc_stranger"]["name"] == "une silhouette encapuchonnée"


def test_companion_npc_states_overrides_stale_poi_flag() -> None:
    """npc_states[id].known_to_party is authoritative over a stale POI flag."""
    state = {
        "current_scene": {
            "pois": [
                {
                    "id": "npc_x",
                    "name": "Maître Orlin",
                    "kind": "npc",
                    "description": "un vieil érudit",
                    "known_to_party": True,  # stale: POI claims known...
                },
            ],
        },
        "npc_states": {
            "npc_x": {"name": "Maître Orlin", "known_to_party": False},  # ...truth: unknown
        },
    }
    visible = companion_visible_game_state(state)
    assert visible["current_scene"]["pois"][0]["name"] == "un vieil érudit"


def test_companion_keeps_known_npc_visible() -> None:
    """A PNJ marked known_to_party in npc_states stays named for companions."""
    state = {
        "current_scene": {
            "pois": [{"id": "npc_ally", "name": "Aldric", "kind": "npc"}],
        },
        "npc_states": {"npc_ally": {"name": "Aldric", "known_to_party": True}},
    }
    visible = companion_visible_game_state(state)
    assert visible["current_scene"]["pois"][0]["name"] == "Aldric"


def test_scene_update_propagates_known_to_party_then_anonymizes() -> None:
    """A1bis end-to-end: GM introduces an unknown NPC via scene_update, and the
    companion view anonymizes it both in npc_states and in current_scene.pois."""
    active = ActiveSession(
        session_id="s1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "current_scene": {"cols": 12, "rows": 12, "pois": [], "exits": []},
        },
    )
    apply_scene_update(
        active,
        {
            "npc_updates": [
                {
                    "id": "npc_mystery",
                    "name": "Dame Saphir",
                    "status": "present",
                    "position": {"col": 4, "row": 4},
                    "known_to_party": False,
                    "note": "une voyageuse au capuchon bleu",
                }
            ]
        },
    )
    # The POI now carries the authoritative flag (A1bis).
    poi = next(p for p in active.state_data["current_scene"]["pois"] if p["id"] == "npc_mystery")
    assert poi["known_to_party"] is False

    visible = companion_visible_game_state(active.state_data)
    visible_poi = visible["current_scene"]["pois"][0]
    assert visible_poi["name"] != "Dame Saphir"
    assert visible["npc_states"]["npc_mystery"]["name"] != "Dame Saphir"
