"""Dice rolling engine — pure logic, no I/O.

Supported notations:
  "d20"          → 1d20
  "2d6"          → 2d6
  "2d6+3"        → 2d6 + 3
  "4d6kh3"       → 4d6 keep highest 3
  "4d6kl1"       → 4d6 keep lowest 1
  "2d8-1"        → 2d8 - 1
  advantage      → roll 2d20, keep highest
  disadvantage   → roll 2d20, keep lowest
"""
from __future__ import annotations

import random
import re
from dataclasses import dataclass, field
from typing import List, Optional

# Regex: XdY[kh|kl]Z[+/-N]
_NOTATION = re.compile(
    r"^(?P<count>\d+)?d(?P<sides>\d+)"
    r"(?:k(?P<keep_dir>[hl])(?P<keep_n>\d+))?"
    r"(?P<mod>[+-]\d+)?$",
    re.IGNORECASE,
)


@dataclass
class RollResult:
    """Result of a dice roll."""

    notation: str
    rolls: List[int]          # all individual dice results
    kept: List[int]           # dice that count toward the total
    modifier: int
    total: int
    advantage: Optional[bool] = None  # True=adv, False=disadv, None=normal


def roll_dice(sides: int, count: int = 1, rng: random.Random | None = None) -> List[int]:
    """Roll `count` dice with `sides` faces."""
    r = rng or random
    return [r.randint(1, sides) for _ in range(count)]


def roll(notation: str, rng: random.Random | None = None) -> RollResult:
    """Parse and evaluate a dice notation string.

    Args:
        notation: Dice expression, e.g. "2d6+3", "4d6kh3", "d20".
        rng: Optional seeded Random instance for deterministic tests.

    Returns:
        RollResult with full breakdown.

    Raises:
        ValueError: If the notation is invalid.
    """
    cleaned = notation.strip().lower().replace(" ", "")
    m = _NOTATION.match(cleaned)
    if not m:
        raise ValueError(f"Invalid dice notation: '{notation}'")

    count = int(m.group("count") or 1)
    sides = int(m.group("sides"))
    keep_dir = m.group("keep_dir")   # 'h' or 'l'
    keep_n = int(m.group("keep_n")) if m.group("keep_n") else None
    modifier = int(m.group("mod") or 0)

    if sides < 2:
        raise ValueError(f"Dice must have at least 2 sides, got {sides}")
    if count < 1:
        raise ValueError(f"Must roll at least 1 die, got {count}")
    if keep_n is not None and (keep_n < 1 or keep_n > count):
        raise ValueError(f"keep_n={keep_n} out of range for {count} dice")

    rolls = roll_dice(sides, count, rng)

    if keep_n is not None:
        sorted_rolls = sorted(rolls, reverse=(keep_dir == "h"))
        kept = sorted_rolls[:keep_n]
    else:
        kept = rolls[:]

    total = sum(kept) + modifier
    return RollResult(
        notation=notation,
        rolls=rolls,
        kept=kept,
        modifier=modifier,
        total=total,
    )


def roll_with_advantage(
    sides: int = 20,
    advantage: bool = True,
    modifier: int = 0,
    rng: random.Random | None = None,
) -> RollResult:
    """Roll 2dX and keep highest (advantage) or lowest (disadvantage).

    Args:
        sides: Number of faces (default 20).
        advantage: True = keep highest, False = keep lowest.
        modifier: Flat modifier added to the kept die.
        rng: Optional seeded Random for tests.
    """
    rolls = roll_dice(sides, 2, rng)
    kept_value = max(rolls) if advantage else min(rolls)
    total = kept_value + modifier
    notation = f"2d{sides} ({'advantage' if advantage else 'disadvantage'}){modifier:+d}" if modifier else f"2d{sides} ({'advantage' if advantage else 'disadvantage'})"
    return RollResult(
        notation=notation,
        rolls=rolls,
        kept=[kept_value],
        modifier=modifier,
        total=total,
        advantage=advantage,
    )


def roll_ability_scores() -> List[RollResult]:
    """Roll six ability scores using the standard 4d6kh3 method."""
    return [roll("4d6kh3") for _ in range(6)]
