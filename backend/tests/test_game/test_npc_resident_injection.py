"""Resident NPCs keep a visible POI even when the LLM omits them.

These pin inject_resident_npc_pois(): a stationary/local NPC whose npc_states
entry anchors it to the current scene (last_location == scene_id, not departed)
must appear as a POI — the LLM-authored scene_layout rarely re-lists locals,
and _merge_npc_updates only upserts a POI when the update carries a position,
so "the merchant in his own shop" used to be invisible on the map.
"""

from __future__ import annotations

from app.game.scene_state_service import apply_scene_update, inject_resident_npc_pois
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus


def _active(scene: dict, npc_states: dict | None = None) -> ActiveSession:
    return ActiveSession(
        session_id="s1",
        phase=SessionStatus.EXPLORATION,
        state_data={"current_scene": scene, "npc_states": npc_states or {}},
    )


def _shop_layout(**overrides: object) -> dict:
    layout = {
        "scene_id": "echoppe_bram",
        "cols": 12,
        "rows": 12,
        "pois": [{"id": "comptoir", "name": "Comptoir", "kind": "clue"}],
        "exits": [],
        "party_positions": {"thorvald": {"col": 5, "row": 7}},
    }
    layout.update(overrides)
    return layout


def _poi_ids(layout: dict) -> list[str]:
    return [p["id"] for p in layout["pois"]]


def test_resident_npc_omitted_by_llm_is_injected() -> None:
    layout = _shop_layout()
    active = _active(
        layout,
        {
            "bram": {
                "name": "Bram",
                "status": "present",
                "last_location": "echoppe_bram",
                "known_to_party": True,
            }
        },
    )
    inject_resident_npc_pois(active, layout)

    assert "bram" in _poi_ids(layout), "le PNJ résident doit être réinjecté"
    poi = next(p for p in layout["pois"] if p["id"] == "bram")
    assert poi["kind"] == "npc"
    assert poi["visibility"] == "visible"
    assert poi["known_to_party"] is True
    assert poi["name"] == "Bram"


def test_npc_anchored_to_another_scene_is_not_injected() -> None:
    layout = _shop_layout()
    active = _active(layout, {"bram": {"status": "present", "last_location": "taverne"}})
    inject_resident_npc_pois(active, layout)
    assert "bram" not in _poi_ids(layout)


def test_existing_poi_is_not_duplicated() -> None:
    layout = _shop_layout()
    layout["pois"].append({"id": "bram", "name": "Bram", "kind": "npc"})
    active = _active(layout, {"bram": {"status": "present", "last_location": "echoppe_bram"}})
    inject_resident_npc_pois(active, layout)
    assert _poi_ids(layout).count("bram") == 1


def test_departed_and_hidden_npcs_are_not_injected() -> None:
    layout = _shop_layout()
    active = _active(
        layout,
        {
            "fantome": {"status": "dead", "last_location": "echoppe_bram"},
            "espion": {"status": "hidden", "last_location": "echoppe_bram"},
        },
    )
    inject_resident_npc_pois(active, layout)
    assert "fantome" not in _poi_ids(layout)
    assert "espion" not in _poi_ids(layout)


def test_noop_without_scene_id() -> None:
    layout = _shop_layout()
    layout.pop("scene_id")
    active = _active(layout, {"bram": {"status": "present", "last_location": "echoppe_bram"}})
    inject_resident_npc_pois(active, layout)
    assert "bram" not in _poi_ids(layout)


def test_stored_position_is_reused_and_collisions_are_shifted() -> None:
    layout = _shop_layout()
    layout["pois"][0]["position"] = {"col": 3, "row": 3}
    active = _active(
        layout,
        {
            "bram": {
                "status": "present",
                "last_location": "echoppe_bram",
                "position": {"col": 2, "row": 2},
            },
            "mira": {
                "status": "present",
                "last_location": "echoppe_bram",
                "position": {"col": 3, "row": 3},  # déjà prise par le comptoir
            },
        },
    )
    inject_resident_npc_pois(active, layout)

    bram = next(p for p in layout["pois"] if p["id"] == "bram")
    assert bram["position"] == {"col": 2, "row": 2}
    mira = next(p for p in layout["pois"] if p["id"] == "mira")
    assert mira["position"] != {"col": 3, "row": 3}, "cellule occupée → décalée"


def test_two_injected_npcs_get_distinct_cells() -> None:
    layout = _shop_layout()
    active = _active(
        layout,
        {
            "bram": {"status": "present", "last_location": "echoppe_bram"},
            "mira": {"status": "present", "last_location": "echoppe_bram"},
        },
    )
    inject_resident_npc_pois(active, layout)
    positions = [
        (p["position"]["col"], p["position"]["row"])
        for p in layout["pois"]
        if p["id"] in {"bram", "mira"}
    ]
    assert len(positions) == 2
    assert len(set(positions)) == 2


def test_scene_update_present_without_position_yields_a_poi() -> None:
    """Régression réelle : npc_update «present» sans position → PNJ invisible."""
    active = _active(_shop_layout(), {})
    apply_scene_update(
        active, {"npc_updates": [{"id": "bram", "name": "Bram", "status": "present"}]}
    )

    scene = active.state_data["current_scene"]
    assert "bram" in _poi_ids(scene), "apply_scene_update doit garantir le POI résident"
    poi = next(p for p in scene["pois"] if p["id"] == "bram")
    assert poi["kind"] == "npc"
