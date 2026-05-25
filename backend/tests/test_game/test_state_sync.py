from __future__ import annotations

from app.game.session_manager import ActiveSession
from app.game.state_sync import sync_character_state
from app.models.session import SessionStatus


def test_sync_character_state_updates_combat_stats_for_equipment_change_in_combat() -> None:
    active = ActiveSession(
        session_id="sync-combat-stats",
        phase=SessionStatus.COMBAT,
        state_data={
            "characters": {
                "shade_1": {
                    "name": "Shade",
                    "char_class": "rogue",
                    "level": 1,
                    "ability_scores": {"str": 8, "dex": 16},
                    "equipment": [],
                }
            },
            "combatants": {
                "shade_1": {
                    "name": "Shade",
                    "hp": 10,
                    "hp_max": 10,
                    "is_player": True,
                    "attack_bonus": 3,
                    "damage_notation": "1d6",
                    "reach_m": 1.5,
                    "attack_range_m": 1.5,
                    "speed_m": 9.0,
                    "status": "active",
                }
            },
        },
    )
    equipment = [
        {
            "id": "shortbow",
            "item_type": "weapon",
            "equipped": True,
            "occupied_slots": ["main_hand", "off_hand"],
        }
    ]

    changed = sync_character_state(active, "shade_1", equipment=equipment)

    assert changed is True
    combatant = active.state_data["combatants"]["shade_1"]
    assert combatant["attack_bonus"] == 5
    assert combatant["damage_notation"] == "1d6+3"
    assert combatant["attack_range_m"] == 24.0
