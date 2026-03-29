"""Ability checks, skill checks, saving throws — pure D&D SRD 5.2 logic.

Glossary (SRD 5.2 terms):
  ability score  : STR/DEX/CON/INT/WIS/CHA value (1–30)
  ability modifier: (score - 10) // 2
  proficiency bonus: based on character level (+2 at level 1, up to +6 at 17+)
  DC             : Difficulty Class (target number to meet or beat)
  advantage/disadvantage: roll 2d20, keep best/worst
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from app.engine.dice import RollResult, roll_dice, roll_with_advantage


class Ability(str, Enum):
    STR = "strength"
    DEX = "dexterity"
    CON = "constitution"
    INT = "intelligence"
    WIS = "wisdom"
    CHA = "charisma"


class Proficiency(str, Enum):
    NONE = "none"
    HALF = "half"          # Jack of All Trades (bard feature)
    PROFICIENT = "proficient"
    EXPERT = "expert"      # double proficiency bonus


# Canonical skill → governing ability mapping (SRD 5.2)
SKILL_ABILITY: dict[str, Ability] = {
    "acrobatics": Ability.DEX,
    "animal_handling": Ability.WIS,
    "arcana": Ability.INT,
    "athletics": Ability.STR,
    "deception": Ability.CHA,
    "history": Ability.INT,
    "insight": Ability.WIS,
    "intimidation": Ability.CHA,
    "investigation": Ability.INT,
    "medicine": Ability.WIS,
    "nature": Ability.INT,
    "perception": Ability.WIS,
    "performance": Ability.CHA,
    "persuasion": Ability.CHA,
    "religion": Ability.INT,
    "sleight_of_hand": Ability.DEX,
    "stealth": Ability.DEX,
    "survival": Ability.WIS,
}


def ability_modifier(score: int) -> int:
    """Return the ability modifier for a given ability score."""
    return (score - 10) // 2


def proficiency_bonus(level: int) -> int:
    """Return the proficiency bonus for a character of given level (SRD 5.2).

    Level  1–4  → +2
    Level  5–8  → +3
    Level  9–12 → +4
    Level 13–16 → +5
    Level 17–20 → +6
    """
    if level < 1 or level > 20:
        raise ValueError(f"Level must be 1–20, got {level}")
    return 2 + (level - 1) // 4


@dataclass
class CheckResult:
    """Full breakdown of an ability/skill/saving-throw check."""

    d20_roll: int
    all_rolls: list[int]           # both dice when advantage/disadvantage applies
    modifier: int                  # total modifier applied
    total: int                     # d20_roll + modifier
    dc: Optional[int]
    success: Optional[bool]        # None when no DC was provided
    advantage: Optional[bool]      # True/False/None
    label: str                     # human-readable label, e.g. "DEX (Stealth)"
    breakdown: str                 # e.g. "14 + 5 = 19 vs DC 15 ✓"

    @property
    def critical_hit(self) -> bool:
        return self.d20_roll == 20

    @property
    def critical_fail(self) -> bool:
        return self.d20_roll == 1


def _resolve_d20(
    advantage: Optional[bool],
    rng: random.Random | None,
) -> tuple[int, list[int]]:
    """Roll d20 respecting advantage / disadvantage.

    Returns (kept_die, all_rolls).
    """
    r = rng or random
    if advantage is None:
        result = r.randint(1, 20)
        return result, [result]

    rolls = roll_dice(20, 2, rng)
    kept = max(rolls) if advantage else min(rolls)
    return kept, rolls


def ability_check(
    score: int,
    dc: Optional[int] = None,
    advantage: Optional[bool] = None,
    ability: Optional[Ability] = None,
    rng: random.Random | None = None,
) -> CheckResult:
    """Perform a raw ability check (no proficiency).

    Args:
        score: The relevant ability score (e.g. 16 for STR 16).
        dc: Difficulty Class. Pass None to get the raw roll without success/fail.
        advantage: True=advantage, False=disadvantage, None=normal.
        ability: For labelling purposes only.
        rng: Seeded RNG for deterministic tests.
    """
    mod = ability_modifier(score)
    d20, all_rolls = _resolve_d20(advantage, rng)
    total = d20 + mod
    success = (total >= dc) if dc is not None else None
    label = ability.value.upper()[:3] if ability else "Ability"

    adv_str = " (adv)" if advantage is True else " (dis)" if advantage is False else ""
    dc_str = f" vs DC {dc} {'✓' if success else '✗'}" if dc is not None else ""
    breakdown = f"{d20}{adv_str} + {mod} = {total}{dc_str}"

    return CheckResult(
        d20_roll=d20,
        all_rolls=all_rolls,
        modifier=mod,
        total=total,
        dc=dc,
        success=success,
        advantage=advantage,
        label=label,
        breakdown=breakdown,
    )


def skill_check(
    score: int,
    skill: str,
    level: int,
    proficiency: Proficiency = Proficiency.NONE,
    dc: Optional[int] = None,
    advantage: Optional[bool] = None,
    rng: random.Random | None = None,
) -> CheckResult:
    """Perform a skill check with optional proficiency.

    Args:
        score: Governing ability score.
        skill: Skill name, e.g. "stealth". Must be in SKILL_ABILITY.
        level: Character level (used to compute proficiency bonus).
        proficiency: Proficiency tier for this skill.
        dc: Difficulty Class.
        advantage: True/False/None.
        rng: Seeded RNG.
    """
    skill_key = skill.lower().replace(" ", "_")
    if skill_key not in SKILL_ABILITY:
        raise ValueError(f"Unknown skill: '{skill}'")

    gov_ability = SKILL_ABILITY[skill_key]
    mod = ability_modifier(score)
    prof = proficiency_bonus(level)

    bonus = {
        Proficiency.NONE: 0,
        Proficiency.HALF: prof // 2,
        Proficiency.PROFICIENT: prof,
        Proficiency.EXPERT: prof * 2,
    }[proficiency]

    total_mod = mod + bonus
    d20, all_rolls = _resolve_d20(advantage, rng)
    total = d20 + total_mod
    success = (total >= dc) if dc is not None else None

    ability_label = gov_ability.value.capitalize()[:3].upper()
    label = f"{ability_label} ({skill_key.replace('_', ' ').title()})"

    adv_str = " (adv)" if advantage is True else " (dis)" if advantage is False else ""
    prof_str = f" + {bonus} prof" if bonus else ""
    dc_str = f" vs DC {dc} {'✓' if success else '✗'}" if dc is not None else ""
    breakdown = f"{d20}{adv_str} + {mod}{prof_str} = {total}{dc_str}"

    return CheckResult(
        d20_roll=d20,
        all_rolls=all_rolls,
        modifier=total_mod,
        total=total,
        dc=dc,
        success=success,
        advantage=advantage,
        label=label,
        breakdown=breakdown,
    )


def saving_throw(
    score: int,
    ability: Ability,
    level: int,
    proficient: bool = False,
    dc: Optional[int] = None,
    advantage: Optional[bool] = None,
    rng: random.Random | None = None,
) -> CheckResult:
    """Perform a saving throw.

    Args:
        score: The relevant ability score.
        ability: Which ability this save is for (for labelling).
        level: Character level (proficiency bonus computation).
        proficient: Whether the character is proficient in this save.
        dc: Difficulty Class (e.g. spell save DC of the caster).
        advantage: True/False/None.
        rng: Seeded RNG.
    """
    mod = ability_modifier(score)
    prof = proficiency_bonus(level) if proficient else 0
    total_mod = mod + prof

    d20, all_rolls = _resolve_d20(advantage, rng)
    total = d20 + total_mod
    success = (total >= dc) if dc is not None else None

    label = f"{ability.value[:3].upper()} Save"
    adv_str = " (adv)" if advantage is True else " (dis)" if advantage is False else ""
    prof_str = f" + {prof} prof" if prof else ""
    dc_str = f" vs DC {dc} {'✓' if success else '✗'}" if dc is not None else ""
    breakdown = f"{d20}{adv_str} + {mod}{prof_str} = {total}{dc_str}"

    return CheckResult(
        d20_roll=d20,
        all_rolls=all_rolls,
        modifier=total_mod,
        total=total,
        dc=dc,
        success=success,
        advantage=advantage,
        label=label,
        breakdown=breakdown,
    )
