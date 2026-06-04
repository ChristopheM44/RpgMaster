from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus


@pytest.mark.asyncio
async def test_start_combat_materializes_custom_monster(monkeypatch) -> None:
    from app.api import ws_game

    active = ActiveSession(
        session_id="session-custom",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "phase": "exploration",
            "characters": {
                "hero-1": {
                    "name": "Thorvald",
                    "level": 1,
                    "hp": 12,
                    "hp_max": 12,
                    "dex": 12,
                    "is_ai": False,
                    "equipment": [],
                }
            },
            "campaign_context": {
                "custom_monsters": [
                    {
                        "id": "squelette_enflamme",
                        "base_srd_id": "skeleton",
                        "name": "Flaming Skeleton",
                        "name_fr": "Squelette enflammé",
                        "description": "Un squelette nimbé de flammes bleues.",
                        "stat_overrides": {
                            "hp": 18,
                            "ac": 14,
                            "attack_bonus": 5,
                            "damage_dice": "1d6+2",
                            "damage_type": "fire",
                            "damage_immunities": ["fire"],
                        },
                    }
                ],
            },
            "pending_encounter": {
                "monster_ids": ["custom:squelette-enflamme", "skeleton"],
                "intro_played": True,
                "intro_text": "Les morts s'embrasent.",
            },
        },
    )
    published: list[tuple[str, dict]] = []

    async def capture(_session_id, event_type, payload, **_kwargs):
        published.append((event_type, payload))

    monkeypatch.setattr(ws_game, "_sync_ai_control_from_db", AsyncMock(return_value=False))
    monkeypatch.setattr(ws_game.session_manager, "save_state", AsyncMock())
    monkeypatch.setattr(ws_game, "persist_narration", AsyncMock())
    monkeypatch.setattr(ws_game.event_bus, "publish_to_session", capture)

    await ws_game._handle_start_combat("session-custom", active, db=object())

    custom = active.state_data["combatants"]["custom:squelette_enflamme_1"]
    assert custom["hp"] == 18
    assert custom["hp_max"] == 18
    assert custom["ac"] == 14
    assert custom["attack_bonus"] == 5
    assert custom["damage_notation"] == "1d6+2"
    assert custom["damage_immunities"] == ["fire"]
    assert custom["actions"][0]["damage_type"] == "fire"
    assert active.state_data["encounter_monsters"]["custom:squelette_enflamme"]["base_srd_id"] == (
        "skeleton"
    )

    combat_start = next(
        payload for event_type, payload in published if event_type == "combat_start"
    )
    custom_payload = next(
        item for item in combat_start["combatants"] if item["id"] == "custom:squelette_enflamme_1"
    )
    assert custom_payload["hp_max"] == 18
    assert custom_payload["description"] == "Un squelette nimbé de flammes bleues."
    assert custom_payload["damage_immunities"] == ["fire"]
