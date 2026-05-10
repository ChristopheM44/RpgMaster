"""SRD data loader — lazy JSON loading for D&D SRD 5.2 reference data.

All data files are loaded once on first access and cached in-process.
No I/O after the first call; safe to call from async contexts.

Spell and monster entries are validated at load-time against the Pydantic
schemas defined in ``schemas.py``. The cached return value is kept as a
``list[dict]`` for backwards compatibility with existing consumers, but a
``ValueError`` is raised on the first call if any entry is malformed.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List

from pydantic import ValidationError

from .schemas import MonsterSchema, SpellSchema

_DATA_DIR = Path(__file__).parent


def _load(filename: str) -> Dict[str, Any]:
    with (_DATA_DIR / filename).open(encoding="utf-8") as f:
        return json.load(f)


def _validate_all(items: List[Dict[str, Any]], model, kind: str) -> List[Dict[str, Any]]:
    errors: List[str] = []
    for item in items:
        try:
            model.model_validate(item)
        except ValidationError as e:
            errors.append(f"{kind} '{item.get('id', '?')}': {e.errors()[0]['msg']} "
                          f"at {'.'.join(str(p) for p in e.errors()[0]['loc'])}")
    if errors:
        head = "\n  - ".join(errors[:10])
        more = f"\n  ... and {len(errors) - 10} more" if len(errors) > 10 else ""
        raise ValueError(f"Invalid SRD {kind} data ({len(errors)} errors):\n  - {head}{more}")
    return items


@lru_cache(maxsize=None)
def get_classes() -> List[Dict[str, Any]]:
    return _load("classes.json")["classes"]


@lru_cache(maxsize=None)
def get_species() -> List[Dict[str, Any]]:
    return _load("species.json")["species"]


@lru_cache(maxsize=None)
def get_spells() -> List[Dict[str, Any]]:
    return _validate_all(_load("spells.json")["spells"], SpellSchema, "spell")


@lru_cache(maxsize=None)
def get_monsters() -> List[Dict[str, Any]]:
    return _validate_all(_load("monsters.json")["monsters"], MonsterSchema, "monster")


@lru_cache(maxsize=None)
def get_equipment() -> Dict[str, Any]:
    return _load("equipment.json")


@lru_cache(maxsize=None)
def get_equipment_flat() -> List[Dict[str, Any]]:
    """Return all equipment entries across weapons, armor, gear, consumables, and kits."""
    data = get_equipment()
    items: list[dict[str, Any]] = []
    for section in ("weapons", "armor"):
        grouped = data.get(section, {})
        if isinstance(grouped, dict):
            for group in grouped.values():
                items.extend(group)
        elif isinstance(grouped, list):
            items.extend(grouped)
    for section in ("adventuring_gear", "consumables", "adventurer_kits"):
        section_items = data.get(section, [])
        if isinstance(section_items, list):
            items.extend(section_items)
    return items


def find_class(class_id: str) -> Dict[str, Any]:
    """Return a class by id (case-insensitive). Raises KeyError if not found."""
    key = class_id.lower()
    for c in get_classes():
        if c["id"] == key:
            return c
    raise KeyError(f"Class '{class_id}' not found in SRD data")


def find_species(species_id: str) -> Dict[str, Any]:
    """Return a species by id (case-insensitive). Raises KeyError if not found."""
    key = species_id.lower()
    for s in get_species():
        if s["id"] == key:
            return s
    raise KeyError(f"Species '{species_id}' not found in SRD data")


def find_spell(spell_id: str) -> Dict[str, Any]:
    """Return a spell by id (case-insensitive). Raises KeyError if not found."""
    key = spell_id.lower()
    for sp in get_spells():
        if sp["id"] == key:
            return sp
    raise KeyError(f"Spell '{spell_id}' not found in SRD data")


def find_monster(monster_id: str) -> Dict[str, Any]:
    """Return a monster by id (case-insensitive). Raises KeyError if not found."""
    key = monster_id.lower()
    for m in get_monsters():
        if m["id"] == key:
            return m
    raise KeyError(f"Monster '{monster_id}' not found in SRD data")


def find_weapon(weapon_id: str) -> Dict[str, Any]:
    """Return a weapon by id across all weapon categories. Raises KeyError if not found."""
    key = weapon_id.lower()
    weapons = get_equipment()["weapons"]
    for category_weapons in weapons.values():
        for w in category_weapons:
            if w["id"] == key:
                return w
    raise KeyError(f"Weapon '{weapon_id}' not found in SRD data")


def find_armor(armor_id: str) -> Dict[str, Any]:
    """Return an armor piece by id across all armor categories. Raises KeyError if not found."""
    key = armor_id.lower()
    armors = get_equipment()["armor"]
    for category_armors in armors.values():
        for a in category_armors:
            if a["id"] == key:
                return a
    raise KeyError(f"Armor '{armor_id}' not found in SRD data")


def find_equipment(item_id: str) -> Dict[str, Any]:
    """Return any equipment entry by id. Raises KeyError if not found."""
    key = item_id.lower()
    for item in get_equipment_flat():
        if str(item.get("id", "")).lower() == key:
            return item
    raise KeyError(f"Equipment '{item_id}' not found in SRD data")


def spells_by_level(level: int) -> List[Dict[str, Any]]:
    """Return all spells of the given level (0 = cantrips)."""
    return [sp for sp in get_spells() if sp["level"] == level]


def spells_for_class(class_id: str) -> List[Dict[str, Any]]:
    """Return all spells available to the given class."""
    key = class_id.lower()
    return [sp for sp in get_spells() if key in sp.get("classes", [])]


def monsters_by_cr(cr: float) -> List[Dict[str, Any]]:
    """Return all monsters of the given CR."""
    return [m for m in get_monsters() if m["cr"] == cr]
