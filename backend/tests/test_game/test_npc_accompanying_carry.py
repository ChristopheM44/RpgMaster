"""P1+P2 — party-accompanying NPCs survive a scene transition; canon is protected.

These pin the fix for the "Khalid the guide vanishes at the oasis" class of bug:
1. carry_accompanying_npcs() moves a travelling NPC into the new scene (P1).
2. The carried NPC is no longer dropped by _filter_absent_npc_pois (ordering).
3. _merge_npc_updates rejects a *causeless* departure for an accompanying NPC,
   so a transition artifact can't be frozen as "the guide disappeared" (P2).
4. detect_travel_intent now recognises imperative phrasing ("rendons-nous à …").
"""

from __future__ import annotations

from app.agents.schemas import AgentResponse, GMAction
from app.game.action_pipeline import ActionPipeline, ActionRequest
from app.game.gm_response_executor import GMResponseExecutor
from app.game.scene_state_service import apply_scene_update, carry_accompanying_npcs
from app.game.session_manager import ActiveSession
from app.game.travel_detection import detect_travel_intent
from app.models.session import SessionStatus


def _active(scene: dict, npc_states: dict | None = None) -> ActiveSession:
    return ActiveSession(
        session_id="s1",
        phase=SessionStatus.EXPLORATION,
        state_data={"current_scene": scene, "npc_states": npc_states or {}},
    )


def _old_scene_with_guide() -> dict:
    return {
        "scene_id": "piste_ambre",
        "pois": [{"id": "khalid_guide", "name": "Khalid le Guide", "kind": "npc"}],
    }


def _new_oasis_layout() -> dict:
    return {
        "scene_id": "oasis_emeraude",
        "cols": 12,
        "rows": 12,
        "pois": [{"id": "bassin_noir", "name": "Bassin noir", "kind": "hazard"}],
        "party_positions": {"thorvald": {"col": 5, "row": 7}},
    }


# --- P1: carry-over -----------------------------------------------------------


def test_guide_is_carried_into_the_new_scene() -> None:
    old, new = _old_scene_with_guide(), _new_oasis_layout()
    active = _active(
        old,
        {
            "khalid_guide": {
                "name": "Khalid le Guide",
                "status": "present",
                "disposition": "accompanying",
                "known_to_party": True,
            }
        },
    )
    carry_accompanying_npcs(active, old, new)

    assert "khalid_guide" in [p["id"] for p in new["pois"]], "le guide doit être injecté"
    npc = active.state_data["npc_states"]["khalid_guide"]
    assert npc["status"] == "present"
    assert npc["disposition"] == "accompanying"
    assert npc["last_location"] == "oasis_emeraude"
    carried = next(p for p in new["pois"] if p["id"] == "khalid_guide")
    assert carried["known_to_party"] is True  # anonymisation préservée


def test_already_present_poi_in_new_layout_is_not_duplicated() -> None:
    old = _old_scene_with_guide()
    new = _new_oasis_layout()
    new["pois"].append({"id": "khalid_guide", "name": "Khalid", "kind": "npc"})
    active = _active(
        old,
        {
            "khalid_guide": {
                "name": "Khalid le Guide",
                "status": "present",
                "disposition": "accompanying",
            }
        },
    )
    carry_accompanying_npcs(active, old, new)
    assert [p["id"] for p in new["pois"]].count("khalid_guide") == 1


def test_local_present_npc_is_not_carried_without_accompanying_flag() -> None:
    old = {
        "scene_id": "quai_sirenes",
        "pois": [{"id": "amirale_vance", "name": "Amirale Vance", "kind": "npc"}],
    }
    new = _new_oasis_layout()
    active = _active(old, {"amirale_vance": {"name": "Amirale Vance", "status": "present"}})
    carry_accompanying_npcs(active, old, new)
    assert "amirale_vance" not in [p["id"] for p in new["pois"]]


def test_stationary_npc_is_not_carried() -> None:
    old = {
        "scene_id": "taverne",
        "pois": [{"id": "aubergiste", "name": "Aubergiste", "kind": "npc"}],
    }
    new = _new_oasis_layout()
    active = _active(old, {"aubergiste": {"status": "present", "disposition": "stationary"}})
    carry_accompanying_npcs(active, old, new)
    assert "aubergiste" not in [p["id"] for p in new["pois"]]


def test_departed_npc_is_not_carried() -> None:
    old = _old_scene_with_guide()
    new = _new_oasis_layout()
    active = _active(old, {"khalid_guide": {"status": "dead", "disposition": "accompanying"}})
    carry_accompanying_npcs(active, old, new)
    assert "khalid_guide" not in [p["id"] for p in new["pois"]]


def test_no_carry_when_same_scene_reemitted() -> None:
    old = _old_scene_with_guide()
    new = _new_oasis_layout()
    new["scene_id"] = "piste_ambre"  # same place re-emitted, not a travel transition
    active = _active(old, {"khalid_guide": {"status": "present", "disposition": "accompanying"}})
    carry_accompanying_npcs(active, old, new)
    assert "khalid_guide" not in [p["id"] for p in new["pois"]]


def test_no_carry_when_new_layout_has_no_scene_id() -> None:
    old = _old_scene_with_guide()
    new = _new_oasis_layout()
    new.pop("scene_id")
    active = _active(old, {"khalid_guide": {"status": "present", "disposition": "accompanying"}})
    carry_accompanying_npcs(active, old, new)
    assert "khalid_guide" not in [p["id"] for p in new["pois"]]


# --- P1: carry survives the absence filter (ordering regression) --------------


def test_filter_removes_uncarried_guide_but_keeps_carried_one() -> None:
    """Without carry the absence filter drops the guide; with carry it keeps him."""
    # Baseline: the guide is in the layout but still anchored to the old scene.
    active = _active(
        _old_scene_with_guide(),
        {
            "khalid_guide": {
                "name": "Khalid le Guide",
                "status": "present",
                "disposition": "accompanying",
                "last_location": "piste_ambre",
            }
        },
    )
    naive = _new_oasis_layout()
    naive["pois"].append({"id": "khalid_guide", "name": "Khalid", "kind": "npc"})
    GMResponseExecutor._filter_absent_npc_pois(naive, active)
    assert "khalid_guide" not in [p["id"] for p in naive["pois"]], (
        "le filtre supprime un PNJ ancré à l'ancienne scène (bug d'origine)"
    )

    # With carry first, last_location moves forward and he survives the filter.
    carried = _new_oasis_layout()
    carry_accompanying_npcs(active, _old_scene_with_guide(), carried)
    GMResponseExecutor._filter_absent_npc_pois(carried, active)
    assert "khalid_guide" in [p["id"] for p in carried["pois"]]


# --- P2: causeless-departure guard -------------------------------------------


def _scene_with_accompanying_guide() -> ActiveSession:
    return _active(
        {
            "scene_id": "oasis_emeraude",
            "cols": 12,
            "rows": 12,
            "pois": [
                {
                    "id": "khalid_guide",
                    "name": "Khalid",
                    "kind": "npc",
                    "position": {"col": 5, "row": 5},
                }
            ],
            "exits": [],
        },
        {"khalid_guide": {"name": "Khalid", "status": "present", "disposition": "accompanying"}},
    )


def test_causeless_missing_on_accompanying_npc_is_ignored() -> None:
    active = _scene_with_accompanying_guide()
    apply_scene_update(active, {"npc_updates": [{"id": "khalid_guide", "status": "missing"}]})
    npc = active.state_data["npc_states"]["khalid_guide"]
    assert npc["status"] == "present", "départ sans cause refusé pour un accompagnant"
    assert any(p["id"] == "khalid_guide" for p in active.state_data["current_scene"]["pois"])


def test_caused_departure_on_accompanying_npc_is_applied() -> None:
    active = _scene_with_accompanying_guide()
    apply_scene_update(
        active,
        {
            "npc_updates": [
                {
                    "id": "khalid_guide",
                    "status": "missing",
                    "note": "Enlevé par les pillards des dunes.",
                }
            ]
        },
    )
    npc = active.state_data["npc_states"]["khalid_guide"]
    assert npc["status"] == "missing"
    assert npc["disposition"] == "neutral"  # the accompanying state ends on a real departure
    assert not any(p["id"] == "khalid_guide" for p in active.state_data["current_scene"]["pois"])


def test_non_accompanying_npc_can_leave_without_cause() -> None:
    """The guard is narrow: a regular NPC may still go missing without a note."""
    active = _active(
        {
            "scene_id": "ruelle",
            "cols": 12,
            "rows": 12,
            "pois": [
                {
                    "id": "passant",
                    "name": "Passant",
                    "kind": "npc",
                    "position": {"col": 2, "row": 2},
                }
            ],
            "exits": [],
        },
        {"passant": {"name": "Passant", "status": "present"}},
    )
    apply_scene_update(active, {"npc_updates": [{"id": "passant", "status": "missing"}]})
    assert active.state_data["npc_states"]["passant"]["status"] == "missing"


# --- P2: imperative travel markers -------------------------------------------


def test_imperative_travel_phrasing_is_detected() -> None:
    state = {
        "current_scene": {
            "exits": [
                {"id": "vers_oasis", "label": "Oasis d'Émeraude", "leads_to": "oasis_emeraude"}
            ]
        }
    }
    intent = detect_travel_intent(
        "Très bien rendons-nous à l'oasis d'émeraude, ouvrez la route Khalid.", state
    )
    assert intent.is_travel is True
    assert intent.confidence == "explicit"
    assert intent.destination_node_id == "oasis_emeraude"


def test_surface_return_phrasing_is_detected_from_scene_exit() -> None:
    state = {
        "current_scene": {
            "exits": [
                {
                    "id": "vers_surface",
                    "label": "Conduit vers la surface",
                    "leads_to": "rivage_port_azur",
                }
            ]
        }
    }
    intent = detect_travel_intent(
        "Nous remontons à la surface pour remettre la sirène à la mer.", state
    )
    assert intent.is_travel is True
    assert intent.destination == "Conduit vers la surface"
    assert intent.destination_node_id == "rivage_port_azur"


def test_sea_return_phrasing_is_detected_without_known_exit() -> None:
    intent = detect_travel_intent(
        "Je ramène la sirène blessée et je la remets à la mer.",
        {"current_scene": {"exits": []}},
    )
    assert intent.is_travel is True
    assert intent.destination == "la mer"
    assert intent.destination_node_id is None


# --- P2: deterministic scene_layout fallback ---------------------------------


def _travel_request(node_id: str = "oasis_emeraude") -> ActionRequest:
    return ActionRequest(
        session_id="s1",
        actor_id="thorvald",
        actor_kind="player",
        action_type="free_text",
        content="rendons-nous à l'oasis",
        travel_intent={
            "is_travel": True,
            "destination": "oasis",
            "destination_node_id": node_id,
            "confidence": "explicit",
        },
    )


def _exploration_active() -> ActiveSession:
    return ActiveSession(
        session_id="s1",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {"thorvald": {"name": "Thorvald"}, "elara": {"name": "Elara"}},
            "current_scene": {
                "scene_id": "piste_ambre",
                "exits": [
                    {"id": "vers_oasis", "label": "Oasis d'Émeraude", "leads_to": "oasis_emeraude"}
                ],
                "pois": [{"id": "khalid_guide", "name": "Khalid le Guide", "kind": "npc"}],
            },
            "npc_states": {"khalid_guide": {"name": "Khalid le Guide", "status": "present"}},
        },
    )


def test_travel_fallback_injects_scene_layout_when_gm_forgot() -> None:
    response = AgentResponse(content="Vous progressez vers l'oasis…", actions=[])
    out = ActionPipeline._with_travel_scene_fallback(
        response, _travel_request(), _exploration_active()
    )
    layouts = [a for a in out.actions if a.type == "scene_layout"]
    assert len(layouts) == 1
    assert layouts[0].params["scene_id"] == "oasis_emeraude"
    assert "Oasis d'Émeraude" in layouts[0].params["description"]
    assert "thorvald" in layouts[0].params["party_positions"]
    # The journal must move with the scene, else next turn's VERROU anchor lies.
    journals = [a for a in out.actions if a.type == "journal_update"]
    assert len(journals) == 1
    assert journals[0].params["location_place"] == "Oasis d'Émeraude"


def test_travel_fallback_does_not_clobber_gm_journal_update() -> None:
    response = AgentResponse(
        content="…",
        actions=[GMAction(type="journal_update", params={"location_place": "Oasis (vue MJ)"})],
    )
    out = ActionPipeline._with_travel_scene_fallback(
        response, _travel_request(), _exploration_active()
    )
    journals = [a for a in out.actions if a.type == "journal_update"]
    assert len(journals) == 1
    assert journals[0].params["location_place"] == "Oasis (vue MJ)"
    assert any(a.type == "scene_layout" for a in out.actions)  # layout still injected


def test_travel_fallback_noop_when_gm_emitted_scene_layout() -> None:
    response = AgentResponse(
        content="…",
        actions=[GMAction(type="scene_layout", params={"scene_id": "oasis_emeraude"})],
    )
    out = ActionPipeline._with_travel_scene_fallback(
        response, _travel_request(), _exploration_active()
    )
    assert sum(1 for a in out.actions if a.type == "scene_layout") == 1


def test_travel_fallback_injects_scene_layout_for_unknown_explicit_destination() -> None:
    response = AgentResponse(content="…", actions=[])
    out = ActionPipeline._with_travel_scene_fallback(
        response, _travel_request(node_id=""), _exploration_active()
    )
    layouts = [a for a in out.actions if a.type == "scene_layout"]
    assert len(layouts) == 1
    assert layouts[0].params["scene_id"] == "scene_oasis"


def test_travel_fallback_noop_without_destination() -> None:
    response = AgentResponse(content="…", actions=[])
    request = _travel_request(node_id="")
    request.travel_intent = {"is_travel": True, "confidence": "implicit"}
    out = ActionPipeline._with_travel_scene_fallback(response, request, _exploration_active())
    assert not any(a.type == "scene_layout" for a in out.actions)


def test_travel_fallback_noop_when_already_at_destination() -> None:
    response = AgentResponse(content="…", actions=[])
    active = _exploration_active()
    active.state_data["current_scene"]["scene_id"] = "oasis_emeraude"
    out = ActionPipeline._with_travel_scene_fallback(response, _travel_request(), active)
    assert not any(a.type == "scene_layout" for a in out.actions)


def test_journal_location_update_injects_scene_layout_when_gm_forgot() -> None:
    active = _exploration_active()
    active.state_data["adventure_journal"] = {"location_place": "Prison de cristal"}
    response = AgentResponse(
        content="Vous retrouvez le rivage.",
        actions=[
            GMAction(
                type="journal_update",
                params={"location_place": "Rivage du Port d'Azur"},
            )
        ],
    )

    out = ActionPipeline._with_journal_scene_fallback(response, active)

    layouts = [a for a in out.actions if a.type == "scene_layout"]
    assert len(layouts) == 1
    assert layouts[0].params["scene_id"] == "scene_rivage_du_port_d_azur"
    assert "Rivage du Port d'Azur" in layouts[0].params["description"]
