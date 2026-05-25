from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.equipment import validate_equipment_item


def normalize_content_id(value: Any, *, max_len: int = 80) -> str:
    """Normalize Forge-authored ids without fuzzy matching."""
    text = str(value or "").strip().lower().replace("-", "_")
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^a-z0-9_]", "", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:max_len] or ""


def normalize_monster_reference(value: Any) -> str:
    raw = str(value or "").strip()
    if raw.lower().startswith("custom:"):
        custom_id = normalize_content_id(raw.split(":", 1)[1])
        return f"custom:{custom_id}" if custom_id else ""
    return normalize_content_id(raw)


class CustomItemTemplate(BaseModel):
    """Forge-authored equipment template stored in ``gm_dossier.items``."""

    model_config = ConfigDict(extra="allow")

    id: str
    template_id: str
    name: str = ""
    name_fr: Optional[str] = None
    category: str = ""
    item_type: str = "gear"
    unique: bool = False

    @model_validator(mode="before")
    @classmethod
    def normalize_ids(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        item_id = normalize_content_id(data.get("id") or data.get("template_id"))
        if not item_id:
            return data
        data["id"] = item_id
        data["template_id"] = normalize_content_id(data.get("template_id") or item_id) or item_id
        return data


class MonsterStatOverride(BaseModel):
    """Validated mechanical changes applied over a SRD monster stat block."""

    hp: Optional[int] = Field(None, ge=1)
    ac: Optional[int] = Field(None, ge=1)
    cr: Optional[float] = Field(None, ge=0)
    xp: Optional[int] = Field(None, ge=0)
    attack_bonus: Optional[int] = None
    damage_dice: Optional[str] = None
    damage_type: Optional[str] = None
    damage_resistances: list[str] = Field(default_factory=list)
    damage_immunities: list[str] = Field(default_factory=list)
    damage_vulnerabilities: list[str] = Field(default_factory=list)
    condition_immunities: list[str] = Field(default_factory=list)
    traits: list[dict[str, Any]] = Field(default_factory=list)
    actions: list[dict[str, Any]] = Field(default_factory=list)


class CustomMonsterTemplate(BaseModel):
    """Forge-authored monster template stored in ``gm_dossier.custom_monsters``."""

    id: str
    base_srd_id: str
    name: str
    name_fr: Optional[str] = None
    description: Optional[str] = None
    stat_overrides: MonsterStatOverride = Field(default_factory=MonsterStatOverride)
    persona_id: Optional[str] = None

    @model_validator(mode="before")
    @classmethod
    def normalize_ids(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        data = dict(value)
        data["id"] = normalize_content_id(data.get("id"))
        data["base_srd_id"] = normalize_content_id(
            data.get("base_srd_id") or data.get("monster_srd_id")
        )
        persona_id = normalize_content_id(data.get("persona_id"))
        data["persona_id"] = persona_id or None
        return data


def validate_custom_item_template(data: dict[str, Any]) -> dict[str, Any]:
    """Validate and dump a custom item, preserving item-specific fields."""
    payload = dict(data)
    custom = CustomItemTemplate.model_validate(payload)
    equipment_payload = dict(payload)
    equipment_payload["id"] = custom.id
    equipment_payload["template_id"] = custom.template_id
    equipment_payload["unique"] = custom.unique
    equipment = validate_equipment_item(equipment_payload).model_dump(mode="json")
    equipment["unique"] = custom.unique
    return equipment


def materialize_custom_monster(
    base_monster: dict[str, Any],
    template: dict[str, Any] | CustomMonsterTemplate,
) -> dict[str, Any]:
    """Return a SRD monster copy with a custom template's overrides applied."""
    custom = (
        template
        if isinstance(template, CustomMonsterTemplate)
        else CustomMonsterTemplate.model_validate(template)
    )
    monster = deepcopy(base_monster)
    monster["id"] = f"custom:{custom.id}"
    monster["base_srd_id"] = custom.base_srd_id
    monster["name"] = custom.name
    monster["name_fr"] = custom.name_fr or custom.name
    if custom.description:
        monster["description"] = custom.description
    if custom.persona_id:
        monster["persona_id"] = custom.persona_id

    overrides = custom.stat_overrides
    for field_name in ("hp", "ac", "cr", "xp"):
        value = getattr(overrides, field_name)
        if value is not None:
            monster[field_name] = value
    for field_name in (
        "damage_resistances",
        "damage_immunities",
        "damage_vulnerabilities",
        "condition_immunities",
    ):
        value = getattr(overrides, field_name)
        if value:
            monster[field_name] = list(value)

    if overrides.traits:
        monster["traits"] = list(monster.get("traits") or []) + list(overrides.traits)

    if overrides.actions:
        monster["actions"] = list(overrides.actions)
    else:
        actions = [dict(action) for action in monster.get("actions", []) or []]
        for action in actions:
            if "attack_bonus" not in action:
                continue
            if overrides.attack_bonus is not None:
                action["attack_bonus"] = overrides.attack_bonus
            if overrides.damage_dice:
                action["damage_dice"] = overrides.damage_dice
            if overrides.damage_type:
                action["damage_type"] = overrides.damage_type
            break
        monster["actions"] = actions

    return monster
