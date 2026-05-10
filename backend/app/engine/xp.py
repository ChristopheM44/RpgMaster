"""XP thresholds and level lookup helpers for SRD-style progression."""
from __future__ import annotations

XP_THRESHOLDS: dict[int, int] = {
    1: 0,
    2: 300,
    3: 900,
    4: 2700,
    5: 6500,
    6: 14000,
    7: 23000,
    8: 34000,
    9: 48000,
    10: 64000,
    11: 85000,
    12: 100000,
    13: 120000,
    14: 140000,
    15: 165000,
    16: 195000,
    17: 225000,
    18: 265000,
    19: 305000,
    20: 355000,
}


def xp_for_level(level: int) -> int:
    """Return the cumulative XP required for a character level."""
    if level not in XP_THRESHOLDS:
        raise ValueError(f"Level must be between 1 and 20, got {level}")
    return XP_THRESHOLDS[level]


def level_from_xp(xp: int) -> int:
    """Return the highest reachable level for a cumulative XP value."""
    value = max(0, int(xp))
    level = 1
    for candidate, threshold in XP_THRESHOLDS.items():
        if value >= threshold:
            level = candidate
    return level


def xp_to_next_level(xp: int, current_level: int) -> int:
    """Return XP still needed for ``current_level + 1``.

    If the character already has enough XP for the next level, this returns 0.
    Level 20 characters have no next threshold.
    """
    level = max(1, min(20, int(current_level)))
    if level >= 20:
        return 0
    return max(0, XP_THRESHOLDS[level + 1] - max(0, int(xp)))
