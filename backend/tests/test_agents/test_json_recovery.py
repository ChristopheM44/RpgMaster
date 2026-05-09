from __future__ import annotations

from app.agents.json_recovery import (
    build_default_combat_action,
    recover_partial_json_response,
    recover_structured_text_response,
)


def test_recover_partial_json_response_uses_safe_roleplay_for_truncated_text() -> None:
    recovered = recover_partial_json_response(
        '{"action_type": "attack", "target": "goblin_1", "roleplay_text": "Je',
        character_name="Aria",
        game_state={},
        safe_recovered_roleplay=lambda action, description, target, state: "Aria agit.",
    )

    assert recovered is not None
    assert recovered["action_type"] == "attack"
    assert recovered["target"] == "goblin_1"
    assert recovered["roleplay_text"] == "Aria agit."


def test_recover_structured_text_response_extracts_fields() -> None:
    recovered = recover_structured_text_response(
        "action: dodge\nroleplay_text: Je me mets à couvert.\nreasoning: Trop risqué."
    )

    assert recovered is not None
    assert recovered["action_type"] == "dodge"
    assert recovered["roleplay_text"] == "Je me mets à couvert."


def test_build_default_combat_action_attacks_default_target() -> None:
    recovered = build_default_combat_action(
        "...",
        character_name="Aria",
        game_state={"combatants": {"goblin_1": {"name": "Gobelin", "hp": 3}}},
        available_actions=["attack", "wait"],
        available_action_set=lambda actions: set(actions or []),
        select_default_enemy_target=lambda state: "goblin_1",
        combatant_name=lambda state, target: "Gobelin",
    )

    assert recovered is not None
    assert recovered["action_type"] == "attack"
    assert recovered["target"] == "goblin_1"
