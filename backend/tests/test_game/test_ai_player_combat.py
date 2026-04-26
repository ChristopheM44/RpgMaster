"""Test d'intégration Sprint 5 : combat 1 humain + 2 compagnons IA vs gobelins.

Scénario :
- 1 joueur humain : Aria (Guerrière)
- 2 compagnons IA : Thorin (brave+noble) et Elara (arcane+cautious)
- 3 ennemis gobelins

Le LLM Ollama est mocké — tous les appels LLM retournent une réponse JSON fixe.

Ce test vérifie :
1. setup_combat avec is_ai_controlled=True est sérialisé/désérialisé correctement
2. AIPlayerManager.process_ai_turns() déclenche les agents IA dans le bon ordre
3. Les actions IA sont validées puis dispatché via ActionResolver
4. Un scénario complet : humain agit → 2 IA agissent → gobelins → round suivant
"""
from __future__ import annotations

import json
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.player_agent import PlayerAgent
from app.agents.schemas import PlayerPersonality
from app.game.ai_player_manager import AIPlayerManager
from app.game.session_manager import ActiveSession
from app.game.turn_manager import CombatantInfo, TurnManager
from app.models.session import SessionStatus


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _attack_json(character_name: str, target: str = "goblin_1") -> str:
    return json.dumps({
        "action_type": "attack",
        "action_description": f"{character_name} attaque",
        "target": target,
        "params": {"weapon": "épée"},
        "roleplay_text": f"{character_name} frappe le gobelin avec détermination !",
        "inner_reasoning": "Attaque le gobelin le plus proche.",
    }, ensure_ascii=False)


def _wait_json(character_name: str) -> str:
    return json.dumps({
        "action_type": "wait",
        "action_description": "Attend",
        "target": None,
        "params": {},
        "roleplay_text": f"{character_name} observe la situation.",
        "inner_reasoning": "Conserve les ressources.",
    }, ensure_ascii=False)


def _build_game_state() -> Dict[str, Any]:
    return {
        "phase": "COMBAT",
        "combatants": {
            "aria_1": {"hp": 30, "ac": 16, "attack_bonus": 5, "damage_notation": "1d8+3"},
            "thorin_1": {"hp": 28, "ac": 15, "attack_bonus": 4, "damage_notation": "1d8+2"},
            "elara_1": {"hp": 10, "ac": 12, "attack_bonus": 3, "damage_notation": "1d6"},
            "goblin_1": {"hp": 7, "ac": 15, "attack_bonus": 4, "damage_notation": "1d6+2"},
            "goblin_2": {"hp": 7, "ac": 15, "attack_bonus": 4, "damage_notation": "1d6+2"},
            "goblin_3": {"hp": 7, "ac": 15, "attack_bonus": 4, "damage_notation": "1d6+2"},
        },
        "characters": {
            "thorin_1": {
                "current_hp": 28,
                "max_hp": 28,
                "spell_slots": {},
                "inventory": [],
            },
            "elara_1": {
                "current_hp": 10,
                "max_hp": 10,
                "spell_slots": {"1": 2},
                "inventory": [],
            },
        },
    }


def _build_combatants() -> list:
    """Builds combatant list: 1 human + 2 AI players + 3 goblins."""
    return [
        CombatantInfo("aria_1", "Aria", dex_score=14, is_player=True, is_ai_controlled=False),
        CombatantInfo("thorin_1", "Thorin", dex_score=12, is_player=True, is_ai_controlled=True),
        CombatantInfo("elara_1", "Elara", dex_score=16, is_player=True, is_ai_controlled=True),
        CombatantInfo("goblin_1", "Gobelin 1", dex_score=8, is_player=False, is_ai_controlled=False),
        CombatantInfo("goblin_2", "Gobelin 2", dex_score=8, is_player=False, is_ai_controlled=False),
        CombatantInfo("goblin_3", "Gobelin 3", dex_score=8, is_player=False, is_ai_controlled=False),
    ]


# ---------------------------------------------------------------------------
# TurnEntry serialization with is_ai_controlled
# ---------------------------------------------------------------------------


def test_turn_entry_serialization_preserves_is_ai_controlled() -> None:
    """TurnEntry.to_dict() / from_dict() doit conserver is_ai_controlled."""
    from app.game.turn_manager import TurnEntry

    entry = TurnEntry(
        combatant_id="thorin_1",
        name="Thorin",
        initiative_total=15,
        is_player=True,
        is_ai_controlled=True,
    )
    d = entry.to_dict()
    assert d["is_ai_controlled"] is True

    restored = TurnEntry.from_dict(d)
    assert restored.is_ai_controlled is True
    assert restored.combatant_id == "thorin_1"


def test_turn_entry_serialization_default_false() -> None:
    """is_ai_controlled vaut False par défaut à la désérialisation."""
    from app.game.turn_manager import TurnEntry

    entry = TurnEntry(
        combatant_id="aria_1",
        name="Aria",
        initiative_total=18,
        is_player=True,
        is_ai_controlled=False,
    )
    d = entry.to_dict()
    # Simulate old serialized data without the field
    d.pop("is_ai_controlled")
    restored = TurnEntry.from_dict(d)
    assert restored.is_ai_controlled is False


# ---------------------------------------------------------------------------
# TurnManager.setup_combat with is_ai_controlled
# ---------------------------------------------------------------------------


def test_setup_combat_marks_ai_controlled_entries() -> None:
    """setup_combat() propage is_ai_controlled sur les TurnEntry."""
    import random

    tm = TurnManager()
    rng = random.Random(42)
    order = tm.setup_combat(_build_combatants(), rng=rng)

    entry_by_id = {e.combatant_id: e for e in order}
    assert entry_by_id["aria_1"].is_ai_controlled is False
    assert entry_by_id["thorin_1"].is_ai_controlled is True
    assert entry_by_id["elara_1"].is_ai_controlled is True
    assert entry_by_id["goblin_1"].is_ai_controlled is False


def test_setup_combat_full_serialization() -> None:
    """Le TurnManager peut être sérialisé et restauré avec is_ai_controlled."""
    import random

    tm = TurnManager()
    tm.setup_combat(_build_combatants(), rng=random.Random(7))

    data = tm.to_dict()
    tm2 = TurnManager()
    tm2.load_dict(data)

    for orig, restored in zip(tm._order, tm2._order):
        assert orig.is_ai_controlled == restored.is_ai_controlled


# ---------------------------------------------------------------------------
# AIPlayerManager.process_ai_turns
# ---------------------------------------------------------------------------


def _make_active_session(state_data: Dict[str, Any]) -> ActiveSession:
    """Build an ActiveSession in COMBAT phase with a seeded turn order."""
    import random

    active = ActiveSession(
        session_id="test_session",
        phase=SessionStatus.COMBAT,
        state_data=state_data,
    )
    active.turn_manager.setup_combat(_build_combatants(), rng=random.Random(99))
    return active


async def test_process_ai_turns_skips_human_turn() -> None:
    """process_ai_turns() ne fait rien si le tour courant est un humain."""
    state = _build_game_state()
    active = _make_active_session(state)

    # Force current turn to human player Aria
    for i, entry in enumerate(active.turn_manager._order):
        if entry.combatant_id == "aria_1":
            active.turn_manager._index = i
            break

    resolver = MagicMock()
    resolver.resolve = AsyncMock()

    ai_manager = AIPlayerManager()
    triggered = await ai_manager.process_ai_turns("test_session", active, resolver)

    assert triggered == 0
    resolver.resolve.assert_not_called()


async def test_process_ai_turns_triggers_ai_action() -> None:
    """process_ai_turns() appelle le PlayerAgent quand c'est son tour."""
    state = _build_game_state()
    active = _make_active_session(state)

    # Register Thorin's AI agent
    thorin_agent = PlayerAgent(
        character_id="thorin_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["brave", "noble"]),
        client=MagicMock(),
    )
    active.ai_players["thorin_1"] = thorin_agent

    # Force current turn to Thorin (AI)
    for i, entry in enumerate(active.turn_manager._order):
        if entry.combatant_id == "thorin_1":
            active.turn_manager._index = i
            break

    # Mock LLM response
    with patch.object(
        thorin_agent._client, "chat", new=AsyncMock(return_value=_attack_json("Thorin"))
    ):
        resolver = MagicMock()
        resolver.resolve = AsyncMock()

        # Mock event bus to avoid real async queue
        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
            ai_manager = AIPlayerManager()
            triggered = await ai_manager.process_ai_turns("test_session", active, resolver)

    assert triggered >= 1
    resolver.resolve.assert_called()
    call_kwargs = resolver.resolve.call_args.kwargs
    assert call_kwargs["character_id"] == "thorin_1"
    assert call_kwargs["action_type"] == "attack"


async def test_process_ai_turns_multiple_consecutive_ai() -> None:
    """process_ai_turns() enchaîne tous les tours IA consécutifs."""
    state = _build_game_state()
    active = _make_active_session(state)

    thorin_agent = PlayerAgent(
        character_id="thorin_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["brave"]),
        client=MagicMock(),
    )
    elara_agent = PlayerAgent(
        character_id="elara_1",
        character_name="Elara",
        personality=PlayerPersonality(traits=["arcane", "cautious"]),
        client=MagicMock(),
    )
    active.ai_players["thorin_1"] = thorin_agent
    active.ai_players["elara_1"] = elara_agent

    # Build a controlled order: Thorin (AI) → Elara (AI) → Aria (human)
    from app.engine.combat import ActionEconomy
    from app.game.turn_manager import TurnEntry

    active.turn_manager._order = [
        TurnEntry("thorin_1", "Thorin", 18, True, True),
        TurnEntry("elara_1", "Elara", 15, True, True),
        TurnEntry("aria_1", "Aria", 12, True, False),
        TurnEntry("goblin_1", "Gobelin 1", 8, False, False),
    ]
    active.turn_manager._index = 0

    with patch.object(thorin_agent._client, "chat", new=AsyncMock(
        return_value=_attack_json("Thorin")
    )), patch.object(elara_agent._client, "chat", new=AsyncMock(
        return_value=_attack_json("Elara", target="goblin_2")
    )):
        resolver = MagicMock()
        resolver.resolve = AsyncMock()

        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
            ai_manager = AIPlayerManager()
            triggered = await ai_manager.process_ai_turns("test_session", active, resolver)

    # Both AI players acted, stopped at Aria (human)
    assert triggered == 2
    assert resolver.resolve.call_count == 2

    # Current turn should now be Aria (human)
    current = active.turn_manager.current_turn
    assert current is not None
    assert current.combatant_id == "aria_1"
    assert current.is_ai_controlled is False


async def test_process_ai_turns_validates_and_falls_back_to_wait() -> None:
    """Si l'action IA est invalide, process_ai_turns() dispatch 'wait' à la place."""
    state = _build_game_state()
    # Thorin at 0 HP — any action except 'wait' is invalid
    state["characters"]["thorin_1"]["current_hp"] = 0

    active = _make_active_session(state)
    thorin_agent = PlayerAgent(
        character_id="thorin_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["brave"]),
        client=MagicMock(),
    )
    active.ai_players["thorin_1"] = thorin_agent

    from app.game.turn_manager import TurnEntry

    active.turn_manager._order = [
        TurnEntry("thorin_1", "Thorin", 18, True, True),
        TurnEntry("aria_1", "Aria", 12, True, False),
    ]
    active.turn_manager._index = 0

    # LLM says 'attack', but validate_action should reject it
    with patch.object(thorin_agent._client, "chat", new=AsyncMock(
        return_value=_attack_json("Thorin")
    )):
        resolver = MagicMock()
        resolver.resolve = AsyncMock()

        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
            ai_manager = AIPlayerManager()
            triggered = await ai_manager.process_ai_turns("test_session", active, resolver)

    assert triggered == 1
    # The resolver was still called, but with 'wait'
    call_kwargs = resolver.resolve.call_args.kwargs
    assert call_kwargs["action_type"] == "wait"


async def test_process_ai_turns_no_agent_registered_skips_entry() -> None:
    """Si aucun PlayerAgent n'est enregistré pour un tour IA, ce tour est sauté."""
    state = _build_game_state()
    active = _make_active_session(state)
    # No agents registered in ai_players

    from app.game.turn_manager import TurnEntry

    active.turn_manager._order = [
        TurnEntry("thorin_1", "Thorin", 18, True, True),  # AI but no agent registered
        TurnEntry("aria_1", "Aria", 12, True, False),      # human
    ]
    active.turn_manager._index = 0

    resolver = MagicMock()
    resolver.resolve = AsyncMock()

    with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
        ai_manager = AIPlayerManager()
        triggered = await ai_manager.process_ai_turns("test_session", active, resolver)

    assert triggered == 0
    resolver.resolve.assert_not_called()
    # Skipped Thorin, current is now Aria
    assert active.turn_manager.current_turn.combatant_id == "aria_1"


async def test_process_ai_turns_stops_at_ai_controlled_monster() -> None:
    """Les monstres automatiques ne passent pas par PlayerAgent.

    Ils restent au tour courant pour que ws_game._handle_ai_turns les résolve
    via la branche mécanique des monstres.
    """
    state = _build_game_state()
    active = _make_active_session(state)

    from app.game.turn_manager import TurnEntry

    active.turn_manager._order = [
        TurnEntry("poisonous_snake_1", "Serpent venimeux", 18, False, True),
        TurnEntry("aria_1", "Aria", 12, True, False),
    ]
    active.turn_manager._index = 0

    resolver = MagicMock()
    resolver.resolve = AsyncMock()

    with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
        ai_manager = AIPlayerManager()
        triggered = await ai_manager.process_ai_turns("test_session", active, resolver)

    assert triggered == 0
    resolver.resolve.assert_not_called()
    assert active.turn_manager.current_turn.combatant_id == "poisonous_snake_1"
    assert active.turn_manager.current_turn.is_player is False


# ---------------------------------------------------------------------------
# Scénario complet : 1 humain + 2 IA vs gobelins (1 round)
# ---------------------------------------------------------------------------


async def test_full_combat_round_human_then_ai_then_monsters() -> None:
    """Scénario d'un round complet : Aria (humain) → Thorin (IA) → Elara (IA) → gobelins.

    Vérifie que :
    - L'humain agit manuellement (pas de déclenchement automatique)
    - Après l'action humaine, les deux compagnons IA agissent
    - Le tour s'arrête aux gobelins (non-IA, non-joueur)
    """
    from app.game.turn_manager import TurnEntry

    state = _build_game_state()
    active = ActiveSession(
        session_id="full_combat_session",
        phase=SessionStatus.COMBAT,
        state_data=state,
    )

    # Controlled order : Aria → Thorin → Elara → Gobelin 1 → Gobelin 2 → Gobelin 3
    active.turn_manager._order = [
        TurnEntry("aria_1", "Aria", 20, True, False),
        TurnEntry("thorin_1", "Thorin", 16, True, True),
        TurnEntry("elara_1", "Elara", 14, True, True),
        TurnEntry("goblin_1", "Gobelin 1", 10, False, True),
        TurnEntry("goblin_2", "Gobelin 2", 8, False, True),
        TurnEntry("goblin_3", "Gobelin 3", 6, False, True),
    ]
    active.turn_manager._index = 0
    active.turn_manager._mode = "combat"
    active.turn_manager._round = 1

    thorin_agent = PlayerAgent(
        character_id="thorin_1",
        character_name="Thorin",
        personality=PlayerPersonality(traits=["brave", "noble"]),
        client=MagicMock(),
    )
    elara_agent = PlayerAgent(
        character_id="elara_1",
        character_name="Elara",
        personality=PlayerPersonality(traits=["arcane", "cautious"]),
        client=MagicMock(),
    )
    active.ai_players["thorin_1"] = thorin_agent
    active.ai_players["elara_1"] = elara_agent

    # --- Step 1 : Aria (human) acts — simulated manually ---
    assert active.turn_manager.current_turn.combatant_id == "aria_1"
    # Human action is dispatched by ws_game (not by AI manager)
    # Advance turn to Thorin
    active.turn_manager.next_turn()
    assert active.turn_manager.current_turn.combatant_id == "thorin_1"

    # --- Step 2 : AI companions act ---
    with patch.object(thorin_agent._client, "chat", new=AsyncMock(
        return_value=_attack_json("Thorin", target="goblin_1")
    )), patch.object(elara_agent._client, "chat", new=AsyncMock(
        return_value=_attack_json("Elara", target="goblin_2")
    )):
        resolver = MagicMock()
        resolver.resolve = AsyncMock()

        with patch("app.game.ai_player_manager.event_bus.publish_to_session", new=AsyncMock()):
            ai_manager = AIPlayerManager()
            triggered = await ai_manager.process_ai_turns(
                "full_combat_session", active, resolver
            )

    assert triggered == 2, "Thorin et Elara doivent avoir agi"
    assert resolver.resolve.call_count == 2

    # --- Step 3 : current turn should be Gobelin 1 (monster handled by ws_game) ---
    current = active.turn_manager.current_turn
    assert current.combatant_id == "goblin_1"
    assert current.is_player is False
    assert current.is_ai_controlled is True
