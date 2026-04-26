from __future__ import annotations

import asyncio
import uuid
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.game.event_bus import EventType, event_bus
from app.game.turn_manager import CombatantInfo
from app.models.character import Character
from app.models.message import Message
from app.models.save_slot import SaveSlot
from app.models.session import Session, SessionStatus

router = APIRouter()


class StartGameBody(BaseModel):
    adventure_script: Optional[str] = None
    auto_generate: bool = False


@router.get("/{session_id}/state")
async def get_game_state(session_id: str, db: AsyncSession = Depends(get_db)):
    """Get current game state."""
    from app.api.ws_game import session_manager

    active = session_manager.get_session(session_id)
    if active:
        return {
            "session_id": session_id,
            "phase": active.phase.value,
            "turn_number": active.turn_number,
            "round_number": active.round_number,
        }

    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    return {"session_id": session_id, "phase": session.status.value}


@router.post("/{session_id}/start")
async def start_game(
    session_id: str,
    body: StartGameBody = Body(default_factory=StartGameBody),
    db: AsyncSession = Depends(get_db),
):
    """Start a game session — transition to EXPLORATION and set up participants."""
    from app.api.ws_game import _build_session_state_payload, _character_snapshot, session_manager

    try:
        active = await session_manager.open_session(session_id, db)
    except KeyError:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found.")

    # Already past character creation — idempotent
    if active.phase not in (SessionStatus.LOBBY, SessionStatus.CHARACTER_CREATION):
        return {
            "status": "already_started",
            "phase": active.phase.value,
            "session_id": session_id,
        }

    # Load characters for this session
    result = await db.execute(
        select(Character).where(Character.session_id == session_id)
    )
    characters = result.scalars().all()

    if not characters:
        raise HTTPException(
            status_code=400,
            detail="Aucun personnage dans cette session. Créez un personnage d'abord.",
        )

    # Force-transition to EXPLORATION (bypasses strict state-machine validation)
    active.phase = SessionStatus.EXPLORATION

    # Set up TurnManager for exploration (round-robin)
    participants = [
        CombatantInfo(
            combatant_id=c.id,
            name=c.name,
            dex_score=int(c.ability_scores.get("dex", 10)),
            is_player=True,
            is_ai_controlled=c.is_ai,
        )
        for c in characters
    ]
    active.turn_manager.setup_exploration(participants)

    # Store character snapshots in state_data for later combat use
    active.state_data["characters"] = {
        c.id: _character_snapshot(c)
        for c in characters
    }

    # Seed world-state slices (idempotent — setdefault preserves existing saves)
    active.state_data.setdefault("adventure_journal", {
        "location_region": None,
        "location_place": None,
        "time_of_day": "morning",
        "day_number": 1,
        "calendar_date": None,
        "weather": None,
    })
    active.state_data.setdefault("quests", [])
    active.state_data.setdefault("chronicle", [])

    from app.services import campaign_dossier_service

    campaign_context = await campaign_dossier_service.compile_campaign_context_for_session(
        session_id,
        db,
    )
    if campaign_context is not None:
        active.state_data["campaign_context"] = campaign_context
    else:
        active.state_data.pop("campaign_context", None)

    # Store adventure context for the GM agent
    if body.adventure_script:
        active.state_data["adventure_script"] = body.adventure_script
    if body.auto_generate:
        active.state_data["auto_generate_adventure"] = True
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    # Notify any already-connected WebSocket clients
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.EXPLORATION.value},
        source="routes_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="routes_game",
    )

    from app.services.message_service import persist_narration

    if body.adventure_script:
        # Le script fourni devient la narration d'introduction
        welcome_text = body.adventure_script
        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {"text": welcome_text, "speaker": "Maître du Jeu"},
            source="routes_game",
        )
        await persist_narration(session_id, welcome_text, "Maître du Jeu", db)
    elif body.auto_generate:
        # Le MJ génère une accroche d'aventure adapée au groupe (fire-and-forget)
        from app.api.ws_game import _send_welcome_narration
        asyncio.create_task(_send_welcome_narration(session_id, active, db))
    else:
        # Mode libre : texte d'accueil neutre
        welcome_text = (
            "La partie commence ! Vous vous trouvez au seuil de l'aventure. "
            "Que souhaitez-vous faire ?"
        )
        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {"text": welcome_text, "speaker": "Maître du Jeu"},
            source="routes_game",
        )
        await persist_narration(session_id, welcome_text, "Maître du Jeu", db)

    return {
        "status": "ok",
        "phase": active.phase.value,
        "session_id": session_id,
        "characters": len(characters),
    }


# ─── Save / Load ──────────────────────────────────────────────────────────────


@router.post("/{session_id}/saves")
async def create_save(session_id: str, body: dict, db: AsyncSession = Depends(get_db)):
    """Creer un point de sauvegarde nomme pour la session."""
    from app.api.ws_game import session_manager

    name = (body.get("name") or "").strip()
    if not name:
        raise HTTPException(status_code=422, detail="Le nom de la sauvegarde est requis.")

    # Verifier que la session existe
    result = await db.execute(select(Session).where(Session.id == session_id))
    session = result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    # Obtenir l'etat courant (depuis la memoire ou la DB)
    active = session_manager.get_session(session_id)
    if active:
        phase_val = active.phase.value
        turn_number = active.turn_number
        round_number = active.round_number
        state_data = dict(active.state_data)
        # Snapshot TurnManager dans state_data
        state_data["turn_manager"] = active.turn_manager.to_dict()
        state_data["phase"] = phase_val
    else:
        from app.models.game_state import GameState
        gs_result = await db.execute(
            select(GameState).where(GameState.session_id == session_id)
        )
        gs = gs_result.scalar_one_or_none()
        phase_val = session.status.value
        turn_number = gs.turn_number if gs else 0
        round_number = gs.round_number if gs else 0
        state_data = dict(gs.state_data) if gs else {}

    # Snapshot de tous les personnages
    chars_result = await db.execute(
        select(Character).where(Character.session_id == session_id)
    )
    characters = chars_result.scalars().all()
    characters_snapshot = [
        {
            "id": c.id,
            "name": c.name,
            "player_name": c.player_name,
            "is_ai": c.is_ai,
            "species": c.species,
            "char_class": c.char_class,
            "level": c.level,
            "background": c.background,
            "ability_scores": c.ability_scores,
            "hp_current": c.hp_current,
            "hp_max": c.hp_max,
            "hp_temp": c.hp_temp,
            "equipment": c.equipment,
            "spell_slots": c.spell_slots,
            "known_spells": c.known_spells,
            "conditions": c.conditions,
            "proficiencies": c.proficiencies,
            "personality": c.personality,
        }
        for c in characters
    ]

    save_slot = SaveSlot(
        id=str(uuid.uuid4()),
        session_id=session_id,
        name=name,
        phase=phase_val,
        turn_number=turn_number,
        round_number=round_number,
        state_data=state_data,
        characters_snapshot=characters_snapshot,
    )
    db.add(save_slot)
    await db.commit()
    await db.refresh(save_slot)

    return {
        "id": save_slot.id,
        "session_id": save_slot.session_id,
        "name": save_slot.name,
        "phase": save_slot.phase,
        "turn_number": save_slot.turn_number,
        "round_number": save_slot.round_number,
        "characters_count": len(characters_snapshot),
        "created_at": save_slot.created_at.isoformat(),
    }


@router.get("/{session_id}/saves")
async def list_saves(session_id: str, db: AsyncSession = Depends(get_db)):
    """Lister toutes les sauvegardes d'une session."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    saves_result = await db.execute(
        select(SaveSlot)
        .where(SaveSlot.session_id == session_id)
        .order_by(SaveSlot.created_at.desc())
    )
    saves = saves_result.scalars().all()

    return {
        "saves": [
            {
                "id": s.id,
                "session_id": s.session_id,
                "name": s.name,
                "phase": s.phase,
                "turn_number": s.turn_number,
                "round_number": s.round_number,
                "characters_count": len(s.characters_snapshot),
                "created_at": s.created_at.isoformat(),
            }
            for s in saves
        ],
        "total": len(saves),
    }


@router.delete("/{session_id}/saves/{save_id}", status_code=204)
async def delete_save(session_id: str, save_id: str, db: AsyncSession = Depends(get_db)):
    """Supprimer une sauvegarde."""
    result = await db.execute(
        select(SaveSlot).where(
            SaveSlot.id == save_id, SaveSlot.session_id == session_id
        )
    )
    save = result.scalar_one_or_none()
    if save is None:
        raise HTTPException(status_code=404, detail="Sauvegarde introuvable.")

    await db.delete(save)
    await db.commit()


@router.post("/{session_id}/saves/{save_id}/load")
async def load_save(session_id: str, save_id: str, db: AsyncSession = Depends(get_db)):
    """Restaurer la session a partir d'une sauvegarde."""
    from app.api.ws_game import session_manager
    from app.models.game_state import GameState

    result = await db.execute(
        select(SaveSlot).where(
            SaveSlot.id == save_id, SaveSlot.session_id == session_id
        )
    )
    save = result.scalar_one_or_none()
    if save is None:
        raise HTTPException(status_code=404, detail="Sauvegarde introuvable.")

    # Verifier que la session existe
    sess_result = await db.execute(select(Session).where(Session.id == session_id))
    session = sess_result.scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    # Restaurer SessionStatus
    try:
        target_status = SessionStatus(save.phase)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Phase invalide : {save.phase!r}")

    session.status = target_status

    # Restaurer GameState
    gs_result = await db.execute(
        select(GameState).where(GameState.session_id == session_id)
    )
    gs = gs_result.scalar_one_or_none()
    if gs is None:
        gs = GameState(session_id=session_id)
        db.add(gs)

    gs.state_data = save.state_data
    gs.turn_number = save.turn_number
    gs.round_number = save.round_number

    # Restaurer les personnages depuis le snapshot
    chars_result = await db.execute(
        select(Character).where(Character.session_id == session_id)
    )
    existing_chars = {c.id: c for c in chars_result.scalars().all()}

    for snap in save.characters_snapshot:
        char = existing_chars.get(snap["id"])
        if char is None:
            continue
        char.hp_current = snap["hp_current"]
        char.hp_max = snap["hp_max"]
        char.hp_temp = snap["hp_temp"]
        char.level = snap["level"]
        char.ability_scores = snap["ability_scores"]
        char.equipment = snap["equipment"]
        char.spell_slots = snap["spell_slots"]
        char.known_spells = snap["known_spells"]
        char.conditions = snap["conditions"]
        char.proficiencies = snap["proficiencies"]

    await db.commit()

    # Si la session est active en memoire, la recharger
    if session_manager.is_active(session_id):
        await session_manager.close_session(session_id, db)
    await session_manager.open_session(session_id, db)
    from app.api.ws_game import _build_session_state_payload

    # Notifier les clients connectes
    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": save.phase},
        source="routes_game",
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        _build_session_state_payload(session_id),
        source="routes_game",
    )

    return {
        "status": "ok",
        "save_id": save_id,
        "phase": save.phase,
        "session_id": session_id,
    }


# ─── Historique narratif ──────────────────────────────────────────────────────


@router.get("/{session_id}/history")
async def get_history(
    session_id: str,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """Retourner les derniers messages narratifs pour restaurer le journal."""
    result = await db.execute(select(Session).where(Session.id == session_id))
    if result.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail="Session introuvable.")

    msgs_result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.created_at.desc())
        .limit(limit)
    )
    messages = list(msgs_result.scalars().all())
    messages.reverse()

    return {
        "messages": [
            {
                "id": m.id,
                "role": m.role.value,
                "speaker": m.speaker,
                "message_type": m.message_type.value,
                "content": m.content,
                "metadata": m.metadata_,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "total": len(messages),
    }
