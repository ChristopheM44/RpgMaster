from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession
from app.game.state_sync import sync_character_state
from app.models.character import Character


class SpellcastingServiceError(Exception):
    """Erreur métier lors de la préparation d'un sort."""


@dataclass
class SpellCastPreparation:
    caster: dict[str, Any]
    spell_slots: dict[str, Any]
    slot_level: int
    spell_level: int


class SpellcastingService:
    """DB-facing preparation for spell casting.

    The actual spell mechanics stay in ``ActionMechanics``; this service only
    loads the caster, consumes a slot when needed, syncs snapshots, and emits
    the resulting character update.
    """

    async def prepare_cast(
        self,
        *,
        session_id: str,
        character_id: Optional[str],
        spell_id: str,
        slot_level: Optional[int],
        active: ActiveSession,
        db: AsyncSession,
        event_bus_instance: Any = event_bus,
    ) -> Optional[SpellCastPreparation]:
        from app.game.action_mechanics import _load_spells

        if not character_id:
            return None

        result = await db.execute(select(Character).where(Character.id == character_id))
        char = result.scalar_one_or_none()
        if char is None:
            return None

        spells = _load_spells()
        spell = spells.get(spell_id)
        if not spell:
            return self._snapshot(char, slot_level=slot_level or 0, spell_level=0)

        spell_level = int(spell["level"])
        effective_slot = slot_level if slot_level is not None else spell_level
        if effective_slot < spell_level:
            effective_slot = spell_level
        if spell_level == 0:
            effective_slot = 0

        spell_slots: dict[str, Any] = dict(char.spell_slots) if char.spell_slots else {}
        if spell_level > 0:
            slot_key = str(effective_slot)
            slot_info = spell_slots.get(slot_key, {"total": 0, "used": 0})
            total = int(slot_info.get("total", 0))
            used = int(slot_info.get("used", 0))
            if total - used <= 0:
                raise SpellcastingServiceError(
                    f"Aucun emplacement de niveau {effective_slot} disponible."
                )

            spell_slots = dict(spell_slots)
            spell_slots[slot_key] = {"total": total, "used": used + 1}
            char.spell_slots = spell_slots
            await db.commit()
            await db.refresh(char)
            sync_character_state(active, character_id, spell_slots=spell_slots)

            await event_bus_instance.publish_to_session(
                session_id,
                EventType.SPELL_SLOT_UPDATED,
                {
                    "character_id": character_id,
                    "spell_slots": spell_slots,
                },
                source="spellcasting_service",
            )

        return self._snapshot(
            char,
            slot_level=effective_slot,
            spell_level=spell_level,
            spell_slots=spell_slots,
        )

    @staticmethod
    def _snapshot(
        char: Character,
        *,
        slot_level: int,
        spell_level: int,
        spell_slots: Optional[dict[str, Any]] = None,
    ) -> SpellCastPreparation:
        slots = dict(spell_slots if spell_slots is not None else (char.spell_slots or {}))
        remaining = {
            str(k): int(v.get("total", 0)) - int(v.get("used", 0))
            for k, v in slots.items()
            if isinstance(v, dict)
        }
        return SpellCastPreparation(
            caster={
                "id": char.id,
                "char_class": char.char_class,
                "level": char.level,
                "ability_scores": dict(char.ability_scores or {}),
                "spell_slots": slots,
                "slots_remaining": remaining,
            },
            spell_slots=slots,
            slot_level=slot_level,
            spell_level=spell_level,
        )
