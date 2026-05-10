"""Inventory helpers for typed equipment, slots, weight, and attunement."""
from __future__ import annotations

from typing import Any

ARMOR_CATEGORIES = {"light", "medium", "heavy"}
HAND_SLOTS = {"main_hand", "off_hand"}
ATTUNEMENT_LIMIT = 3


def total_weight(equipment: list[dict[str, Any]]) -> float:
    """Return carried weight in pounds."""
    total = 0.0
    for item in equipment or []:
        qty = max(1, int(item.get("quantity", 1) or 1))
        weight = item.get("weight_lb", item.get("weight", 0.0))
        try:
            total += float(weight or 0.0) * qty
        except (TypeError, ValueError):
            continue
    return round(total, 2)


def carrying_capacity(str_score: int) -> float:
    """Return D&D carrying capacity in pounds."""
    return max(0, int(str_score)) * 15.0


def encumbrance_level(weight: float, capacity: float) -> str:
    if capacity <= 0:
        return "heavily"
    ratio = float(weight) / float(capacity)
    if ratio >= 1:
        return "heavily"
    if ratio >= 2 / 3:
        return "encumbered"
    return "normal"


def resolve_default_slot(
    category: str | None,
    properties: list[str] | None = None,
    item_type: str | None = None,
) -> str | None:
    item_type = (item_type or "").lower()
    category = (category or "").lower()
    properties = [str(prop).lower() for prop in (properties or [])]
    if category in ARMOR_CATEGORIES or item_type == "armor":
        return "body"
    if category == "shield" or item_type == "shield":
        return "off_hand"
    if item_type == "weapon" or "damage_dice" in properties or category in {"simple", "martial"}:
        return "main_hand"
    return None


def slots_for_item(item: dict[str, Any], requested_slot: str | None = None) -> set[str]:
    properties = [str(prop).lower() for prop in item.get("properties", []) or []]
    default_slot = requested_slot or item.get("slot") or resolve_default_slot(
        item.get("category"),
        properties,
        item.get("item_type"),
    )
    if default_slot is None:
        return set()
    if "two-handed" in properties and default_slot in HAND_SLOTS:
        return {"main_hand", "off_hand"}
    return {str(default_slot)}


def equipped_slots_for_item(item: dict[str, Any]) -> set[str]:
    slots = item.get("occupied_slots")
    if isinstance(slots, list):
        return {str(slot) for slot in slots}
    return slots_for_item(item)


def can_equip_in_slot(
    item: dict[str, Any],
    slot: str | None,
    current_equipment: list[dict[str, Any]],
) -> tuple[bool, str | None]:
    wanted = slots_for_item(item, slot)
    if not wanted:
        return True, None
    item_id = item.get("id")
    for equipped in current_equipment:
        if not equipped.get("equipped") or equipped.get("id") == item_id:
            continue
        occupied = equipped_slots_for_item(equipped)
        if wanted & occupied:
            return False, f"Slot occupé : {', '.join(sorted(wanted & occupied))}"
    return True, None


def count_attuned(equipment: list[dict[str, Any]]) -> int:
    return sum(1 for item in equipment or [] if item.get("attuned"))
