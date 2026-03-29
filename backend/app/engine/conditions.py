"""D&D SRD 5.2 conditions — pure logic, no I/O.

The 14 standard conditions plus exhaustion (tracked as a level 0–6).
Each condition is mapped to a frozen ConditionEffects dataclass describing
its mechanical impact on combat and ability checks.

Special cases documented inline:
- PRONE: melee attacks against it have advantage; ranged attacks have disadvantage
         (not the simple attacked_advantage / attacked_disadvantage split).
- PETRIFIED: also grants resistance to all damage (not encoded here;
             handled at the damage-application layer).
- CHARMED: prevents attacking the charmer; charmer has advantage on social checks
           (encoded as notes, not as combat toggles).
- FRIGHTENED: can't willingly move closer to the source (position-tracking concern,
              not encoded in ConditionEffects).
- EXHAUSTION level 3+: disadvantage on attack rolls and saving throws
                       (see ExhaustionEffects).
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Set


# ---------------------------------------------------------------------------
# Condition enum
# ---------------------------------------------------------------------------


class Condition(str, Enum):
    BLINDED = "blinded"
    CHARMED = "charmed"
    DEAFENED = "deafened"
    FRIGHTENED = "frightened"
    GRAPPLED = "grappled"
    INCAPACITATED = "incapacitated"
    INVISIBLE = "invisible"
    PARALYZED = "paralyzed"
    PETRIFIED = "petrified"
    POISONED = "poisoned"
    PRONE = "prone"
    RESTRAINED = "restrained"
    STUNNED = "stunned"
    UNCONSCIOUS = "unconscious"


# ---------------------------------------------------------------------------
# ConditionEffects dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ConditionEffects:
    """Mechanical effects of a single condition.

    Fields use the combatant's perspective:
    - *_self  : affects the afflicted creature's own rolls
    - *_vs    : affects rolls made *against* the afflicted creature
    """

    # Afflicted creature's attack rolls
    attack_disadvantage: bool = False
    attack_advantage: bool = False

    # Rolls made against the afflicted creature
    melee_attacked_advantage: bool = False    # melee attacks have advantage vs this creature
    ranged_attacked_disadvantage: bool = False  # ranged attacks have disadvantage vs this creature
    attacked_advantage: bool = False           # ALL attacks (melee+ranged) have advantage
    attacked_disadvantage: bool = False        # ALL attacks have disadvantage

    # Critical hit rule: melee hits within 5 ft are automatic crits
    auto_crit_melee: bool = False

    # Mobility
    speed_zero: bool = False
    # speed_halved is handled by ExhaustionEffects for exhaustion level 2+

    # Action restrictions
    no_actions: bool = False
    no_reactions: bool = False
    no_bonus_actions: bool = False

    # Automatic save failures (STR and/or DEX)
    fail_str_saves: bool = False
    fail_dex_saves: bool = False

    # Concentration (losing this condition doesn't itself break concentration,
    # but some conditions imply you can't maintain it)
    breaks_concentration: bool = False

    # Ability check disadvantage for the afflicted creature
    ability_check_disadvantage: bool = False


# ---------------------------------------------------------------------------
# SRD 5.2 condition effects table
# ---------------------------------------------------------------------------


CONDITION_EFFECTS: dict[Condition, ConditionEffects] = {
    # Blinded: can't see → disadv on own attacks, adv against it
    Condition.BLINDED: ConditionEffects(
        attack_disadvantage=True,
        attacked_advantage=True,
    ),

    # Charmed: can't attack the charmer (position/target logic, not toggles here)
    Condition.CHARMED: ConditionEffects(),

    # Deafened: can't hear (no direct combat mechanic in SRD combat rolls)
    Condition.DEAFENED: ConditionEffects(),

    # Frightened: disadv on attacks/checks while source is in sight;
    # can't move closer (movement logic outside engine)
    Condition.FRIGHTENED: ConditionEffects(
        attack_disadvantage=True,
        ability_check_disadvantage=True,
    ),

    # Grappled: speed 0 (grappler can drag)
    Condition.GRAPPLED: ConditionEffects(
        speed_zero=True,
    ),

    # Incapacitated: no actions or reactions
    Condition.INCAPACITATED: ConditionEffects(
        no_actions=True,
        no_reactions=True,
        no_bonus_actions=True,
    ),

    # Invisible: adv on own attacks, disadv against it
    Condition.INVISIBLE: ConditionEffects(
        attack_advantage=True,
        attacked_disadvantage=True,
    ),

    # Paralyzed: incapacitated + speed 0 + auto-fail STR/DEX saves +
    #            all attacks have adv + melee crits within 5 ft
    Condition.PARALYZED: ConditionEffects(
        no_actions=True,
        no_reactions=True,
        no_bonus_actions=True,
        speed_zero=True,
        fail_str_saves=True,
        fail_dex_saves=True,
        attacked_advantage=True,
        auto_crit_melee=True,
    ),

    # Petrified: same as paralyzed + resistance to all damage (apply at damage layer)
    Condition.PETRIFIED: ConditionEffects(
        no_actions=True,
        no_reactions=True,
        no_bonus_actions=True,
        speed_zero=True,
        fail_str_saves=True,
        fail_dex_saves=True,
        attacked_advantage=True,
        auto_crit_melee=True,
    ),

    # Poisoned: disadv on attack rolls and ability checks
    Condition.POISONED: ConditionEffects(
        attack_disadvantage=True,
        ability_check_disadvantage=True,
    ),

    # Prone: disadv on own attacks; melee attacks have adv vs it, ranged have disadv
    Condition.PRONE: ConditionEffects(
        attack_disadvantage=True,
        melee_attacked_advantage=True,
        ranged_attacked_disadvantage=True,
    ),

    # Restrained: disadv on own attacks + DEX saves; adv against it; speed 0
    Condition.RESTRAINED: ConditionEffects(
        attack_disadvantage=True,
        attacked_advantage=True,
        speed_zero=True,
        fail_dex_saves=False,  # restrained → disadv on DEX saves (not auto-fail)
        # Note: restrained gives disadv on DEX saves, not auto-fail.
        # Handled separately by attack_disadvantage flag on saves if needed.
    ),

    # Stunned: incapacitated + speed 0 + auto-fail STR/DEX + adv attacks against it
    Condition.STUNNED: ConditionEffects(
        no_actions=True,
        no_reactions=True,
        no_bonus_actions=True,
        speed_zero=True,
        fail_str_saves=True,
        fail_dex_saves=True,
        attacked_advantage=True,
    ),

    # Unconscious: incapacitated + prone + speed 0 + auto-fail STR/DEX +
    #              adv attacks against it + melee crits + breaks concentration
    Condition.UNCONSCIOUS: ConditionEffects(
        no_actions=True,
        no_reactions=True,
        no_bonus_actions=True,
        speed_zero=True,
        fail_str_saves=True,
        fail_dex_saves=True,
        attacked_advantage=True,
        auto_crit_melee=True,
        breaks_concentration=True,
    ),
}


# ---------------------------------------------------------------------------
# Exhaustion (cumulative, level 0–6)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ExhaustionEffects:
    """Mechanical effects at a given exhaustion level (SRD 5.2 §Exhaustion).

    Effects are cumulative: level 3 includes all level 1 and 2 effects.
    """
    ability_check_disadvantage: bool = False   # level 1+
    speed_halved: bool = False                 # level 2+
    attack_and_save_disadvantage: bool = False  # level 3+
    max_hp_halved: bool = False                # level 4+
    speed_zero: bool = False                   # level 5+
    # level 6 = death (creature dies)


def exhaustion_effects(level: int) -> ExhaustionEffects:
    """Return the cumulative mechanical effects for a given exhaustion level.

    Args:
        level: 0 (no exhaustion) through 6 (dead).

    Raises:
        ValueError: If level is out of range.
    """
    if not 0 <= level <= 6:
        raise ValueError(f"Exhaustion level must be 0–6, got {level}")
    return ExhaustionEffects(
        ability_check_disadvantage=level >= 1,
        speed_halved=level >= 2,
        attack_and_save_disadvantage=level >= 3,
        max_hp_halved=level >= 4,
        speed_zero=level >= 5,
    )


# ---------------------------------------------------------------------------
# Helper query functions
# ---------------------------------------------------------------------------


def get_effects(condition: Condition) -> ConditionEffects:
    """Return the ConditionEffects for a given condition."""
    return CONDITION_EFFECTS[condition]


def has_attack_advantage(attacker_conditions: Set[Condition]) -> bool:
    """True if any of the attacker's conditions grant advantage on attack rolls."""
    return any(CONDITION_EFFECTS[c].attack_advantage for c in attacker_conditions)


def has_attack_disadvantage(attacker_conditions: Set[Condition]) -> bool:
    """True if any of the attacker's conditions impose disadvantage on attack rolls."""
    return any(CONDITION_EFFECTS[c].attack_disadvantage for c in attacker_conditions)


def resolve_attack_advantage(attacker_conditions: Set[Condition]) -> Optional[bool]:
    """Resolve the net advantage state for an attacker.

    SRD 5.2 §Advantage and Disadvantage: if you have both advantage and
    disadvantage from any sources, they cancel out (normal roll).

    Returns:
        True  = advantage
        False = disadvantage
        None  = normal roll
    """
    adv = has_attack_advantage(attacker_conditions)
    dis = has_attack_disadvantage(attacker_conditions)
    if adv and dis:
        return None
    if adv:
        return True
    if dis:
        return False
    return None


def is_attacked_with_advantage(
    target_conditions: Set[Condition],
    ranged: bool = False,
) -> bool:
    """True if attacks against the target have advantage.

    Args:
        target_conditions: Active conditions on the target.
        ranged: True for ranged attacks (affects PRONE ruling).
    """
    for c in target_conditions:
        fx = CONDITION_EFFECTS[c]
        if fx.attacked_advantage:
            return True
        if not ranged and fx.melee_attacked_advantage:
            return True
    return False


def is_attacked_with_disadvantage(
    target_conditions: Set[Condition],
    ranged: bool = False,
) -> bool:
    """True if attacks against the target have disadvantage.

    Args:
        target_conditions: Active conditions on the target.
        ranged: True for ranged attacks (affects PRONE ruling).
    """
    for c in target_conditions:
        fx = CONDITION_EFFECTS[c]
        if fx.attacked_disadvantage:
            return True
        if ranged and fx.ranged_attacked_disadvantage:
            return True
    return False


def resolve_attack_advantage_vs(
    target_conditions: Set[Condition],
    ranged: bool = False,
) -> Optional[bool]:
    """Resolve the net advantage state for attacks *against* the target.

    Returns:
        True  = advantage (attack with advantage)
        False = disadvantage
        None  = normal roll
    """
    adv = is_attacked_with_advantage(target_conditions, ranged)
    dis = is_attacked_with_disadvantage(target_conditions, ranged)
    if adv and dis:
        return None
    if adv:
        return True
    if dis:
        return False
    return None


def auto_crits_on_melee(target_conditions: Set[Condition]) -> bool:
    """True if melee hits within 5 ft against the target are automatic crits."""
    return any(CONDITION_EFFECTS[c].auto_crit_melee for c in target_conditions)


def auto_fails_str_save(target_conditions: Set[Condition]) -> bool:
    """True if the creature automatically fails STR saving throws."""
    return any(CONDITION_EFFECTS[c].fail_str_saves for c in target_conditions)


def auto_fails_dex_save(target_conditions: Set[Condition]) -> bool:
    """True if the creature automatically fails DEX saving throws."""
    return any(CONDITION_EFFECTS[c].fail_dex_saves for c in target_conditions)


def can_take_actions(conditions: Set[Condition]) -> bool:
    """True if the creature can take actions this turn."""
    return not any(CONDITION_EFFECTS[c].no_actions for c in conditions)


def can_take_reactions(conditions: Set[Condition]) -> bool:
    """True if the creature can take reactions."""
    return not any(CONDITION_EFFECTS[c].no_reactions for c in conditions)


def can_take_bonus_actions(conditions: Set[Condition]) -> bool:
    """True if the creature can take bonus actions."""
    return not any(CONDITION_EFFECTS[c].no_bonus_actions for c in conditions)


def breaks_concentration(conditions: Set[Condition]) -> bool:
    """True if any active condition immediately breaks concentration."""
    return any(CONDITION_EFFECTS[c].breaks_concentration for c in conditions)


def effective_speed(base_speed: int, conditions: Set[Condition], exhaustion_level: int = 0) -> int:
    """Return the effective speed in feet after applying conditions and exhaustion.

    Args:
        base_speed: Base walking speed in feet.
        conditions: Active conditions on the creature.
        exhaustion_level: Current exhaustion level (0–6).
    """
    # Speed 0 from conditions
    if any(CONDITION_EFFECTS[c].speed_zero for c in conditions):
        return 0

    speed = base_speed
    ex = exhaustion_effects(exhaustion_level)
    if ex.speed_zero:
        return 0
    if ex.speed_halved:
        speed = speed // 2

    return speed
