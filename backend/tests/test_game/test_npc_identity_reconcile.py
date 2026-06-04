"""A4 — npc_states[id] is the single identity authority; the POI is a projection.

reconcile_scene_npcs() runs after every scene write (scene_layout via
gm_response_executor, scene_update via apply_scene_update) and keeps the scene
POI's ``name`` / ``known_to_party`` consistent with the authoritative
``npc_states[id]``. These tests pin the conflict-resolution contract so the
class of "real name / stale reveal leaks to the POI" bugs cannot regress.
"""

from __future__ import annotations

from app.game.scene_state_service import apply_scene_update, reconcile_scene_npcs
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus


def _active(scene: dict, npc_states: dict | None = None) -> ActiveSession:
    return ActiveSession(
        session_id="s1",
        phase=SessionStatus.EXPLORATION,
        state_data={"current_scene": scene, "npc_states": npc_states or {}},
    )


def test_npc_states_known_flag_wins_over_poi() -> None:
    """npc_states.known_to_party=False overrides a stale POI known=True."""
    scene = {
        "pois": [{"id": "npc_x", "name": "Orlin", "kind": "npc", "known_to_party": True}],
    }
    active = _active(scene, {"npc_x": {"name": "Orlin", "known_to_party": False}})
    reconcile_scene_npcs(active, scene)
    assert scene["pois"][0]["known_to_party"] is False
    assert active.state_data["npc_states"]["npc_x"]["known_to_party"] is False


def test_poi_known_flag_seeds_npc_states_when_missing() -> None:
    """If only the POI carries known_to_party, npc_states adopts it (converge)."""
    scene = {"pois": [{"id": "npc_y", "name": "Vex", "kind": "npc", "known_to_party": False}]}
    active = _active(scene, {"npc_y": {"name": "Vex"}})
    reconcile_scene_npcs(active, scene)
    assert active.state_data["npc_states"]["npc_y"]["known_to_party"] is False
    assert scene["pois"][0]["known_to_party"] is False


def test_npc_states_name_propagates_to_poi() -> None:
    """A rename in npc_states (authority) surfaces on the visible POI."""
    scene = {"pois": [{"id": "npc_z", "name": "l'inconnu", "kind": "npc"}]}
    active = _active(scene, {"npc_z": {"name": "Capitaine Reyes", "known_to_party": True}})
    reconcile_scene_npcs(active, scene)
    assert scene["pois"][0]["name"] == "Capitaine Reyes"


def test_poi_name_seeds_npc_states_when_missing() -> None:
    """If npc_states has no name yet, the POI name seeds it."""
    scene = {"pois": [{"id": "npc_w", "name": "Garde", "kind": "npc"}]}
    active = _active(scene, {"npc_w": {"known_to_party": True}})
    reconcile_scene_npcs(active, scene)
    assert active.state_data["npc_states"]["npc_w"]["name"] == "Garde"


def test_reconcile_is_idempotent() -> None:
    scene = {"pois": [{"id": "npc_a", "name": "Mira", "kind": "npc", "known_to_party": False}]}
    active = _active(scene, {"npc_a": {"name": "Mira", "known_to_party": False}})
    reconcile_scene_npcs(active, scene)
    snapshot = (dict(scene["pois"][0]), dict(active.state_data["npc_states"]["npc_a"]))
    reconcile_scene_npcs(active, scene)
    assert (scene["pois"][0], active.state_data["npc_states"]["npc_a"]) == snapshot


def test_non_npc_poi_untouched() -> None:
    scene = {"pois": [{"id": "chest_1", "name": "Coffre", "kind": "object"}]}
    active = _active(scene, {})
    reconcile_scene_npcs(active, scene)
    assert scene["pois"][0] == {"id": "chest_1", "name": "Coffre", "kind": "object"}
    assert "chest_1" not in active.state_data["npc_states"]


def test_scene_update_runs_reconcile_end_to_end() -> None:
    """apply_scene_update wires reconcile: an unknown NPC added via npc_updates
    has its POI projection flagged unknown without the caller touching the POI."""
    active = _active({"cols": 12, "rows": 12, "pois": [], "exits": []})
    apply_scene_update(
        active,
        {
            "npc_updates": [
                {
                    "id": "npc_spy",
                    "name": "Sombre silhouette",
                    "status": "present",
                    "position": {"col": 3, "row": 3},
                    "known_to_party": False,
                }
            ]
        },
    )
    poi = next(p for p in active.state_data["current_scene"]["pois"] if p["id"] == "npc_spy")
    assert poi["known_to_party"] is False
    assert active.state_data["npc_states"]["npc_spy"]["known_to_party"] is False
