"""Services d'inventaire utilisables par REST et WebSocket."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.dice import RollResult, roll
from app.engine.inventory import (
    ATTUNEMENT_LIMIT,
    count_attuned,
    encumbrance_level,
    equipped_slots_for_item,
    slots_for_item,
    total_weight,
)
from app.game.constants import ARMOR_CATEGORIES
from app.game.session_manager import ActiveSession
from app.game.state_sync import sync_character_state
from app.models.character import Character


class EquipmentServiceError(Exception):
    """Erreur métier lors d'une action d'inventaire."""


class CharacterNotFoundError(EquipmentServiceError):
    """Le personnage demandé n'existe pas."""


class ItemNotFoundError(EquipmentServiceError):
    """L'objet demandé n'est pas dans l'inventaire."""


@dataclass
class EquipmentActionResult:
    character: Character
    character_id: str
    item_id: str
    item_name: str
    equipment: list[dict[str, Any]]
    narration: str
    equipped: Optional[bool] = None
    hp_delta: int = 0
    hp: Optional[int] = None
    heal_roll: Optional[RollResult] = None
    slot: Optional[str] = None


class EquipmentService:
    """Mutations d'équipement avec synchronisation optionnelle du game state."""

    async def equip_item(
        self,
        *,
        character_id: str,
        item_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> EquipmentActionResult:
        """Backward-compatible toggle used by existing clients."""
        char = await self._load_character(character_id, db)
        equipment = list(char.equipment or [])
        idx, item = self._find_item(equipment, item_id)
        if item.get("equipped"):
            return await self.unequip_item(
                character_id=character_id,
                item_id=item_id,
                db=db,
                active=active,
            )
        return await self._equip_loaded_item(char, equipment, idx, item, db, active)

    async def unequip_item(
        self,
        *,
        character_id: str,
        item_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> EquipmentActionResult:
        char = await self._load_character(character_id, db)
        equipment = list(char.equipment or [])
        idx, item = self._find_item(equipment, item_id)
        item_name = self._item_name(item, item_id)
        equipment[idx] = {
            **item,
            "equipped": False,
            "occupied_slots": [],
        }
        char.equipment = equipment
        await db.commit()
        await db.refresh(char)
        self._sync_equipment(active, char.id, equipment)
        return EquipmentActionResult(
            character=char,
            character_id=character_id,
            item_id=item_id,
            item_name=item_name,
            equipment=equipment,
            equipped=False,
            narration=f"{char.name} retire : {item_name}.",
        )

    async def _equip_loaded_item(
        self,
        char: Character,
        equipment: list[dict[str, Any]],
        idx: int,
        item: dict[str, Any],
        db: AsyncSession,
        active: Optional[ActiveSession],
    ) -> EquipmentActionResult:
        item_id = str(item.get("id") or "")
        item_name = self._item_name(item, item_id)
        wanted_slots = slots_for_item(item)

        for i, eq in enumerate(equipment):
            if i == idx or not eq.get("equipped"):
                continue
            conflicts = wanted_slots & equipped_slots_for_item(eq)
            armor_conflict = (
                item.get("category", "") in ARMOR_CATEGORIES
                and eq.get("category", "") in ARMOR_CATEGORIES
            )
            if conflicts or armor_conflict:
                equipment[i] = {**eq, "equipped": False, "occupied_slots": []}

        equipment[idx] = {
            **item,
            "equipped": True,
            "slot": str(next(iter(wanted_slots))) if wanted_slots else item.get("slot"),
            "occupied_slots": sorted(wanted_slots),
        }
        char.equipment = equipment
        await db.commit()
        await db.refresh(char)

        self._sync_equipment(active, char.id, equipment)
        return EquipmentActionResult(
            character=char,
            character_id=char.id,
            item_id=item_id,
            item_name=item_name,
            equipment=equipment,
            equipped=True,
            slot=str(next(iter(wanted_slots))) if wanted_slots else None,
            narration=f"{char.name} équipe : {item_name}.",
        )

    async def use_item(
        self,
        *,
        character_id: str,
        item_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> EquipmentActionResult:
        char = await self._load_character(character_id, db)
        equipment = list(char.equipment or [])
        idx, item = self._find_item(equipment, item_id)
        item_name = self._item_name(item, item_id)
        heal_roll: Optional[RollResult] = None
        hp_delta = 0
        hp: Optional[int] = None

        if self._is_healing_potion(item, item_id):
            heal_roll = roll("2d4+2")
            old_hp = int(char.hp_current)
            new_hp = min(int(char.hp_max), old_hp + int(heal_roll.total))
            hp_delta = max(0, new_hp - old_hp)
            hp = new_hp
            char.hp_current = new_hp

        qty = int(item.get("quantity", 1))
        if qty > 1:
            equipment[idx] = {**item, "quantity": qty - 1}
        else:
            equipment.pop(idx)

        char.equipment = equipment
        await db.commit()
        await db.refresh(char)

        self._sync_equipment(active, character_id, equipment)
        if hp is not None:
            self._sync_hp(active, character_id, hp)

        if heal_roll is not None:
            narration = f"{char.name} boit {item_name} et récupère {hp_delta} point(s) de vie."
        else:
            narration = f"{char.name} utilise {item_name}."
        return EquipmentActionResult(
            character=char,
            character_id=character_id,
            item_id=item_id,
            item_name=item_name,
            equipment=equipment,
            narration=narration,
            hp_delta=hp_delta,
            hp=hp,
            heal_roll=heal_roll,
        )

    async def drop_item(
        self,
        *,
        character_id: str,
        item_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> EquipmentActionResult:
        char = await self._load_character(character_id, db)
        equipment = list(char.equipment or [])
        idx, item = self._find_item(equipment, item_id)
        item_name = self._item_name(item, item_id)
        equipment.pop(idx)

        char.equipment = equipment
        await db.commit()
        await db.refresh(char)

        self._sync_equipment(active, character_id, equipment)
        return EquipmentActionResult(
            character=char,
            character_id=character_id,
            item_id=item_id,
            item_name=item_name,
            equipment=equipment,
            narration=f"{char.name} lâche {item_name}.",
        )

    async def remove_item(
        self,
        *,
        character_id: str,
        item_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> EquipmentActionResult:
        return await self.drop_item(
            character_id=character_id,
            item_id=item_id,
            db=db,
            active=active,
        )

    async def attune_item(
        self,
        *,
        character_id: str,
        item_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> EquipmentActionResult:
        char = await self._load_character(character_id, db)
        equipment = list(char.equipment or [])
        idx, item = self._find_item(equipment, item_id)
        if count_attuned(equipment) >= ATTUNEMENT_LIMIT and not item.get("attuned"):
            raise EquipmentServiceError("Limite d'harmonisation atteinte")
        equipment[idx] = {**item, "attuned": True}
        char.equipment = equipment
        await db.commit()
        await db.refresh(char)
        self._sync_equipment(active, character_id, equipment)
        name = self._item_name(item, item_id)
        return EquipmentActionResult(
            character=char,
            character_id=character_id,
            item_id=item_id,
            item_name=name,
            equipment=equipment,
            narration=f"{char.name} s'harmonise avec {name}.",
        )

    async def unattune_item(
        self,
        *,
        character_id: str,
        item_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> EquipmentActionResult:
        char = await self._load_character(character_id, db)
        equipment = list(char.equipment or [])
        idx, item = self._find_item(equipment, item_id)
        equipment[idx] = {**item, "attuned": False}
        char.equipment = equipment
        await db.commit()
        await db.refresh(char)
        self._sync_equipment(active, character_id, equipment)
        name = self._item_name(item, item_id)
        return EquipmentActionResult(
            character=char,
            character_id=character_id,
            item_id=item_id,
            item_name=name,
            equipment=equipment,
            narration=f"{char.name} rompt l'harmonisation avec {name}.",
        )

    async def identify_item(
        self,
        *,
        character_id: str,
        item_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> EquipmentActionResult:
        char = await self._load_character(character_id, db)
        equipment = list(char.equipment or [])
        idx, item = self._find_item(equipment, item_id)
        hidden = dict(item.get("hidden_properties") or {})
        identified = {**item, **{k: v for k, v in hidden.items() if k != "true_name"}}
        if hidden.get("true_name"):
            identified["name_fr"] = hidden["true_name"]
        identified["identified"] = True
        identified["hidden_properties"] = {}
        equipment[idx] = identified
        char.equipment = equipment
        await db.commit()
        await db.refresh(char)
        self._sync_equipment(active, character_id, equipment)
        name = self._item_name(identified, item_id)
        return EquipmentActionResult(
            character=char,
            character_id=character_id,
            item_id=item_id,
            item_name=name,
            equipment=equipment,
            narration=f"{char.name} identifie {name}.",
        )

    def get_encumbrance_info(self, *, strength_score: int, equipment: list[dict[str, Any]]) -> dict[str, Any]:
        from app.engine.inventory import carrying_capacity

        weight = total_weight(equipment)
        capacity = carrying_capacity(strength_score)
        return {
            "weight_lb": weight,
            "capacity_lb": capacity,
            "level": encumbrance_level(weight, capacity),
        }

    async def _load_character(self, character_id: str, db: AsyncSession) -> Character:
        result = await db.execute(select(Character).where(Character.id == character_id))
        char = result.scalar_one_or_none()
        if char is None:
            raise CharacterNotFoundError("Personnage introuvable")
        return char

    @staticmethod
    def _find_item(
        equipment: list[dict[str, Any]],
        item_id: str,
    ) -> tuple[int, dict[str, Any]]:
        for i, item in enumerate(equipment):
            if item.get("id") == item_id:
                return i, item
        raise ItemNotFoundError("Objet introuvable dans l'inventaire")

    @staticmethod
    def _item_name(item: dict[str, Any], fallback: str) -> str:
        return str(item.get("name_fr") or item.get("name") or fallback)

    @staticmethod
    def _is_healing_potion(item: dict[str, Any], item_id: str) -> bool:
        item_id_lower = item_id.lower()
        item_name_lower = str(item.get("name_fr") or item.get("name") or "").lower()
        return "potion" in item_id_lower or "potion" in item_name_lower

    @staticmethod
    def _sync_equipment(
        active: Optional[ActiveSession],
        character_id: str,
        equipment: list[dict[str, Any]],
    ) -> None:
        sync_character_state(active, character_id, equipment=equipment)

    @staticmethod
    def _sync_hp(active: Optional[ActiveSession], character_id: str, hp: int) -> None:
        sync_character_state(active, character_id, hp=hp)
