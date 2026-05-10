"""Spell mechanics — pure D&D SRD 5.2 logic.

Covers:
- Spell slot tables for full casters (Wizard, Cleric), half casters (Paladin, Ranger),
  and third casters (Eldritch Knight Fighter, Arcane Trickster Rogue)
- SpellSlots dataclass: use, restore, and query remaining slots
- Concentration tracking (one spell at a time; new concentration ends the previous one)
- Spell save DC calculation
- Spell attack roll (reuses AttackResult from combat.py)
- Concentration check when taking damage (CON save, DC = max(10, damage ÷ 2))
- Upcast damage: extra dice added per slot level above the spell's base level

No I/O, no async, no database access.
"""
from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from app.engine.ability_checks import _resolve_d20, ability_modifier, proficiency_bonus, saving_throw, Ability
from app.engine.combat import AttackResult, DamageResult, roll_attack, roll_damage


# ---------------------------------------------------------------------------
# Spell slot tables (SRD 5.2)
# ---------------------------------------------------------------------------


# Full casters: Wizard, Cleric, Druid, Bard, Sorcerer
# Key: character level → {slot_level: count}
FULL_CASTER_SLOTS: Dict[int, Dict[int, int]] = {
    1:  {1: 2},
    2:  {1: 3},
    3:  {1: 4, 2: 2},
    4:  {1: 4, 2: 3},
    5:  {1: 4, 2: 3, 3: 2},
    6:  {1: 4, 2: 3, 3: 3},
    7:  {1: 4, 2: 3, 3: 3, 4: 1},
    8:  {1: 4, 2: 3, 3: 3, 4: 2},
    9:  {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    10: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    11: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    12: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1},
    13: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    16: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2, 6: 1, 7: 1, 8: 1, 9: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 1, 7: 1, 8: 1, 9: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 1, 8: 1, 9: 1},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 3, 6: 2, 7: 2, 8: 1, 9: 1},
}

# Half casters: Paladin, Ranger (slots start at class level 2)
HALF_CASTER_SLOTS: Dict[int, Dict[int, int]] = {
    1:  {},
    2:  {1: 2},
    3:  {1: 3},
    4:  {1: 3},
    5:  {1: 4, 2: 2},
    6:  {1: 4, 2: 2},
    7:  {1: 4, 2: 3},
    8:  {1: 4, 2: 3},
    9:  {1: 4, 2: 3, 3: 2},
    10: {1: 4, 2: 3, 3: 2},
    11: {1: 4, 2: 3, 3: 3},
    12: {1: 4, 2: 3, 3: 3},
    13: {1: 4, 2: 3, 3: 3, 4: 1},
    14: {1: 4, 2: 3, 3: 3, 4: 1},
    15: {1: 4, 2: 3, 3: 3, 4: 2},
    16: {1: 4, 2: 3, 3: 3, 4: 2},
    17: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    18: {1: 4, 2: 3, 3: 3, 4: 3, 5: 1},
    19: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
    20: {1: 4, 2: 3, 3: 3, 4: 3, 5: 2},
}

# Third casters: Eldritch Knight (Fighter), Arcane Trickster (Rogue)
# Slots start at class level 3
THIRD_CASTER_SLOTS: Dict[int, Dict[int, int]] = {
    1:  {},
    2:  {},
    3:  {1: 2},
    4:  {1: 3},
    5:  {1: 3},
    6:  {1: 3},
    7:  {1: 4, 2: 2},
    8:  {1: 4, 2: 2},
    9:  {1: 4, 2: 2},
    10: {1: 4, 2: 3},
    11: {1: 4, 2: 3},
    12: {1: 4, 2: 3},
    13: {1: 4, 2: 3, 3: 2},
    14: {1: 4, 2: 3, 3: 2},
    15: {1: 4, 2: 3, 3: 2},
    16: {1: 4, 2: 3, 3: 3},
    17: {1: 4, 2: 3, 3: 3},
    18: {1: 4, 2: 3, 3: 3},
    19: {1: 4, 2: 3, 3: 3, 4: 1},
    20: {1: 4, 2: 3, 3: 3, 4: 1},
}

# Warlock Pact Magic slots: slot level is represented by the key, count by value.
WARLOCK_PACT_SLOTS: Dict[int, Dict[int, int]] = {
    1: {1: 1},
    2: {1: 2},
    3: {2: 2},
    4: {2: 2},
    5: {3: 2},
    6: {3: 2},
    7: {4: 2},
    8: {4: 2},
    9: {5: 2},
    10: {5: 2},
    11: {5: 3},
    12: {5: 3},
    13: {5: 3},
    14: {5: 3},
    15: {5: 3},
    16: {5: 3},
    17: {5: 4},
    18: {5: 4},
    19: {5: 4},
    20: {5: 4},
}


def starting_slots(caster_type: str, class_level: int) -> Dict[int, int]:
    """Return the spell slot counts for a caster at the given class level.

    Args:
        caster_type: One of "full", "half", "third", "warlock".
        class_level: Character's class level (1–20).

    Returns:
        Dict mapping slot level → count. Empty dict if no slots.

    Raises:
        ValueError: If caster_type is unknown or class_level is out of range.
    """
    if class_level < 1 or class_level > 20:
        raise ValueError(f"Class level must be 1–20, got {class_level}")

    tables: Dict[str, Dict[int, Dict[int, int]]] = {
        "full": FULL_CASTER_SLOTS,
        "half": HALF_CASTER_SLOTS,
        "third": THIRD_CASTER_SLOTS,
        "warlock": WARLOCK_PACT_SLOTS,
    }
    if caster_type not in tables:
        raise ValueError(
            f"Unknown caster_type '{caster_type}'. Use 'full', 'half', 'third', or 'warlock'."
        )

    return dict(tables[caster_type][class_level])  # copy to avoid mutation


# ---------------------------------------------------------------------------
# SpellSlots dataclass
# ---------------------------------------------------------------------------


@dataclass
class SpellSlots:
    """Tracks remaining spell slots by level.

    Slots are stored as a dict: {slot_level: remaining_count}.
    Missing keys mean zero slots of that level.
    """

    slots: Dict[int, int] = field(default_factory=dict)

    @classmethod
    def from_table(cls, caster_type: str, class_level: int) -> SpellSlots:
        """Create a fully-recharged SpellSlots from a caster type and level."""
        return cls(slots=starting_slots(caster_type, class_level))

    def has_slot(self, level: int) -> bool:
        """True if at least one slot of the given level remains."""
        return self.slots.get(level, 0) > 0

    def remaining(self, level: int) -> int:
        """Return the number of remaining slots of the given level."""
        return self.slots.get(level, 0)

    def use_slot(self, level: int) -> None:
        """Consume one slot of the given level.

        Raises:
            ValueError: If no slots of that level are available.
        """
        if not self.has_slot(level):
            raise ValueError(f"No spell slots of level {level} remaining.")
        self.slots[level] -= 1

    def restore(self, level: int, count: int = 1) -> None:
        """Restore up to `count` slots of the given level (e.g. after a long rest).

        The restored count is capped at the original maximum from the table.
        This method does not enforce caps — the caller should recharge from
        starting_slots() for a full long rest.
        """
        if level < 1 or level > 9:
            raise ValueError(f"Slot level must be 1–9, got {level}")
        self.slots[level] = self.slots.get(level, 0) + count

    def snapshot(self) -> Dict[int, int]:
        """Return a copy of the current slots dict."""
        return dict(self.slots)


# ---------------------------------------------------------------------------
# Concentration tracking
# ---------------------------------------------------------------------------


@dataclass
class ConcentrationState:
    """Tracks the active concentration spell for one caster."""

    active: bool = False
    spell_name: str = ""
    slot_level: int = 0

    def start(self, spell_name: str, slot_level: int) -> None:
        """Begin concentrating on a new spell (ends any previous concentration)."""
        self.active = True
        self.spell_name = spell_name
        self.slot_level = slot_level

    def end(self) -> None:
        """Stop concentrating (spell ends)."""
        self.active = False
        self.spell_name = ""
        self.slot_level = 0


# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class SpellCastResult:
    """Result of attempting to cast a spell."""

    spell_name: str
    spell_level: int           # minimum level of the spell
    slot_level: int            # actual slot used (≥ spell_level when upcasting)
    upcasted: bool             # True when slot_level > spell_level
    concentration: bool        # True if this spell requires concentration
    previous_concentration: str  # Name of the concentration spell that was ended ("" if none)
    slots_remaining: Dict[int, int]  # Slot snapshot after casting


@dataclass
class ConcentrationCheckResult:
    """Result of a concentration check triggered by taking damage."""

    damage_taken: int
    dc: int                    # max(10, damage_taken // 2)
    d20_roll: int
    modifier: int
    total: int
    success: bool
    breakdown: str


# ---------------------------------------------------------------------------
# Core functions
# ---------------------------------------------------------------------------


def spell_save_dc(caster_ability_score: int, prof_bonus: int) -> int:
    """Calculate the spell save DC for a caster.

    SRD 5.2: Spell Save DC = 8 + proficiency bonus + spellcasting ability modifier.

    Args:
        caster_ability_score: The relevant spellcasting ability score (INT/WIS/CHA).
        prof_bonus: The caster's proficiency bonus.
    """
    return 8 + prof_bonus + ability_modifier(caster_ability_score)


def spell_attack_bonus(caster_ability_score: int, prof_bonus: int) -> int:
    """Calculate the spell attack bonus for a caster.

    SRD 5.2: Spell Attack Bonus = proficiency bonus + spellcasting ability modifier.
    """
    return prof_bonus + ability_modifier(caster_ability_score)


def roll_spell_attack(
    caster_ability_score: int,
    prof_bonus: int,
    target_ac: int,
    advantage: Optional[bool] = None,
    rng: Optional[random.Random] = None,
) -> AttackResult:
    """Roll a spell attack (ranged or melee spell attack).

    Uses the same attack mechanic as weapon attacks (natural 20 = crit, natural 1 = miss).

    Args:
        caster_ability_score: The relevant spellcasting ability score.
        prof_bonus: The caster's proficiency bonus.
        target_ac: Target's Armor Class.
        advantage: True/False/None.
        rng: Seeded Random for tests.
    """
    bonus = spell_attack_bonus(caster_ability_score, prof_bonus)
    return roll_attack(bonus, target_ac, advantage=advantage, rng=rng)


def cast_spell(
    slots: SpellSlots,
    spell_name: str,
    spell_level: int,
    slot_level: int,
    is_concentration: bool,
    concentration: ConcentrationState,
) -> SpellCastResult:
    """Attempt to cast a spell, consuming a spell slot.

    Args:
        slots: The caster's current spell slots (mutated in place).
        spell_name: Name of the spell being cast.
        spell_level: The minimum level of the spell (e.g. 1 for Magic Missile).
        slot_level: The actual slot level to use (≥ spell_level).
        is_concentration: Whether the spell requires concentration.
        concentration: The caster's current concentration state (mutated in place).

    Returns:
        SpellCastResult with the updated state.

    Raises:
        ValueError: If slot_level < spell_level, or no slot of that level is available.
    """
    if slot_level < spell_level:
        raise ValueError(
            f"Cannot cast a level-{spell_level} spell in a level-{slot_level} slot."
        )
    if spell_level > 0 and not slots.has_slot(slot_level):
        raise ValueError(
            f"No spell slots of level {slot_level} remaining."
        )

    # End previous concentration if needed
    prev_concentration = ""
    if is_concentration and concentration.active:
        prev_concentration = concentration.spell_name
        concentration.end()

    # Consume slot (cantrips have spell_level == 0 and use no slot)
    if spell_level > 0:
        slots.use_slot(slot_level)

    # Start new concentration
    if is_concentration:
        concentration.start(spell_name, slot_level)

    return SpellCastResult(
        spell_name=spell_name,
        spell_level=spell_level,
        slot_level=slot_level,
        upcasted=slot_level > spell_level,
        concentration=is_concentration,
        previous_concentration=prev_concentration,
        slots_remaining=slots.snapshot(),
    )


def concentration_check(
    con_score: int,
    damage_taken: int,
    level: int,
    proficient: bool = False,
    advantage: Optional[bool] = None,
    rng: Optional[random.Random] = None,
) -> ConcentrationCheckResult:
    """Roll a concentration check after taking damage.

    SRD 5.2 §Concentration: CON save, DC = max(10, damage_taken // 2).

    Args:
        con_score: The caster's CON ability score.
        damage_taken: Amount of damage taken from the triggering hit.
        level: Character level (for proficiency bonus if proficient in CON saves).
        proficient: Whether the caster is proficient in CON saving throws.
        advantage: True/False/None.
        rng: Seeded Random for tests.

    Returns:
        ConcentrationCheckResult (caller must call concentration.end() if failed).
    """
    dc = max(10, damage_taken // 2)
    result = saving_throw(
        score=con_score,
        ability=Ability.CON,
        level=level,
        proficient=proficient,
        dc=dc,
        advantage=advantage,
        rng=rng,
    )
    return ConcentrationCheckResult(
        damage_taken=damage_taken,
        dc=dc,
        d20_roll=result.d20_roll,
        modifier=result.modifier,
        total=result.total,
        success=result.success or False,
        breakdown=result.breakdown,
    )


def upcast_damage(
    base_notation: str,
    extra_dice_per_level: str,
    spell_level: int,
    slot_level: int,
    critical: bool = False,
    rng: Optional[random.Random] = None,
) -> DamageResult:
    """Roll damage for an upcasted spell with additional dice per slot level.

    Many spells add extra dice when cast at a higher level (e.g. Magic Missile
    adds 1d4+1 per level above 1st; Cure Wounds heals +1d8 per level above 1st).
    This function rolls the combined damage.

    Args:
        base_notation: Base damage expression (e.g. "2d6+3").
        extra_dice_per_level: Extra dice per slot level above the spell's level
                              (e.g. "1d6"). Pass "" if the spell has no upcast scaling.
        spell_level: The spell's minimum level.
        slot_level: The actual slot level used.
        critical: Whether this is a critical hit (doubles ALL dice, including extras).
        rng: Seeded Random for tests.

    Returns:
        DamageResult representing the total damage rolled.

    Raises:
        ValueError: If slot_level < spell_level.
    """
    if slot_level < spell_level:
        raise ValueError(
            f"slot_level ({slot_level}) must be ≥ spell_level ({spell_level})."
        )

    levels_above = slot_level - spell_level

    if levels_above == 0 or not extra_dice_per_level:
        return roll_damage(base_notation, critical=critical, rng=rng)

    # Parse the extra dice notation (no modifier allowed on extra dice)
    import re
    _EXTRA = re.compile(r"^(?P<count>\d+)?d(?P<sides>\d+)$", re.IGNORECASE)
    cleaned = extra_dice_per_level.strip().lower()
    m = _EXTRA.match(cleaned)
    if not m:
        raise ValueError(
            f"Invalid extra_dice_per_level: '{extra_dice_per_level}'. "
            "Expected format: [N]dS (e.g. '1d6')."
        )
    extra_count = int(m.group("count") or 1) * levels_above
    extra_sides = int(m.group("sides"))

    # Roll base
    base = roll_damage(base_notation, critical=critical, rng=rng)

    # Roll extra dice (also doubled on crit)
    from app.engine.dice import roll_dice as _roll_dice
    actual_extra = extra_count * 2 if critical else extra_count
    extra_rolls = _roll_dice(extra_sides, actual_extra, rng)

    combined_rolls = base.rolls + extra_rolls
    combined_total = max(0, base.total + sum(extra_rolls))

    return DamageResult(
        notation=f"{base_notation}+{extra_count}d{extra_sides} (upcast)",
        rolls=combined_rolls,
        modifier=base.modifier,
        total=combined_total,
        critical=critical,
    )
