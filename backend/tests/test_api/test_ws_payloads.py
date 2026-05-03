from __future__ import annotations

from types import SimpleNamespace

from app.api.ws_payloads import (
    build_session_state_payload,
    compute_ac_from_equipment,
)
from app.models.session import SessionStatus


class _TurnManager:
    def to_dict(self) -> dict:
        return {
            "index": 0,
            "order": [
                {
                    "combatant_id": "hero-1",
                    "name": "Aria",
                    "initiative_total": 17,
                    "is_ai_controlled": False,
                    "is_player": True,
                }
            ],
        }


class _GameLoop:
    def get_valid_transitions(self, phase: SessionStatus) -> list[SessionStatus]:
        assert phase == SessionStatus.EXPLORATION
        return [SessionStatus.ENCOUNTER_START, SessionStatus.COMBAT]


def test_build_session_state_payload_maps_turn_entries() -> None:
    active = SimpleNamespace(
        phase=SessionStatus.EXPLORATION,
        turn_number=3,
        round_number=1,
        turn_manager=_TurnManager(),
        game_loop=_GameLoop(),
        state_data={"quests": [{"id": "q1"}], "chronicle": [], "current_scene": None},
    )

    payload = build_session_state_payload("session-1", active)

    assert payload["session_id"] == "session-1"
    assert payload["phase"] == "exploration"
    assert payload["turn_order"] == [
        {
            "id": "hero-1",
            "name": "Aria",
            "initiative": 17,
            "is_ai": False,
            "is_ai_controlled": False,
            "is_player": True,
        }
    ]
    assert payload["valid_transitions"] == ["encounter_start", "combat"]


def test_compute_ac_from_equipment_applies_armor_dex_cap_and_shield() -> None:
    equipment = [
        {"equipped": True, "category": "medium", "base_ac": 14, "dex_cap": 2},
        {"equipped": True, "category": "shield"},
    ]

    assert compute_ac_from_equipment(equipment, dex_mod=4) == 18
