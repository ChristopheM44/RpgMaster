"""Continuité spatiale entre scènes : bord opposé, sens vertical inversé, groupe à côté."""

from __future__ import annotations

from app.game.gm_response_executor import GMResponseExecutor
from app.services import scene_continuity as sc


def _old_scene() -> dict:
    return {
        "scene_id": "jardin_petrifie",
        "cols": 12,
        "rows": 12,
        "exits": [
            {
                "id": "exit_2",
                "label": "S'enfoncer vers le Caveau",
                "position": {"col": 8, "row": 11},
                "leads_to": "le_caveau_du_codex",
                "element_id": "element_exit_2_stairs",
            },
            {
                "id": "exit_est",
                "label": "Sentier",
                "position": {"col": 11, "row": 4},
                "leads_to": "foret_grise",
            },
        ],
        "elements": [
            {
                "id": "element_exit_2_stairs",
                "kind": "stairs",
                "facing": "south",
                "vertical_direction": "down",
            }
        ],
        "party_positions": {"hero": {"col": 5, "row": 5}, "elara": {"col": 6, "row": 5}},
    }


def _apply(old: dict, raw: dict, pending: dict | None = None) -> dict:
    """Reproduit le chemin de GMResponseExecutor._apply_scene_layout (sans event bus)."""
    arrival = sc.prepare_arrival(old, raw, pending)
    layout = GMResponseExecutor._normalize_scene_layout({"scene": raw})
    sc.finalize_arrival(layout, arrival, old)
    return layout


def _stairs_for(layout: dict, exit_id: str) -> dict:
    exit_ = next(e for e in layout["exits"] if e["id"] == exit_id)
    return next(el for el in layout["elements"] if el["id"] == exit_["element_id"])


def test_descending_stairs_arrive_by_ascending_stairs_on_opposite_edge() -> None:
    raw = {
        "scene_id": "le_caveau_du_codex",
        "scene_theme": "dungeon",
        "terrain": "crypte",
        "exits": [
            {
                "id": "retour",
                "label": "Retour au jardin",
                "position": {"col": 3, "row": 6},
                "leads_to": "jardin_petrifie",
            }
        ],
        "party_positions": {"hero": {"col": 6, "row": 6}, "elara": {"col": 6, "row": 7}},
    }

    layout = _apply(_old_scene(), raw)

    exit_ = next(e for e in layout["exits"] if e["id"] == "retour")
    assert exit_["position"] == {"col": 8, "row": 0}
    stairs = _stairs_for(layout, "retour")
    assert stairs["kind"] == "stairs"
    assert stairs["facing"] == "north"
    assert stairs["vertical_direction"] == "up"
    assert layout["arrival"] == {
        "exit_id": "retour",
        "from_scene_id": "jardin_petrifie",
        "via_exit_id": "exit_2",
        "facing": "north",
        "vertical_direction": "up",
    }
    for pos in layout["party_positions"].values():
        assert max(abs(pos["col"] - 8), abs(pos["row"] - 1)) <= 1
        assert pos != {"col": 8, "row": 0}


def test_horizontal_exit_creates_return_on_opposite_edge_same_row() -> None:
    raw = {"scene_id": "foret_grise", "scene_theme": "forest", "exits": []}

    layout = _apply(_old_scene(), raw)

    exit_ = next(e for e in layout["exits"] if e["id"] == "exit_retour")
    assert exit_["position"] == {"col": 0, "row": 4}
    assert exit_["leads_to"] == "jardin_petrifie"
    assert layout["arrival"]["facing"] == "west"
    assert layout["arrival"]["vertical_direction"] == "level"
    # Groupe repris de l'ancienne scène, posé juste à l'intérieur du bord ouest.
    assert set(layout["party_positions"]) == {"hero", "elara"}
    assert all(pos["col"] <= 2 for pos in layout["party_positions"].values())


def test_pending_departure_resolves_invented_scene_id() -> None:
    raw = {"scene_id": "salle_inventee_par_le_llm", "scene_theme": "dungeon", "exits": []}
    pending = {"from_scene_id": "jardin_petrifie", "exit_id": "exit_2"}

    layout = _apply(_old_scene(), raw, pending)

    assert layout["arrival"]["vertical_direction"] == "up"
    exit_ = next(e for e in layout["exits"] if e["id"] == layout["arrival"]["exit_id"])
    assert exit_["position"]["row"] == 0


def test_free_text_travel_without_match_adds_no_constraint() -> None:
    raw = {"scene_id": "ailleurs", "scene_theme": "plains", "exits": []}

    assert sc.prepare_arrival(_old_scene(), raw) is None
    assert raw["exits"] == []


def test_relayout_of_same_scene_is_untouched() -> None:
    raw = {"scene_id": "jardin_petrifie", "exits": []}
    assert sc.prepare_arrival(_old_scene(), raw) is None


def test_return_exit_already_on_the_right_edge_keeps_its_position() -> None:
    raw = {
        "scene_id": "foret_grise",
        "exits": [
            {
                "id": "r",
                "label": "Retour",
                "position": {"col": 0, "row": 9},
                "leads_to": "jardin_petrifie",
            }
        ],
    }

    layout = _apply(_old_scene(), raw)

    assert next(e for e in layout["exits"] if e["id"] == "r")["position"] == {"col": 0, "row": 9}


def test_remember_departure_from_click_and_from_destination() -> None:
    state = {"current_scene": _old_scene()}
    sc.remember_departure(state, exit_id="exit_est")
    assert state[sc.PENDING_DEPARTURE_KEY] == {
        "from_scene_id": "jardin_petrifie",
        "exit_id": "exit_est",
    }

    sc.remember_departure(state, destination_node_id="le_caveau_du_codex")
    assert state[sc.PENDING_DEPARTURE_KEY]["exit_id"] == "exit_2"

    sc.remember_departure(state, destination_node_id="nulle_part")
    assert sc.PENDING_DEPARTURE_KEY not in state


def test_party_ids_fallback_when_no_positions_anywhere() -> None:
    old = _old_scene() | {"party_positions": {}}
    raw = {"scene_id": "le_caveau_du_codex", "scene_theme": "dungeon", "exits": []}
    arrival = sc.prepare_arrival(old, raw)
    layout = GMResponseExecutor._normalize_scene_layout({"scene": raw})
    sc.finalize_arrival(layout, arrival, old, party_ids=["a", "b"])

    assert set(layout["party_positions"]) == {"a", "b"}
    assert all(pos["row"] <= 2 for pos in layout["party_positions"].values())


def _access_for(layout: dict, exit_id: str) -> list[dict]:
    exit_ = next(e for e in layout["exits"] if e["id"] == exit_id)
    return [el for el in layout["elements"] if el["id"] == exit_.get("element_id")]


def _unlinked_access(layout: dict) -> list[dict]:
    linked = {item.get("element_id") for key in ("pois", "exits") for item in layout.get(key) or []}
    return [
        el
        for el in layout["elements"]
        if el["kind"] in {"door", "stairs"} and el["id"] not in linked
    ]


def test_round_trip_lands_back_on_the_departure_stairwell() -> None:
    jardin = _apply(
        {"scene_id": "avant", "cols": 12, "rows": 12, "exits": []},
        {
            "scene_id": "jardin_petrifie",
            "scene_theme": "dungeon",
            "terrain": "crypte",
            "exits": [
                {
                    "id": "exit_2",
                    "label": "S'enfoncer vers le Caveau",
                    "position": {"col": 8, "row": 11},
                    "leads_to": "le_caveau_du_codex",
                    "description": "Un escalier descend vers les profondeurs.",
                }
            ],
            "party_positions": {"hero": {"col": 5, "row": 5}},
        },
    )
    caveau = _apply(
        jardin, {"scene_id": "le_caveau_du_codex", "scene_theme": "dungeon", "exits": []}
    )
    back = _apply(
        caveau,
        {
            "scene_id": "jardin_petrifie",
            "scene_theme": "dungeon",
            "terrain": "crypte",
            "exits": [
                {
                    "id": "exit_2",
                    "label": "S'enfoncer vers le Caveau",
                    "position": {"col": 8, "row": 11},
                    "leads_to": "le_caveau_du_codex",
                    "description": "Un escalier descend vers les profondeurs.",
                }
            ],
        },
    )

    assert back["arrival"]["exit_id"] == "exit_2"
    assert back["arrival"]["facing"] == "south"
    assert back["arrival"]["vertical_direction"] == "down"
    assert next(e for e in back["exits"] if e["id"] == "exit_2")["position"] == {
        "col": 8,
        "row": 11,
    }
    (stairs,) = _access_for(back, "exit_2")
    assert (stairs["kind"], stairs["facing"], stairs["vertical_direction"]) == (
        "stairs",
        "south",
        "down",
    )


def test_moving_exit_of_pre_enriched_layout_leaves_no_orphan_nor_wall_gap() -> None:
    from app.services.local_map_service import enrich_scene_layout

    raw = {
        "scene_id": "le_caveau_du_codex",
        "scene_theme": "dungeon",
        "terrain": "crypte",
        "exits": [
            {
                "id": "r",
                "label": "Porte du retour",
                "position": {"col": 3, "row": 11},
                "leads_to": "jardin_petrifie",
            }
        ],
        "pois": [],
        "party_positions": {},
    }
    enrich_scene_layout(raw)  # producteur qui enrichit en amont (salles de donjon)

    layout = _apply(_old_scene(), raw)

    assert len(_access_for(layout, "r")) == 1
    assert _unlinked_access(layout) == []
    south = [
        el
        for el in layout["elements"]
        if el["kind"] == "wall" and el["id"].startswith("wall_south")
    ]
    assert len(south) == 1  # mur sud continu : plus de brèche à l'ancienne position


def test_minimal_fallback_scene_gets_continuity() -> None:
    from types import SimpleNamespace

    from app.game.action_pipeline import ActionPipeline

    old = _old_scene()
    active = SimpleNamespace(
        state_data={"current_scene": old, "characters": {"hero": {}, "elara": {}}}
    )
    action = ActionPipeline._minimal_scene_layout_action("foret_grise", "Forêt grise", active)

    layout = _apply(old, action.params)

    exit_ = next(e for e in layout["exits"] if e["id"] == layout["arrival"]["exit_id"])
    # Sortie est (ligne 4) → retour à l'ouest, même ligne ; le (6, 11) codé en dur est remplacé.
    assert exit_["position"] == {"col": 0, "row": 4}


def test_dungeon_rooms_arrive_on_opposite_edge_without_orphans() -> None:
    from app.engine.dungeon_generator import generate_dungeon, room_scene_skeleton
    from app.services.local_map_service import enrich_scene_layout

    bp = generate_dungeon("continuite")
    room_a = enrich_scene_layout(room_scene_skeleton(bp, bp.entry_room_id))
    room_a["party_positions"] = {"hero": {"col": 6, "row": 6}}
    departure = next(e for e in room_a["exits"] if e["leads_to"] in {r.id for r in bp.rooms})
    room_b = enrich_scene_layout(room_scene_skeleton(bp, departure["leads_to"]))

    layout = _apply(room_a, room_b)

    assert layout["arrival"]["exit_id"]  # la salle B a un accès retour vers A
    facing, _ = sc.departure_orientation(room_a, departure)
    exit_ = next(e for e in layout["exits"] if e["id"] == layout["arrival"]["exit_id"])
    assert sc.OPPOSITE_FACING[facing] in sc.lms.border_facings(exit_["position"], 12, 12)
    assert len(_access_for(layout, exit_["id"])) == 1
    assert _unlinked_access(layout) == []


def test_forget_departure() -> None:
    state = {"current_scene": _old_scene()}
    sc.remember_departure(state, exit_id="exit_est")
    sc.forget_departure(state)
    assert sc.PENDING_DEPARTURE_KEY not in state
