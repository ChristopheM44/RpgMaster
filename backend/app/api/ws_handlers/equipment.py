"""Equipment, trade, currency and character development WebSocket action handlers."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.ws_payloads import build_session_state_payload
from app.api.ws_schemas import PlayerActionMessage
from app.engine.xp import level_from_xp
from app.game.event_bus import EventType, event_bus
from app.game.runtime import session_manager
from app.game.state_sync import sync_character_state
from app.models.character import Character
from app.services.equipment_service import (
    CharacterNotFoundError,
    EquipmentService,
    ItemNotFoundError,
)
from app.services.level_up_service import AsiChoiceError, apply_asi_scores, level_up_service
from app.services.trade_service import trade_service

logger = logging.getLogger(__name__)

equipment_service = EquipmentService()


def _build_session_state_payload(session_id: str) -> dict[str, Any]:
    return build_session_state_payload(session_id, session_manager.get_session(session_id))


async def handle_equip_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Équipe ou retire un objet (toggle) pendant une session active."""
    item_id = action.item_id
    character_id = action.character_id
    if not item_id or not character_id:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "item_id et character_id requis pour équiper un objet."},
            source="ws_game",
        )
        return

    try:
        result = await equipment_service.equip_item(
            character_id=character_id,
            item_id=item_id,
            db=db,
            active=active,
        )
    except CharacterNotFoundError:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Personnage introuvable."},
            source="ws_game",
        )
        return
    except ItemNotFoundError:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"Objet '{item_id}' introuvable dans l'inventaire."},
            source="ws_game",
        )
        return

    await event_bus.publish_to_session(
        session_id,
        EventType.EQUIPMENT_UPDATED,
        {"character_id": character_id, "equipment": result.equipment},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": result.narration, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def handle_use_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Utilise un objet consommable pendant une session (potion = soin)."""
    item_id = action.item_id
    character_id = action.character_id
    if not item_id or not character_id:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "item_id et character_id requis pour utiliser un objet."},
            source="ws_game",
        )
        return

    try:
        result = await equipment_service.use_item(
            character_id=character_id,
            item_id=item_id,
            db=db,
            active=active,
        )
    except CharacterNotFoundError:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Personnage introuvable."},
            source="ws_game",
        )
        return
    except ItemNotFoundError:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"Objet '{item_id}' introuvable dans l'inventaire."},
            source="ws_game",
        )
        return

    if result.hp is not None:
        await event_bus.publish_to_session(
            session_id,
            EventType.HP_CHANGED,
            {"combatant_id": character_id, "delta": result.hp_delta, "hp": result.hp},
            source="ws_game",
        )

    await event_bus.publish_to_session(
        session_id,
        EventType.EQUIPMENT_UPDATED,
        {"character_id": character_id, "equipment": result.equipment},
        source="ws_game",
    )

    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": result.narration, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def handle_drop_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Retire définitivement un objet de l'inventaire."""
    item_id = action.item_id
    character_id = action.character_id
    if not item_id or not character_id:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "item_id et character_id requis pour lâcher un objet."},
            source="ws_game",
        )
        return

    try:
        result = await equipment_service.drop_item(
            character_id=character_id,
            item_id=item_id,
            db=db,
            active=active,
        )
    except CharacterNotFoundError:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Personnage introuvable."},
            source="ws_game",
        )
        return
    except ItemNotFoundError:
        return

    await event_bus.publish_to_session(
        session_id,
        EventType.EQUIPMENT_UPDATED,
        {"character_id": character_id, "equipment": result.equipment},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": result.narration, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def handle_give_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    item_id = action.item_id
    from_id = action.character_id
    to_id = action.target_id
    if not item_id or not from_id or not to_id:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "character_id, target_id et item_id requis pour donner un objet."},
            source="ws_game",
        )
        return
    try:
        sender_result, _ = await trade_service.give_item(
            session_id=session_id,
            from_character_id=from_id,
            to_character_id=to_id,
            item_id=item_id,
            db=db,
            active=active,
        )
    except Exception as exc:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": str(exc) or "Transfert impossible."},
            source="ws_game",
        )
        return
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": sender_result.narration, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def handle_give_currency(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    from_id = action.character_id
    to_id = action.target_id
    if not from_id or not to_id:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "character_id et target_id requis pour donner des pièces."},
            source="ws_game",
        )
        return
    try:
        await trade_service.give_currency(
            session_id=session_id,
            from_character_id=from_id,
            to_character_id=to_id,
            gp=action.gp or 0,
            sp=action.sp or 0,
            cp=action.cp or 0,
            db=db,
            active=active,
        )
    except Exception as exc:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": str(exc) or "Transfert de pièces impossible."},
            source="ws_game",
        )
        return
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": "Les pièces changent de mains.", "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def handle_identify_item(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    item_id = action.item_id
    character_id = action.character_id
    if not item_id or not character_id:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "item_id et character_id requis pour identifier un objet."},
            source="ws_game",
        )
        return
    try:
        result = await trade_service.identify_item(
            session_id=session_id,
            character_id=character_id,
            item_id=item_id,
            db=db,
            active=active,
        )
    except Exception as exc:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": str(exc) or "Identification impossible."},
            source="ws_game",
        )
        return
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": result.narration, "speaker": "Maître du Jeu"},
        source="ws_game",
    )


async def handle_asi_choice(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    character_id = action.character_id
    if not character_id:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "character_id requis pour appliquer l'ASI."},
            source="ws_game",
        )
        return
    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if char is None:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Personnage introuvable."},
            source="ws_game",
        )
        return
    scores = dict(char.ability_scores or {})
    mode = str(action.mode or "")
    try:
        scores = apply_asi_scores(
            scores,
            mode,
            ability=action.ability,
            abilities=list(action.abilities) if action.abilities else None,
        )
    except AsiChoiceError as exc:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": str(exc)},
            source="ws_game",
        )
        return
    char.ability_scores = scores
    personality = dict(char.personality or {})
    personality["pending_asi"] = False
    personality["pending_asi_levels"] = []
    char.personality = personality
    await db.commit()
    await db.refresh(char)
    sync_character_state(
        active,
        character_id,
        ability_scores=dict(char.ability_scores or {}),
        pending_asi=False,
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": f"{char.name} affine ses aptitudes.", "speaker": "Maître du Jeu"},
        source="ws_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="ws_game",
    )


async def handle_level_up(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    db: AsyncSession,
) -> None:
    """Déclenche manuellement un passage de niveau via WebSocket."""
    character_id = action.character_id
    if not character_id:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "character_id requis pour monter de niveau."},
            source="ws_game",
        )
        return

    result = await db.execute(select(Character).where(Character.id == character_id))
    char = result.scalar_one_or_none()
    if char is None:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": "Personnage introuvable."},
            source="ws_game",
        )
        return

    if level_from_xp(int(getattr(char, "xp", 0) or 0)) <= int(char.level or 1):
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"{char.name} n'a pas assez d'XP pour monter de niveau."},
            source="ws_game",
        )
        return

    applied = await level_up_service.level_up_character(
        session_id=session_id,
        character_id=character_id,
        db=db,
        active=active,
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {
            "text": f"{applied.character.name} passe au niveau {applied.result.new_level} !",
            "speaker": "Maître du Jeu",
        },
        source="ws_game",
    )
