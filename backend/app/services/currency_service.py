"""Currency persistence service."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.currency import (
    InsufficientFundsError,
    Wealth,
    add_coins,
    normalize_wealth,
    subtract_cost,
    total_value_cp,
)
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession
from app.game.state_sync import sync_character_state
from app.models.character import Character


class CurrencyServiceError(Exception):
    """Base currency service error."""


class CharacterNotFoundError(CurrencyServiceError):
    """The requested character does not exist."""


@dataclass
class CurrencyResult:
    character: Character
    character_id: str
    old_wealth: Wealth
    new_wealth: Wealth
    delta_cp: int


class CurrencyService:
    async def grant_currency(
        self,
        *,
        session_id: str,
        character_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
        gp: int = 0,
        sp: int = 0,
        cp: int = 0,
    ) -> CurrencyResult:
        if min(int(gp), int(sp), int(cp)) < 0:
            raise ValueError("Coin grants must be non-negative")
        char = await self._load_character(character_id, db)
        old = self._wealth_for(char)
        new = add_coins(old, gp=int(gp), sp=int(sp), cp=int(cp))
        self._apply_wealth(char, new)
        await db.commit()
        await db.refresh(char)
        await self._publish(session_id, char, old, new, active)
        return CurrencyResult(
            character=char,
            character_id=character_id,
            old_wealth=old,
            new_wealth=new,
            delta_cp=total_value_cp(new.gp, new.sp, new.cp) - total_value_cp(old.gp, old.sp, old.cp),
        )

    async def spend_currency(
        self,
        *,
        session_id: str,
        character_id: str,
        cost_gp: int | float | str | Decimal,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> CurrencyResult:
        char = await self._load_character(character_id, db)
        old = self._wealth_for(char)
        new = subtract_cost(old, cost_gp)
        self._apply_wealth(char, new)
        await db.commit()
        await db.refresh(char)
        await self._publish(session_id, char, old, new, active)
        return CurrencyResult(
            character=char,
            character_id=character_id,
            old_wealth=old,
            new_wealth=new,
            delta_cp=total_value_cp(new.gp, new.sp, new.cp) - total_value_cp(old.gp, old.sp, old.cp),
        )

    async def transfer_currency(
        self,
        *,
        session_id: str,
        from_id: str,
        to_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
        gp: int = 0,
        sp: int = 0,
        cp: int = 0,
    ) -> tuple[CurrencyResult, CurrencyResult]:
        if min(int(gp), int(sp), int(cp)) < 0:
            raise ValueError("Coin transfers must be non-negative")
        sender = await self._load_character(from_id, db)
        receiver = await self._load_character(to_id, db)
        old_sender = self._wealth_for(sender)
        old_receiver = self._wealth_for(receiver)
        cost_gp = Decimal(total_value_cp(gp, sp, cp)) / Decimal(100)
        new_sender = subtract_cost(old_sender, cost_gp)
        new_receiver = add_coins(old_receiver, gp=int(gp), sp=int(sp), cp=int(cp))
        self._apply_wealth(sender, new_sender)
        self._apply_wealth(receiver, new_receiver)
        await db.commit()
        await db.refresh(sender)
        await db.refresh(receiver)
        await self._publish(session_id, sender, old_sender, new_sender, active)
        await self._publish(session_id, receiver, old_receiver, new_receiver, active)
        return (
            CurrencyResult(sender, from_id, old_sender, new_sender, -total_value_cp(gp, sp, cp)),
            CurrencyResult(receiver, to_id, old_receiver, new_receiver, total_value_cp(gp, sp, cp)),
        )

    async def _load_character(self, character_id: str, db: AsyncSession) -> Character:
        result = await db.execute(select(Character).where(Character.id == character_id))
        char = result.scalar_one_or_none()
        if char is None:
            raise CharacterNotFoundError("Personnage introuvable")
        return char

    @staticmethod
    def _wealth_for(char: Character) -> Wealth:
        return normalize_wealth(
            gp=int(getattr(char, "gp", 0) or 0),
            sp=int(getattr(char, "sp", 0) or 0),
            cp=int(getattr(char, "cp", 0) or 0),
        )

    @staticmethod
    def _apply_wealth(char: Character, wealth: Wealth) -> None:
        char.gp = wealth.gp
        char.sp = wealth.sp
        char.cp = wealth.cp

    async def _publish(
        self,
        session_id: str,
        char: Character,
        old: Wealth,
        new: Wealth,
        active: Optional[ActiveSession],
    ) -> None:
        sync_character_state(active, char.id, gp=new.gp, sp=new.sp, cp=new.cp)
        await event_bus.publish_to_session(
            session_id,
            EventType.CURRENCY_UPDATED,
            {
                "character_id": char.id,
                "gp": new.gp,
                "sp": new.sp,
                "cp": new.cp,
                "old_gp": old.gp,
                "old_sp": old.sp,
                "old_cp": old.cp,
            },
            source="currency_service",
        )


currency_service = CurrencyService()
