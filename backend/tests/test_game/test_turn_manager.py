"""Tests for game/turn_manager.py — combat and exploration turn order."""
from __future__ import annotations

import random

import pytest

from app.game.turn_manager import CombatantInfo, TurnEntry, TurnManager


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def players() -> list:
    return [
        CombatantInfo("hero_1", "Aria", dex_score=14, is_player=True, speed=30),
        CombatantInfo("hero_2", "Borin", dex_score=8, is_player=True, speed=25),
    ]


@pytest.fixture
def npcs() -> list:
    return [
        CombatantInfo("goblin_1", "Goblin A", dex_score=12, is_player=False, speed=30),
        CombatantInfo("goblin_2", "Goblin B", dex_score=12, is_player=False, speed=30),
    ]


@pytest.fixture
def all_combatants(players, npcs) -> list:
    return players + npcs


@pytest.fixture
def manager() -> TurnManager:
    return TurnManager()


@pytest.fixture
def seeded_rng() -> random.Random:
    return random.Random(42)


# ---------------------------------------------------------------------------
# setup_combat
# ---------------------------------------------------------------------------


class TestSetupCombat:
    def test_returns_sorted_entries(self, manager, all_combatants, seeded_rng) -> None:
        order = manager.setup_combat(all_combatants, rng=seeded_rng)
        assert len(order) == 4
        # Verify descending initiative order
        totals = [e.initiative_total for e in order]
        assert totals == sorted(totals, reverse=True)

    def test_mode_is_combat(self, manager, all_combatants, seeded_rng) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        assert manager.mode == "combat"

    def test_round_starts_at_one(self, manager, all_combatants, seeded_rng) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        assert manager.round_number == 1

    def test_current_turn_is_first_entry(self, manager, all_combatants, seeded_rng) -> None:
        order = manager.setup_combat(all_combatants, rng=seeded_rng)
        assert manager.current_turn is order[0]

    def test_empty_combatants_raises(self, manager) -> None:
        with pytest.raises(ValueError):
            manager.setup_combat([])

    def test_all_ids_present(self, manager, all_combatants, seeded_rng) -> None:
        order = manager.setup_combat(all_combatants, rng=seeded_rng)
        ids = {e.combatant_id for e in order}
        expected = {c.combatant_id for c in all_combatants}
        assert ids == expected

    def test_action_economy_is_fresh(self, manager, all_combatants, seeded_rng) -> None:
        order = manager.setup_combat(all_combatants, rng=seeded_rng)
        for entry in order:
            assert entry.action_economy.action is True
            assert entry.action_economy.bonus_action is True


# ---------------------------------------------------------------------------
# setup_exploration
# ---------------------------------------------------------------------------


class TestSetupExploration:
    def test_preserves_order(self, manager, players) -> None:
        order = manager.setup_exploration(players)
        assert [e.combatant_id for e in order] == [c.combatant_id for c in players]

    def test_mode_is_exploration(self, manager, players) -> None:
        manager.setup_exploration(players)
        assert manager.mode == "exploration"

    def test_initiative_total_is_zero(self, manager, players) -> None:
        order = manager.setup_exploration(players)
        assert all(e.initiative_total == 0 for e in order)

    def test_empty_participants_raises(self, manager) -> None:
        with pytest.raises(ValueError):
            manager.setup_exploration([])


# ---------------------------------------------------------------------------
# next_turn / round counter
# ---------------------------------------------------------------------------


class TestNextTurn:
    def test_advances_to_second_combatant(self, manager, all_combatants, seeded_rng) -> None:
        order = manager.setup_combat(all_combatants, rng=seeded_rng)
        first_id = manager.current_turn.combatant_id
        manager.next_turn()
        assert manager.current_turn.combatant_id != first_id
        assert manager.current_turn is order[1]

    def test_wraps_to_first_and_increments_round(
        self, manager, all_combatants, seeded_rng
    ) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        first_id = manager.current_turn.combatant_id
        # Advance through all 4 combatants
        for _ in range(len(all_combatants)):
            manager.next_turn()
        assert manager.current_turn.combatant_id == first_id
        assert manager.round_number == 2

    def test_action_economy_reset_on_next_turn(
        self, manager, all_combatants, seeded_rng
    ) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        # Spend the action of the first combatant
        manager.current_turn.action_economy.use_action()
        assert manager.current_turn.action_economy.action is False
        # Advance
        manager.next_turn()
        # Come back to first
        for _ in range(len(all_combatants) - 1):
            manager.next_turn()
        # First combatant should have a fresh economy
        assert manager.current_turn.action_economy.action is True

    def test_returns_none_when_empty(self, manager) -> None:
        assert manager.next_turn() is None


# ---------------------------------------------------------------------------
# remove_combatant
# ---------------------------------------------------------------------------


class TestRemoveCombatant:
    def test_remove_existing_returns_true(self, manager, all_combatants, seeded_rng) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        assert manager.remove_combatant("goblin_1") is True

    def test_remove_missing_returns_false(self, manager, all_combatants, seeded_rng) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        assert manager.remove_combatant("unknown_id") is False

    def test_order_shrinks(self, manager, all_combatants, seeded_rng) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        manager.remove_combatant("goblin_1")
        ids = {e.combatant_id for e in manager._order}
        assert "goblin_1" not in ids
        assert len(manager._order) == 3

    def test_all_npcs_removed_after_removing_all_npcs(
        self, manager, all_combatants, seeded_rng
    ) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        manager.remove_combatant("goblin_1")
        manager.remove_combatant("goblin_2")
        assert manager.all_npcs_removed() is True

    def test_all_npcs_not_removed_when_npc_present(
        self, manager, all_combatants, seeded_rng
    ) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        assert manager.all_npcs_removed() is False


# ---------------------------------------------------------------------------
# get_player_entries / get_npc_entries
# ---------------------------------------------------------------------------


class TestFiltering:
    def test_get_player_entries(self, manager, all_combatants, seeded_rng) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        entries = manager.get_player_entries()
        assert all(e.is_player for e in entries)
        assert len(entries) == 2

    def test_get_npc_entries(self, manager, all_combatants, seeded_rng) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        entries = manager.get_npc_entries()
        assert all(not e.is_player for e in entries)
        assert len(entries) == 2


# ---------------------------------------------------------------------------
# reset
# ---------------------------------------------------------------------------


class TestReset:
    def test_reset_clears_state(self, manager, all_combatants, seeded_rng) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        manager.reset()
        assert manager.current_turn is None
        assert manager.mode is None
        assert manager.round_number == 0


# ---------------------------------------------------------------------------
# Serialization round-trip
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_combat_roundtrip(self, manager, all_combatants, seeded_rng) -> None:
        manager.setup_combat(all_combatants, rng=seeded_rng)
        manager.next_turn()
        snapshot = manager.to_dict()

        restored = TurnManager()
        restored.load_dict(snapshot)

        assert restored.mode == manager.mode
        assert restored.round_number == manager.round_number
        assert restored._index == manager._index
        assert len(restored._order) == len(manager._order)
        assert restored.current_turn.combatant_id == manager.current_turn.combatant_id

    def test_exploration_roundtrip(self, manager, players) -> None:
        manager.setup_exploration(players)
        snapshot = manager.to_dict()

        restored = TurnManager()
        restored.load_dict(snapshot)

        assert restored.mode == "exploration"
        assert [e.combatant_id for e in restored._order] == [
            e.combatant_id for e in manager._order
        ]
