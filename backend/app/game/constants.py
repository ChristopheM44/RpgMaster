from __future__ import annotations

from enum import Enum


class CombatantStatus(str, Enum):
    """Statuts possibles d'un combattant dans le game state."""

    ACTIVE = "active"
    DEFEATED = "defeated"
    SURRENDERED = "surrendered"
    FLED = "fled"
    STABLE = "stable"


# Statuts qui excluent un combattant des tours actifs
INACTIVE_STATUSES: frozenset[str] = frozenset(
    {CombatantStatus.DEFEATED, CombatantStatus.SURRENDERED, CombatantStatus.FLED}
)

# Catégories d'armure SRD (hors bouclier)
ARMOR_CATEGORIES: frozenset[str] = frozenset({"light", "medium", "heavy"})

# Couleurs par type de monstre (utilisées dans les tokens frontend)
MONSTER_TYPE_COLORS: dict[str, str] = {
    "aberration": "#8f5cf7",
    "beast": "#7f8a78",
    "celestial": "#f4c95d",
    "construct": "#9aa4b2",
    "dragon": "#d94841",
    "elemental": "#3aa6b9",
    "fey": "#d16ba5",
    "fiend": "#b42318",
    "giant": "#b7791f",
    "humanoid": "#4d9f64",
    "monstrosity": "#8b5e3c",
    "ooze": "#6b7280",
    "plant": "#2f855a",
    "undead": "#6d597a",
}
