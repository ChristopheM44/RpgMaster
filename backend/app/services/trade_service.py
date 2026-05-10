"""Player-to-player inventory and currency transfer service."""
from __future__ import annotations

from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession
from app.game.state_sync import sync_character_state
from app.models.character import Character
from app.services.currency_service import currency_service
from app.services.equipment_service import EquipmentActionResult


class TradeServiceError(Exception):
    """Base trade service error."""


class CharacterNotFoundError(TradeServiceError):
    """The requested character does not exist."""


class ItemNotFoundError(TradeServiceError):
    """The requested item does not exist."""


class TradeService:
    async def give_item(
        self,
        *,
        session_id: str,
        from_character_id: str,
        to_character_id: str,
        item_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> tuple[EquipmentActionResult, EquipmentActionResult]:
        sender = await self._load_character(from_character_id, db)
        receiver = await self._load_character(to_character_id, db)
        sender_equipment = list(sender.equipment or [])
        receiver_equipment = list(receiver.equipment or [])
        idx, item = self._find_item(sender_equipment, item_id)
        item = {**item, "equipped": False, "attuned": False}
        sender_equipment.pop(idx)
        receiver_equipment.append(item)
        sender.equipment = sender_equipment
        receiver.equipment = receiver_equipment
        await db.commit()
        await db.refresh(sender)
        await db.refresh(receiver)

        sync_character_state(active, sender.id, equipment=sender_equipment)
        sync_character_state(active, receiver.id, equipment=receiver_equipment)
        for char_id, equipment in ((sender.id, sender_equipment), (receiver.id, receiver_equipment)):
            await event_bus.publish_to_session(
                session_id,
                EventType.EQUIPMENT_UPDATED,
                {"character_id": char_id, "equipment": equipment},
                source="trade_service",
            )

        item_name = str(item.get("name_fr") or item.get("name") or item_id)
        return (
            EquipmentActionResult(
                character=sender,
                character_id=sender.id,
                item_id=item_id,
                item_name=item_name,
                equipment=sender_equipment,
                narration=f"{sender.name} donne {item_name} à {receiver.name}.",
            ),
            EquipmentActionResult(
                character=receiver,
                character_id=receiver.id,
                item_id=item_id,
                item_name=item_name,
                equipment=receiver_equipment,
                narration=f"{receiver.name} reçoit {item_name}.",
            ),
        )

    async def give_currency(
        self,
        *,
        session_id: str,
        from_character_id: str,
        to_character_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
        gp: int = 0,
        sp: int = 0,
        cp: int = 0,
    ):
        return await currency_service.transfer_currency(
            session_id=session_id,
            from_id=from_character_id,
            to_id=to_character_id,
            gp=gp,
            sp=sp,
            cp=cp,
            db=db,
            active=active,
        )

    async def identify_item(
        self,
        *,
        session_id: str,
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
        sync_character_state(active, character_id, equipment=equipment)
        await event_bus.publish_to_session(
            session_id,
            EventType.EQUIPMENT_UPDATED,
            {"character_id": character_id, "equipment": equipment},
            source="trade_service",
        )
        name = str(identified.get("name_fr") or identified.get("name") or item_id)
        return EquipmentActionResult(
            character=char,
            character_id=character_id,
            item_id=item_id,
            item_name=name,
            equipment=equipment,
            narration=f"{char.name} identifie {name}.",
        )

    async def _load_character(self, character_id: str, db: AsyncSession) -> Character:
        result = await db.execute(select(Character).where(Character.id == character_id))
        char = result.scalar_one_or_none()
        if char is None:
            raise CharacterNotFoundError("Personnage introuvable")
        return char

    @staticmethod
    def _find_item(equipment: list[dict[str, Any]], item_id: str) -> tuple[int, dict[str, Any]]:
        for idx, item in enumerate(equipment):
            if item.get("id") == item_id:
                return idx, item
        raise ItemNotFoundError("Objet introuvable")


trade_service = TradeService()
