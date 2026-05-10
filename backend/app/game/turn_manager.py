"""Turn order manager — initiative (combat) and round-robin (exploration).

Handles:
- Combat: rolls initiative via ``engine.combat``, sorts highest-first, tracks
  the current combatant and their action economy.
- Exploration: simple round-robin order among participants.
- Serialization to/from a plain dict for storage in ``GameState.state_data``.

Pure logic: no I/O, no async, no database access.
"""
from __future__ import annotations

import random
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional

from app.engine.combat import ActionEconomy, new_turn_economy, roll_initiative, sort_initiative
from app.models.session import SessionStatus


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class CombatantInfo:
    """Minimal info needed to set up a combatant's turn entry."""

    combatant_id: str
    name: str
    dex_score: int
    is_player: bool
    speed: float = 9.0  # vitesse en mètres
    is_ai_controlled: bool = False  # True for AI companion players


@dataclass
class TurnEntry:
    """Represents one participant in the current turn order."""

    combatant_id: str
    name: str
    initiative_total: int  # 0 for exploration (order is positional)
    is_player: bool
    is_ai_controlled: bool = False  # True for AI companion players
    action_economy: ActionEconomy = field(default_factory=ActionEconomy)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "combatant_id": self.combatant_id,
            "name": self.name,
            "initiative_total": self.initiative_total,
            "is_player": self.is_player,
            "is_ai_controlled": self.is_ai_controlled,
            "action_economy": asdict(self.action_economy),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> TurnEntry:
        ae_data = data.get("action_economy", {})
        movement_max = ae_data.get("movement_max", ae_data.get("movement", 9.0))
        ae = ActionEconomy(
            action=ae_data.get("action", True),
            bonus_action=ae_data.get("bonus_action", True),
            reaction=ae_data.get("reaction", True),
            movement=ae_data.get("movement", movement_max),
            movement_max=movement_max,
            has_dashed=ae_data.get("has_dashed", False),
            has_disengaged=ae_data.get("has_disengaged", False),
        )
        return cls(
            combatant_id=data["combatant_id"],
            name=data["name"],
            initiative_total=data.get("initiative_total", 0),
            is_player=data.get("is_player", True),
            is_ai_controlled=data.get("is_ai_controlled", False),
            action_economy=ae,
        )


# ---------------------------------------------------------------------------
# TurnManager
# ---------------------------------------------------------------------------


class TurnManager:
    """Manages turn order for a single game phase.

    Two modes:

    - **combat** — initiative-based, highest roll first.  Set up with
      :meth:`setup_combat`.
    - **exploration** — round-robin in the order participants were added.
      Set up with :meth:`setup_exploration`.

    After setup, call :meth:`next_turn` to advance and :attr:`current_turn`
    to read the active entry.

    Usage::

        tm = TurnManager()
        combatants = [
            CombatantInfo("hero_1", "Aria", dex_score=14, is_player=True),
            CombatantInfo("goblin_1", "Goblin", dex_score=8, is_player=False),
        ]
        tm.setup_combat(combatants)
        entry = tm.current_turn          # highest-initiative combatant
        entry.action_economy.use_action()
        tm.next_turn()                   # advance to the next combatant
    """

    def __init__(self) -> None:
        self._order: List[TurnEntry] = []
        self._index: int = 0
        self._round: int = 0
        self._mode: Optional[str] = None  # "combat" | "exploration"

    # ------------------------------------------------------------------
    # Setup
    # ------------------------------------------------------------------

    def setup_combat(
        self,
        combatants: List[CombatantInfo],
        rng: Optional[random.Random] = None,
    ) -> List[TurnEntry]:
        """Roll initiative for all combatants and build the turn order.

        Args:
            combatants: All participants in this combat (players + NPCs).
            rng: Optional seeded RNG for deterministic tests.

        Returns:
            The ordered list of :class:`TurnEntry`, highest initiative first.
        """
        if not combatants:
            raise ValueError("Cannot set up combat with an empty combatant list.")

        initiative_results = [
            roll_initiative(c.dex_score, combatant_id=c.combatant_id, rng=rng)
            for c in combatants
        ]
        sorted_results = sort_initiative(initiative_results)

        combatant_by_id = {c.combatant_id: c for c in combatants}
        self._order = [
            TurnEntry(
                combatant_id=r.combatant_id,
                name=combatant_by_id[r.combatant_id].name,
                initiative_total=r.total,
                is_player=combatant_by_id[r.combatant_id].is_player,
                is_ai_controlled=combatant_by_id[r.combatant_id].is_ai_controlled,
                action_economy=new_turn_economy(combatant_by_id[r.combatant_id].speed),
            )
            for r in sorted_results
        ]
        self._index = 0
        self._round = 1
        self._mode = "combat"
        return list(self._order)

    def setup_exploration(self, participants: List[CombatantInfo]) -> List[TurnEntry]:
        """Set up a round-robin order for exploration.

        No initiative rolls — participants act in the order provided.

        Args:
            participants: All active participants.

        Returns:
            The ordered list of :class:`TurnEntry`.
        """
        if not participants:
            raise ValueError("Cannot set up exploration with an empty participant list.")

        self._order = [
            TurnEntry(
                combatant_id=p.combatant_id,
                name=p.name,
                initiative_total=0,
                is_player=p.is_player,
                is_ai_controlled=p.is_ai_controlled,
                action_economy=new_turn_economy(p.speed),
            )
            for p in participants
        ]
        self._index = 0
        self._round = 1
        self._mode = "exploration"
        return list(self._order)

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    @property
    def current_turn(self) -> Optional[TurnEntry]:
        """The :class:`TurnEntry` for the current turn, or None if not set up."""
        if not self._order:
            return None
        return self._order[self._index]

    @property
    def round_number(self) -> int:
        """Current round number (1-based, increments after the last participant acts)."""
        return self._round

    @property
    def mode(self) -> Optional[str]:
        """Current mode: ``'combat'``, ``'exploration'``, or ``None`` if not set up."""
        return self._mode

    def next_turn(self) -> Optional[TurnEntry]:
        """Advance to the next participant.

        Increments the round counter when wrapping back to the first entry.
        Resets the new participant's :class:`ActionEconomy` for their turn.

        Returns:
            The new current :class:`TurnEntry`, or None if the order is empty.
        """
        if not self._order:
            return None

        self._index += 1
        if self._index >= len(self._order):
            self._index = 0
            self._round += 1

        # Reset action economy for the new active combatant
        entry = self._order[self._index]
        entry.action_economy = new_turn_economy(entry.action_economy.movement_max)
        return entry

    def remove_combatant(self, combatant_id: str) -> bool:
        """Remove a combatant from the turn order (death, flee, incapacitation).

        Adjusts the current index to remain valid after removal.

        Args:
            combatant_id: The ID of the combatant to remove.

        Returns:
            True if the combatant was found and removed, False otherwise.
        """
        for i, entry in enumerate(self._order):
            if entry.combatant_id == combatant_id:
                self._order.pop(i)
                # Keep index valid: if we removed an entry before the current
                # position, step back. If we removed the current entry, keep the
                # same index so it now points at the next combatant.
                if i < self._index and self._index > 0:
                    self._index -= 1
                if self._index >= len(self._order) and self._order:
                    self._index = 0
                return True
        return False

    def get_player_entries(self) -> List[TurnEntry]:
        """Return only the player entries from the current order."""
        return [e for e in self._order if e.is_player]

    def get_npc_entries(self) -> List[TurnEntry]:
        """Return only the NPC/monster entries from the current order."""
        return [e for e in self._order if not e.is_player]

    def all_npcs_removed(self) -> bool:
        """Return True if no NPC entries remain (combat potentially over)."""
        return not any(not e.is_player for e in self._order)

    def reset(self) -> None:
        """Clear all state."""
        self._order = []
        self._index = 0
        self._round = 0
        self._mode = None

    # ------------------------------------------------------------------
    # Serialization (for GameState.state_data blob)
    # ------------------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        """Serialize current state to a plain dict for JSON storage."""
        return {
            "mode": self._mode,
            "round": self._round,
            "index": self._index,
            "order": [e.to_dict() for e in self._order],
        }

    def load_dict(self, data: Dict[str, Any]) -> None:
        """Restore state from a previously serialized dict."""
        self._mode = data.get("mode")
        self._round = data.get("round", 0)
        self._index = data.get("index", 0)
        self._order = [TurnEntry.from_dict(e) for e in data.get("order", [])]
