"""Repos court/long et suivi des dés de vie."""
from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.engine.ability_checks import ability_modifier
from app.engine.character_creation import get_class_features
from app.engine.dice import RollResult, roll
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession, SessionManager
from app.models.character import Character
from app.models.session import SessionStatus
from app.services.message_service import persist_narration


class RestServiceError(Exception):
    """Erreur métier lors d'un repos."""


@dataclass
class RestCharacterUpdate:
    character_id: str
    character_name: str
    hp: int
    hp_delta: int = 0
    hit_dice: dict[str, int] = field(default_factory=dict)
    spell_slots: dict[str, Any] = field(default_factory=dict)
    roll_payload: Optional[dict[str, Any]] = None


@dataclass
class RestResult:
    kind: str
    narration: str
    updates: list[RestCharacterUpdate]


def build_hit_dice(
    char_class: str,
    level: int,
    raw: Optional[dict[str, Any]] = None,
) -> dict[str, int]:
    """Retourne un état de dés de vie canonique pour un personnage."""
    level_total = max(1, int(level or 1))
    die = _hit_die_for_class(char_class, raw)
    used = 0
    if isinstance(raw, dict):
        try:
            used = int(raw.get("used", 0) or 0)
        except (TypeError, ValueError):
            used = 0
    used = min(max(0, used), level_total)
    return {"die": die, "total": level_total, "used": used}


def normalize_character_hit_dice(character: Character) -> dict[str, int]:
    """Normalise et assigne les dés de vie d'un personnage si nécessaire."""
    normalized = build_hit_dice(
        character.char_class,
        character.level,
        character.hit_dice if isinstance(character.hit_dice, dict) else None,
    )
    if character.hit_dice != normalized:
        character.hit_dice = normalized
    return normalized


class RestService:
    """Orchestration des repos avec événements WebSocket optionnels."""

    def __init__(self, session_manager: Optional[SessionManager] = None) -> None:
        self._session_manager = session_manager

    async def short_rest(
        self,
        *,
        session_id: str,
        active: ActiveSession,
        db: AsyncSession,
        hit_dice_spend: dict[str, int],
        session_state_payload: Optional[Callable[[], dict[str, Any]]] = None,
    ) -> RestResult:
        try:
            spend = {
                str(character_id): int(count)
                for character_id, count in (hit_dice_spend or {}).items()
                if int(count) > 0
            }
        except (TypeError, ValueError) as exc:
            raise RestServiceError("Les dés de vie dépensés doivent être des nombres.") from exc
        if not spend:
            raise RestServiceError("Choisissez au moins un dé de vie à dépenser.")

        characters = await self._load_session_characters(session_id, db)
        by_id = {char.id: char for char in characters}
        unknown = sorted(set(spend) - set(by_id))
        if unknown:
            raise RestServiceError("Personnage introuvable pour le repos court.")

        updates: list[RestCharacterUpdate] = []
        for character_id, dice_count in spend.items():
            char = by_id[character_id]
            hit_dice = normalize_character_hit_dice(char)
            available = int(hit_dice["total"]) - int(hit_dice["used"])
            if dice_count > available:
                raise RestServiceError(
                    f"{char.name} n'a que {available} dé(s) de vie disponible(s)."
                )
            if int(char.hp_current) >= int(char.hp_max):
                raise RestServiceError(f"{char.name} a déjà tous ses points de vie.")

            update = self._apply_short_rest_healing(char, hit_dice, dice_count)
            updates.append(update)
            self._sync_character_update(active, update)

        await db.commit()
        active.mark_dirty()
        await self._save_active_state(session_id, db)

        narration = self._short_rest_narration(updates)
        await self._publish_short_rest_events(session_id, updates, narration, db)
        if session_state_payload is not None:
            await event_bus.publish_to_session(
                session_id,
                EventType.SESSION_STATE,
                session_state_payload(),
                source="rest_service",
            )
        return RestResult(kind="short_rest", narration=narration, updates=updates)

    async def long_rest(
        self,
        *,
        session_id: str,
        active: ActiveSession,
        db: AsyncSession,
        session_state_payload: Optional[Callable[[], dict[str, Any]]] = None,
    ) -> RestResult:
        characters = await self._load_session_characters(session_id, db)
        updates: list[RestCharacterUpdate] = []

        for char in characters:
            hit_dice = normalize_character_hit_dice(char)
            hit_dice["used"] = 0
            spell_slots = self._restore_spell_slots(char.spell_slots or {})
            old_hp = int(char.hp_current)

            char.hp_current = char.hp_max
            char.hit_dice = hit_dice
            char.spell_slots = spell_slots

            update = RestCharacterUpdate(
                character_id=char.id,
                character_name=char.name,
                hp=int(char.hp_current),
                hp_delta=max(0, int(char.hp_current) - old_hp),
                hit_dice=hit_dice,
                spell_slots=spell_slots,
            )
            updates.append(update)
            self._sync_character_update(active, update)

        await db.commit()

        active.phase = SessionStatus.EXPLORATION
        active.mark_dirty()
        await self._save_active_state(session_id, db)

        narration = (
            "Le groupe prend un long repos. Les blessures guérissent, "
            "les forces sont entièrement restaurées. L'aventure continue..."
        )
        await self._publish_long_rest_events(session_id, updates, narration, db)
        if session_state_payload is not None:
            await event_bus.publish_to_session(
                session_id,
                EventType.SESSION_STATE,
                session_state_payload(),
                source="rest_service",
            )
        return RestResult(kind="long_rest", narration=narration, updates=updates)

    async def _load_session_characters(
        self,
        session_id: str,
        db: AsyncSession,
    ) -> list[Character]:
        result = await db.execute(select(Character).where(Character.session_id == session_id))
        return list(result.scalars().all())

    def _apply_short_rest_healing(
        self,
        char: Character,
        hit_dice: dict[str, int],
        dice_count: int,
    ) -> RestCharacterUpdate:
        die = int(hit_dice["die"])
        con_score = int((char.ability_scores or {}).get("con", 10))
        con_modifier_total = ability_modifier(con_score) * dice_count
        notation = self._hit_dice_notation(dice_count, die, con_modifier_total)
        result = roll(notation)
        heal_total = max(1, int(result.total))
        old_hp = int(char.hp_current)
        new_hp = min(int(char.hp_max), old_hp + heal_total)
        hp_delta = max(0, new_hp - old_hp)

        hit_dice["used"] = int(hit_dice["used"]) + dice_count
        char.hp_current = new_hp
        char.hit_dice = hit_dice

        roll_payload = self._roll_payload(char, result, dice_count, die)
        return RestCharacterUpdate(
            character_id=char.id,
            character_name=char.name,
            hp=new_hp,
            hp_delta=hp_delta,
            hit_dice=dict(hit_dice),
            spell_slots=dict(char.spell_slots or {}),
            roll_payload=roll_payload,
        )

    @staticmethod
    def _hit_dice_notation(dice_count: int, die: int, modifier: int) -> str:
        base = f"{dice_count}d{die}"
        if modifier > 0:
            return f"{base}+{modifier}"
        if modifier < 0:
            return f"{base}{modifier}"
        return base

    @staticmethod
    def _roll_payload(
        char: Character,
        result: RollResult,
        dice_count: int,
        die: int,
    ) -> dict[str, Any]:
        return {
            "dice_notation": result.notation,
            "rolls": result.rolls,
            "modifier": result.modifier,
            "total": result.total,
            "label": f"Repos court - {char.name}",
            "breakdown": f"{dice_count}d{die} + CON = {result.total}",
            "character_id": char.id,
            "character_name": char.name,
        }

    @staticmethod
    def _restore_spell_slots(spell_slots: dict[str, Any]) -> dict[str, Any]:
        restored: dict[str, Any] = {}
        for level, slot in spell_slots.items():
            if isinstance(slot, dict):
                restored[str(level)] = {**slot, "used": 0}
            else:
                restored[str(level)] = slot
        return restored

    @staticmethod
    def _sync_character_update(active: ActiveSession, update: RestCharacterUpdate) -> None:
        chars_data = active.state_data.get("characters", {})
        if update.character_id in chars_data:
            chars_data[update.character_id]["hp"] = update.hp
            chars_data[update.character_id]["hit_dice"] = dict(update.hit_dice)
            chars_data[update.character_id]["spell_slots"] = dict(update.spell_slots)

        combatants = active.state_data.get("combatants", {})
        if update.character_id in combatants:
            combatants[update.character_id]["hp"] = update.hp

    async def _save_active_state(self, session_id: str, db: AsyncSession) -> None:
        if self._session_manager is not None:
            await self._session_manager.save_state(session_id, db)

    async def _publish_short_rest_events(
        self,
        session_id: str,
        updates: list[RestCharacterUpdate],
        narration: str,
        db: AsyncSession,
    ) -> None:
        for update in updates:
            if update.roll_payload is not None:
                await event_bus.publish_to_session(
                    session_id,
                    EventType.ROLL_RESULT,
                    update.roll_payload,
                    source="rest_service",
                )
            await event_bus.publish_to_session(
                session_id,
                EventType.HP_CHANGED,
                {
                    "combatant_id": update.character_id,
                    "delta": update.hp_delta,
                    "hp": update.hp,
                },
                source="rest_service",
            )
            await event_bus.publish_to_session(
                session_id,
                EventType.HIT_DICE_UPDATED,
                {"character_id": update.character_id, "hit_dice": update.hit_dice},
                source="rest_service",
            )

        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {"text": narration, "speaker": "Maître du Jeu"},
            source="rest_service",
        )
        await persist_narration(session_id, narration, "Maître du Jeu", db)

    async def _publish_long_rest_events(
        self,
        session_id: str,
        updates: list[RestCharacterUpdate],
        narration: str,
        db: AsyncSession,
    ) -> None:
        await event_bus.publish_to_session(
            session_id,
            EventType.PHASE_CHANGE,
            {"phase": SessionStatus.EXPLORATION.value},
            source="rest_service",
        )
        for update in updates:
            await event_bus.publish_to_session(
                session_id,
                EventType.HP_CHANGED,
                {
                    "combatant_id": update.character_id,
                    "delta": update.hp_delta,
                    "hp": update.hp,
                },
                source="rest_service",
            )
            await event_bus.publish_to_session(
                session_id,
                EventType.SPELL_SLOT_UPDATED,
                {"character_id": update.character_id, "spell_slots": update.spell_slots},
                source="rest_service",
            )
            await event_bus.publish_to_session(
                session_id,
                EventType.HIT_DICE_UPDATED,
                {"character_id": update.character_id, "hit_dice": update.hit_dice},
                source="rest_service",
            )

        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {"text": narration, "speaker": "Maître du Jeu"},
            source="rest_service",
        )
        await persist_narration(session_id, narration, "Maître du Jeu", db)

    @staticmethod
    def _short_rest_narration(updates: list[RestCharacterUpdate]) -> str:
        fragments = [
            f"{update.character_name} récupère {update.hp_delta} PV"
            for update in updates
        ]
        return "Le groupe prend un repos court. " + "; ".join(fragments) + "."


def _hit_die_for_class(char_class: str, raw: Optional[dict[str, Any]]) -> int:
    try:
        return int(get_class_features(char_class).hit_die)
    except ValueError:
        if isinstance(raw, dict):
            try:
                raw_die = int(raw.get("die", 8) or 8)
            except (TypeError, ValueError):
                raw_die = 8
            return max(4, raw_die)
        return 8
