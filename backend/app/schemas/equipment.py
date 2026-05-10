from __future__ import annotations

from enum import Enum
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class EquipmentSlot(str, Enum):
    MAIN_HAND = "main_hand"
    OFF_HAND = "off_hand"
    BODY = "body"
    HEAD = "head"
    HANDS = "hands"
    FEET = "feet"
    NECK = "neck"
    RING_1 = "ring_1"
    RING_2 = "ring_2"
    BACK = "back"
    WAIST = "waist"


class ItemRarity(str, Enum):
    COMMON = "common"
    UNCOMMON = "uncommon"
    RARE = "rare"
    VERY_RARE = "very_rare"
    LEGENDARY = "legendary"
    ARTIFACT = "artifact"


ItemType = Literal["weapon", "armor", "shield", "gear", "consumable", "magic"]


class EquipmentItem(BaseModel):
    id: str
    template_id: str
    name: str = ""
    name_fr: Optional[str] = None
    category: str = ""
    item_type: ItemType = "gear"
    quantity: int = Field(1, ge=1)
    equipped: bool = False
    slot: Optional[EquipmentSlot] = None
    occupied_slots: list[str] = Field(default_factory=list)
    weight_lb: float = Field(0.0, ge=0)
    cost_gp: float = Field(0.0, ge=0)
    rarity: ItemRarity = ItemRarity.COMMON
    attunement_required: bool = False
    attuned: bool = False
    identified: bool = True
    hidden_properties: dict[str, Any] = Field(default_factory=dict)
    properties: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def backfill_legacy_item(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        item_id = str(data.get("id") or data.get("template_id") or "")
        data.setdefault("id", item_id)
        data.setdefault("template_id", item_id)
        if "weight_lb" not in data and "weight" in data:
            data["weight_lb"] = data.get("weight") or 0.0
        data.setdefault("item_type", _infer_item_type(data))
        return data


class WeaponItem(EquipmentItem):
    item_type: Literal["weapon"] = "weapon"
    damage_dice: str
    damage_type: str
    versatile_dice: Optional[str] = None
    range_normal: Optional[float] = None
    range_long: Optional[float] = None


class ArmorItem(EquipmentItem):
    item_type: Literal["armor"] = "armor"
    base_ac: int
    dex_cap: Optional[int] = None
    stealth_disadvantage: bool = False


class ShieldItem(EquipmentItem):
    item_type: Literal["shield"] = "shield"
    base_ac_bonus: int = 2


class GearItem(EquipmentItem):
    item_type: Literal["gear"] = "gear"


class ConsumableItem(EquipmentItem):
    item_type: Literal["consumable"] = "consumable"
    effect: dict[str, Any] = Field(default_factory=dict)


class MagicItem(EquipmentItem):
    item_type: Literal["magic"] = "magic"
    charges: Optional[int] = None


def _infer_item_type(data: dict[str, Any]) -> str:
    category = str(data.get("category") or "").lower()
    if category == "shield":
        return "shield"
    if category in {"light", "medium", "heavy"} or "base_ac" in data:
        return "armor"
    if "damage_dice" in data:
        return "weapon"
    if data.get("effect") or "potion" in str(data.get("id") or "").lower():
        return "consumable"
    if data.get("rarity") and data.get("rarity") != "common":
        return "magic"
    return "gear"
