"""Combat mechanics — pure D&D SRD 5.2 logic.

Covers:
- Initiative rolls and ordering
- Attack rolls (melee, ranged; crit on natural 20, fumble on natural 1)
- Damage rolls (dice doubled on critical hit, not the modifier)
- Death saving throws (3 successes = stable, 3 failures = dead)
- Action economy per turn (action, bonus action, reaction, movement)

No I/O, no async, no database access.
"""
from __future__ import annotations

import re
import random
from dataclasses import dataclass, field
from typing import List, Optional

from app.engine.ability_checks import _resolve_d20, ability_modifier
from app.engine.dice import roll_dice


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------


@dataclass
class InitiativeResult:
    """Initiative roll for one combatant."""

    combatant_id: str
    d20_roll: int
    dex_modifier: int
    total: int


@dataclass
class AttackResult:
    """Full breakdown of an attack roll."""

    d20_roll: int
    all_rolls: List[int]       # both dice under advantage/disadvantage
    attack_bonus: int
    total: int
    target_ac: int
    hit: bool
    critical: bool             # natural 20
    fumble: bool               # natural 1
    advantage: Optional[bool]  # True=adv, False=disadv, None=normal
    breakdown: str


@dataclass
class DamageResult:
    """Result of a damage roll (with optional critical doubling)."""

    notation: str
    rolls: List[int]   # all dice rolled (2× count on crit)
    modifier: int
    total: int         # always ≥ 0
    critical: bool


@dataclass
class DeathSaveResult:
    """Death saving throw (SRD 5.2 §Dying).

    - Natural 20  → critical_success: regain 1 HP (counts as 3 successes)
    - Roll ≥ 10   → success
    - Roll 2–9    → failure
    - Natural 1   → critical_failure: counts as 2 failures
    """

    d20_roll: int
    success: bool
    critical_success: bool
    critical_failure: bool


@dataclass
class ActionEconomy:
    """Tracks the actions available to a combatant on their turn."""

    action: bool = True
    bonus_action: bool = True
    reaction: bool = True
    movement: float = 9.0  # mètres restants
    movement_max: float = 9.0
    has_dashed: bool = False
    has_disengaged: bool = False

    def use_action(self) -> bool:
        """Consume the action. Returns False if already spent."""
        if not self.action:
            return False
        self.action = False
        return True

    def use_bonus_action(self) -> bool:
        """Consume the bonus action. Returns False if already spent."""
        if not self.bonus_action:
            return False
        self.bonus_action = False
        return True

    def use_reaction(self) -> bool:
        """Consume the reaction. Returns False if already spent."""
        if not self.reaction:
            return False
        self.reaction = False
        return True

    def spend_movement(self, meters: float) -> bool:
        """Spend movement. Returns False if insufficient movement remains."""
        if meters > self.movement:
            return False
        self.movement -= meters
        return True


# ---------------------------------------------------------------------------
# Regex for damage notation (no keep-highest/lowest — not used for damage)
# ---------------------------------------------------------------------------

_DMG_NOTATION = re.compile(
    r"^(?P<count>\d+)?d(?P<sides>\d+)(?P<mod>[+-]\d+)?$",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------


def roll_initiative(
    dex_score: int,
    combatant_id: str = "",
    rng: Optional[random.Random] = None,
) -> InitiativeResult:
    """Roll initiative (d20 + DEX modifier) for one combatant.

    Args:
        dex_score: Combatant's DEX ability score.
        combatant_id: Identifier (character name, monster tag, etc.).
        rng: Seeded Random for deterministic tests.
    """
    r = rng or random
    d20 = r.randint(1, 20)
    dex_mod = ability_modifier(dex_score)
    return InitiativeResult(
        combatant_id=combatant_id,
        d20_roll=d20,
        dex_modifier=dex_mod,
        total=d20 + dex_mod,
    )


def sort_initiative(results: List[InitiativeResult]) -> List[InitiativeResult]:
    """Sort combatants by initiative total (highest first).

    Ties are broken by DEX modifier (higher DEX wins).
    """
    return sorted(results, key=lambda r: (r.total, r.dex_modifier), reverse=True)


def roll_attack(
    attack_bonus: int,
    target_ac: int,
    advantage: Optional[bool] = None,
    rng: Optional[random.Random] = None,
) -> AttackResult:
    """Resolve an attack roll against a target AC.

    Rules (SRD 5.2 §Making an Attack):
    - Natural 20 always hits and is a critical hit (double damage dice).
    - Natural 1 always misses (fumble).
    - Otherwise: d20 + attack_bonus ≥ target_ac → hit.

    Args:
        attack_bonus: Total attack modifier (proficiency + ability mod + magic items).
        target_ac: Target's Armor Class.
        advantage: True=advantage, False=disadvantage, None=normal.
        rng: Seeded Random for tests.
    """
    d20, all_rolls = _resolve_d20(advantage, rng)
    total = d20 + attack_bonus

    critical = d20 == 20
    fumble = d20 == 1
    hit = critical or (not fumble and total >= target_ac)

    sign = f"+{attack_bonus}" if attack_bonus >= 0 else str(attack_bonus)
    adv_str = " (adv)" if advantage is True else " (dis)" if advantage is False else ""
    if critical:
        result_str = " → CRITICAL HIT!"
    elif fumble:
        result_str = " → FUMBLE (auto-miss)"
    else:
        result_str = f" vs AC {target_ac} {'✓' if hit else '✗'}"
    breakdown = f"{d20}{adv_str} {sign} = {total}{result_str}"

    return AttackResult(
        d20_roll=d20,
        all_rolls=all_rolls,
        attack_bonus=attack_bonus,
        total=total,
        target_ac=target_ac,
        hit=hit,
        critical=critical,
        fumble=fumble,
        advantage=advantage,
        breakdown=breakdown,
    )


def roll_damage(
    notation: str,
    critical: bool = False,
    rng: Optional[random.Random] = None,
) -> DamageResult:
    """Roll damage dice, doubling the dice count on a critical hit.

    SRD 5.2 §Critical Hits: on a crit, roll all of the attack's damage dice
    twice and add them together. Modifiers are NOT doubled.

    Args:
        notation: Damage expression, e.g. "1d8+3", "2d6", "1d4-1".
                  keep-highest / keep-lowest suffixes are NOT allowed.
        critical: If True, dice count is doubled.
        rng: Seeded Random for tests.

    Raises:
        ValueError: If the notation is invalid or uses keep-highest syntax.
    """
    cleaned = notation.strip().lower().replace(" ", "")

    # Support flat damage values (e.g. "1" for monsters with no damage dice)
    if cleaned.lstrip("+-").isdigit():
        flat = max(0, int(cleaned))
        return DamageResult(notation=notation, rolls=[], modifier=flat, total=flat, critical=False)

    m = _DMG_NOTATION.match(cleaned)
    if not m:
        raise ValueError(
            f"Invalid damage notation: '{notation}'. "
            "Expected format: [N]dS[+/-M] (e.g. '2d6+3')."
        )

    count = int(m.group("count") or 1)
    sides = int(m.group("sides"))
    modifier = int(m.group("mod") or 0)

    if sides < 2:
        raise ValueError(f"Damage dice must have at least 2 sides, got {sides}")
    if count < 1:
        raise ValueError(f"Must roll at least 1 damage die, got {count}")

    actual_count = count * 2 if critical else count
    rolls = roll_dice(sides, actual_count, rng)
    raw_total = sum(rolls) + modifier

    return DamageResult(
        notation=notation,
        rolls=rolls,
        modifier=modifier,
        total=max(0, raw_total),
        critical=critical,
    )


def roll_death_save(rng: Optional[random.Random] = None) -> DeathSaveResult:
    """Roll a death saving throw (SRD 5.2 §Dying).

    - Natural 20 → critical success (creature regains 1 HP, counts as 3 successes)
    - d20 ≥ 10   → success
    - d20 2–9    → failure
    - Natural 1  → critical failure (counts as 2 failures)

    The caller is responsible for tracking the running tally of successes/failures
    and determining stable/dead status.
    """
    r = rng or random
    d20 = r.randint(1, 20)
    return DeathSaveResult(
        d20_roll=d20,
        success=d20 >= 10,
        critical_success=d20 == 20,
        critical_failure=d20 == 1,
    )


def new_turn_economy(speed: float = 9.0) -> ActionEconomy:
    """Return a fresh ActionEconomy at the start of a combatant's turn.

    Args:
        speed: The combatant's base walking speed in metres (default 9 m = 30 ft).
    """
    return ActionEconomy(
        action=True,
        bonus_action=True,
        reaction=True,
        movement=speed,
        movement_max=speed,
        has_dashed=False,
        has_disengaged=False,
    )
