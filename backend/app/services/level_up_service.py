"""Level-up persistence service."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.level_up import LevelUpResult, compute_level_up
from app.engine.xp import level_from_xp, xp_to_next_level
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession
from app.game.state_sync import sync_character_state
from app.models.character import Character


class LevelUpServiceError(Exception):
    """Base level-up service error."""


class CharacterNotFoundError(LevelUpServiceError):
    """The requested character does not exist."""


@dataclass
class AppliedLevelUp:
    character: Character
    result: LevelUpResult
    applied: bool


class LevelUpService:
    async def level_up_character(
        self,
        *,
        session_id: str,
        character_id: str,
        db: AsyncSession,
        active: Optional[ActiveSession] = None,
    ) -> AppliedLevelUp:
        result = await db.execute(select(Character).where(Character.id == character_id))
        char = result.scalar_one_or_none()
        if char is None:
            raise CharacterNotFoundError("Personnage introuvable")

        target_level = level_from_xp(int(getattr(char, "xp", 0) or 0))
        if int(char.level or 1) >= target_level:
            noop = compute_level_up(
                char_class=char.char_class,
                current_level=int(char.level or 1),
                target_level=int(char.level or 1),
                con_score=int((char.ability_scores or {}).get("con", 10)),
                current_spell_slots=char.spell_slots or {},
                current_hit_dice=char.hit_dice or {},
            )
            return AppliedLevelUp(character=char, result=noop, applied=False)

        old_hp = int(char.hp_current or 0)
        level_result = compute_level_up(
            char_class=char.char_class,
            current_level=int(char.level or 1),
            target_level=target_level,
            con_score=int((char.ability_scores or {}).get("con", 10)),
            current_spell_slots=char.spell_slots or {},
            current_hit_dice=char.hit_dice or {},
        )
        char.level = level_result.new_level
        char.hp_max = int(char.hp_max or 0) + level_result.hp_total_gain
        char.hp_current = old_hp + level_result.hp_total_gain
        char.spell_slots = level_result.new_spell_slots
        char.hit_dice = level_result.new_hit_dice
        if level_result.asi_levels_granted:
            personality = dict(char.personality or {})
            personality["pending_asi"] = True
            personality["pending_asi_levels"] = level_result.asi_levels_granted
            char.personality = personality

        await db.commit()
        await db.refresh(char)

        pending_asi = bool((char.personality or {}).get("pending_asi"))
        sync_character_state(
            active,
            character_id,
            hp=char.hp_current,
            hp_max=char.hp_max,
            level=char.level,
            spell_slots=char.spell_slots,
            hit_dice=char.hit_dice,
            pending_asi=pending_asi,
            xp_to_next_level=xp_to_next_level(int(char.xp or 0), int(char.level or 1)),
        )
        await event_bus.publish_to_session(
            session_id,
            EventType.CHARACTER_LEVELED_UP,
            {
                "character_id": character_id,
                "old_level": level_result.old_level,
                "new_level": level_result.new_level,
                "level": level_result.new_level,
                "hp_delta": level_result.hp_total_gain,
                "hp": char.hp_current,
                "hp_max": char.hp_max,
                "spell_slots": char.spell_slots,
                "hit_dice": char.hit_dice,
                "asi_levels_granted": level_result.asi_levels_granted,
                "requires_asi": pending_asi,
                "xp_to_next_level": xp_to_next_level(int(char.xp or 0), int(char.level or 1)),
            },
            source="level_up_service",
        )
        await event_bus.publish_to_session(
            session_id,
            EventType.HP_CHANGED,
            {"combatant_id": character_id, "delta": level_result.hp_total_gain, "hp": char.hp_current},
            source="level_up_service",
        )
        await event_bus.publish_to_session(
            session_id,
            EventType.SPELL_SLOT_UPDATED,
            {"character_id": character_id, "spell_slots": char.spell_slots},
            source="level_up_service",
        )
        await event_bus.publish_to_session(
            session_id,
            EventType.HIT_DICE_UPDATED,
            {"character_id": character_id, "hit_dice": char.hit_dice},
            source="level_up_service",
        )
        return AppliedLevelUp(character=char, result=level_result, applied=True)


level_up_service = LevelUpService()
