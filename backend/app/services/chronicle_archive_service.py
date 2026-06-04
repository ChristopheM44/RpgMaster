"""Import/export d'archives de chroniques RPGMaster."""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.game.runtime import session_manager
from app.game.state_schema import migrate_state_data
from app.models.campaign import Campaign
from app.models.campaign_dossier import CampaignDossier
from app.models.character import Character
from app.models.game_state import GameState
from app.models.message import Message, MessageRole, MessageType
from app.models.save_slot import SaveSlot
from app.models.session import Session, SessionStatus
from app.services import campaign_dossier_service, campaign_service

ARCHIVE_FORMAT = "rpgmaster.chronicle"
ARCHIVE_VERSION = 1
APP_VERSION = "0.1.0"


class ChronicleArchiveError(ValueError):
    """Base class for archive validation/import errors."""


class ChronicleArchiveNotFoundError(KeyError):
    """Raised when the source campaign does not exist."""


class ChronicleArchiveConflictError(ChronicleArchiveError):
    """Raised when preserved IDs already exist in the target database."""

    def __init__(self, conflicts: list[dict[str, str]]) -> None:
        super().__init__("Chronicle archive conflicts with existing data.")
        self.conflicts = conflicts


@dataclass
class ChronicleImportResult:
    campaign: Campaign
    active_session_id: str | None
    imported: dict[str, int]
    warnings: list[str]


def safe_archive_filename(name: str) -> str:
    ascii_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", name.strip()).strip("-._")
    return f"rpgmaster-chronique-{(ascii_name or 'chronique').lower()}.json"


async def export_chronicle(campaign_id: str, db: AsyncSession) -> dict[str, Any]:
    campaign = await campaign_service.get_campaign(campaign_id, db)
    if campaign is None:
        raise ChronicleArchiveNotFoundError(f"Campaign {campaign_id} not found")

    for session_id in list(campaign.session_ids or []):
        if session_manager.is_active(session_id):
            await session_manager.save_state(session_id, db)

    session_ids = list(campaign.session_ids or [])
    sessions_by_id = await _sessions_by_id(session_ids, db)
    dossier = await campaign_dossier_service.get_dossier(campaign.id, db)
    session_exports = []
    for session_id in session_ids:
        session = sessions_by_id.get(session_id)
        if session is None:
            continue
        session_exports.append(await _export_session(session, db))

    archive = {
        "format": ARCHIVE_FORMAT,
        "format_version": ARCHIVE_VERSION,
        "exported_at": _now_iso(),
        "app_version": APP_VERSION,
        "manifest": _manifest(campaign, dossier, session_exports),
        "campaign": _campaign_payload(campaign),
        "dossier": _dossier_payload(dossier) if dossier is not None else None,
        "sessions": session_exports,
    }
    warnings = collect_archive_warnings(archive)
    if warnings:
        archive["manifest"]["warnings"] = warnings
    return archive


async def preview_import(archive: dict[str, Any], db: AsyncSession) -> dict[str, Any]:
    normalized = validate_archive_payload(archive)
    conflicts = await find_conflicts(normalized, db)
    warnings = collect_archive_warnings(normalized)
    return {
        "manifest": normalized["manifest"],
        "conflicts": conflicts,
        "warnings": warnings,
    }


async def import_chronicle(archive: dict[str, Any], db: AsyncSession) -> ChronicleImportResult:
    normalized = validate_archive_payload(archive)
    conflicts = await find_conflicts(normalized, db)
    if conflicts:
        raise ChronicleArchiveConflictError(conflicts)

    try:
        campaign_data = normalized["campaign"]
        campaign = Campaign(
            id=campaign_data["id"],
            name=campaign_data["name"],
            description=campaign_data.get("description", ""),
            starting_level=int(campaign_data.get("starting_level", 1) or 1),
            session_ids=list(campaign_data.get("session_ids") or []),
            current_session_index=int(campaign_data.get("current_session_index", 0) or 0),
            character_ids=list(campaign_data.get("character_ids") or []),
            xp_pool=dict(campaign_data.get("xp_pool") or {}),
            created_at=_parse_datetime(campaign_data.get("created_at")),
            updated_at=_parse_datetime(campaign_data.get("updated_at")),
        )
        db.add(campaign)

        imported = {"sessions": 0, "characters": 0, "messages": 0, "save_slots": 0}
        game_states = 0
        for bundle in normalized["sessions"]:
            session = _session_from_payload(bundle["session"])
            db.add(session)
            imported["sessions"] += 1

            for char_data in bundle.get("characters", []):
                db.add(_character_from_payload(char_data, session.id))
                imported["characters"] += 1

            game_state_data = bundle.get("game_state")
            if game_state_data is not None:
                db.add(_game_state_from_payload(game_state_data, session.id))
                game_states += 1

            for message_data in bundle.get("messages", []):
                db.add(_message_from_payload(message_data, session.id))
                imported["messages"] += 1

            for save_data in bundle.get("save_slots", []):
                db.add(_save_slot_from_payload(save_data, session.id))
                imported["save_slots"] += 1

        dossier_data = normalized.get("dossier")
        if isinstance(dossier_data, dict):
            db.add(_dossier_from_payload(dossier_data, campaign))

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    await db.refresh(campaign)
    active_session_id = _active_session_id(campaign)
    return ChronicleImportResult(
        campaign=campaign,
        active_session_id=active_session_id,
        imported={**imported, "game_states": game_states},
        warnings=collect_archive_warnings(normalized),
    )


def validate_archive_payload(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise ChronicleArchiveError("Archive must be a JSON object.")
    if raw.get("format") != ARCHIVE_FORMAT:
        raise ChronicleArchiveError("Archive format is not supported.")
    if int(raw.get("format_version") or 0) != ARCHIVE_VERSION:
        raise ChronicleArchiveError("Archive version is not supported.")
    campaign = raw.get("campaign")
    sessions = raw.get("sessions")
    if not isinstance(campaign, dict):
        raise ChronicleArchiveError("Archive campaign block is missing.")
    if not isinstance(sessions, list):
        raise ChronicleArchiveError("Archive sessions block is missing.")

    _require_uuid(campaign.get("id"), "campaign.id")
    _require_text(campaign.get("name"), "campaign.name")
    session_ids = _string_list(campaign.get("session_ids"), "campaign.session_ids")
    _string_list(campaign.get("character_ids"), "campaign.character_ids")
    if campaign.get("xp_pool") is not None and not isinstance(campaign.get("xp_pool"), dict):
        raise ChronicleArchiveError("campaign.xp_pool must be an object.")

    normalized_sessions = []
    seen_sessions: set[str] = set()
    for index, bundle in enumerate(sessions):
        if not isinstance(bundle, dict):
            raise ChronicleArchiveError(f"sessions[{index}] must be an object.")
        session = bundle.get("session")
        if not isinstance(session, dict):
            raise ChronicleArchiveError(f"sessions[{index}].session is missing.")
        session_id = _require_uuid(session.get("id"), f"sessions[{index}].session.id")
        if session_id in seen_sessions:
            raise ChronicleArchiveError(f"Duplicate session id in archive: {session_id}")
        seen_sessions.add(session_id)
        _coerce_session_status(session.get("status"), f"sessions[{index}].session.status")

        game_state = bundle.get("game_state")
        if game_state is not None:
            _validate_game_state(game_state, session_id, index)

        characters = _list_of_dicts(bundle.get("characters"), f"sessions[{index}].characters")
        for char_idx, char_data in enumerate(characters):
            _validate_character(char_data, session_id, index, char_idx)

        messages = _list_of_dicts(bundle.get("messages"), f"sessions[{index}].messages")
        for msg_idx, message_data in enumerate(messages):
            _validate_message(message_data, session_id, index, msg_idx)

        save_slots = _list_of_dicts(bundle.get("save_slots"), f"sessions[{index}].save_slots")
        for save_idx, save_data in enumerate(save_slots):
            _validate_save_slot(save_data, session_id, index, save_idx)

        normalized_sessions.append(
            {
                "session": session,
                "game_state": game_state,
                "characters": characters,
                "messages": messages,
                "save_slots": save_slots,
            }
        )

    missing_sessions = [session_id for session_id in session_ids if session_id not in seen_sessions]
    if missing_sessions:
        raise ChronicleArchiveError(
            f"Archive is missing referenced sessions: {', '.join(missing_sessions)}"
        )

    manifest = raw.get("manifest") if isinstance(raw.get("manifest"), dict) else {}
    return {
        "format": ARCHIVE_FORMAT,
        "format_version": ARCHIVE_VERSION,
        "exported_at": str(raw.get("exported_at") or ""),
        "app_version": str(raw.get("app_version") or ""),
        "manifest": _normalized_manifest(manifest, campaign, normalized_sessions),
        "campaign": campaign,
        "dossier": _validate_dossier(raw.get("dossier"), campaign.get("id")),
        "sessions": normalized_sessions,
    }


async def find_conflicts(archive: dict[str, Any], db: AsyncSession) -> list[dict[str, str]]:
    ids = _archive_ids(archive)
    checks = (
        ("campaign", Campaign, ids["campaigns"]),
        ("campaign_dossier", CampaignDossier, ids["dossiers"]),
        ("session", Session, ids["sessions"]),
        ("game_state", GameState, ids["game_states"]),
        ("character", Character, ids["characters"]),
        ("message", Message, ids["messages"]),
        ("save_slot", SaveSlot, ids["save_slots"]),
    )
    conflicts: list[dict[str, str]] = []
    for kind, model, values in checks:
        if not values:
            continue
        result = await db.execute(select(model.id).where(model.id.in_(values)))
        for item_id in result.scalars().all():
            conflicts.append({"kind": kind, "id": str(item_id)})
    return conflicts


def collect_archive_warnings(archive: dict[str, Any]) -> list[str]:
    urls: set[str] = set()

    def visit(value: Any) -> None:
        if isinstance(value, dict):
            visual_asset = value.get("visual_asset")
            if isinstance(visual_asset, dict):
                url = str(visual_asset.get("url") or "").strip()
                if url and _is_nonportable_url(url):
                    urls.add(url)
            for child in value.values():
                visit(child)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(archive)
    warnings = []
    if urls:
        warnings.append(
            "Certaines images de cartes utilisent des URLs locales ou non portables "
            f"({len(urls)} référence(s)). Elles pourront être régénérées sur l'autre PC."
        )
    return warnings


async def _sessions_by_id(session_ids: list[str], db: AsyncSession) -> dict[str, Session]:
    if not session_ids:
        return {}
    result = await db.execute(select(Session).where(Session.id.in_(session_ids)))
    return {session.id: session for session in result.scalars().all()}


async def _export_session(session: Session, db: AsyncSession) -> dict[str, Any]:
    game_state_result = await db.execute(
        select(GameState).where(GameState.session_id == session.id)
    )
    game_state = game_state_result.scalar_one_or_none()
    chars_result = await db.execute(
        select(Character).where(Character.session_id == session.id).order_by(Character.created_at)
    )
    messages_result = await db.execute(
        select(Message).where(Message.session_id == session.id).order_by(Message.created_at)
    )
    saves_result = await db.execute(
        select(SaveSlot).where(SaveSlot.session_id == session.id).order_by(SaveSlot.created_at)
    )
    return {
        "session": _session_payload(session),
        "game_state": _game_state_payload(game_state) if game_state is not None else None,
        "characters": [_character_payload(c) for c in chars_result.scalars().all()],
        "messages": [_message_payload(m) for m in messages_result.scalars().all()],
        "save_slots": [_save_slot_payload(s) for s in saves_result.scalars().all()],
    }


def _manifest(
    campaign: Campaign,
    dossier: CampaignDossier | None,
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    messages = sum(len(bundle.get("messages") or []) for bundle in sessions)
    saves = sum(len(bundle.get("save_slots") or []) for bundle in sessions)
    characters = sum(len(bundle.get("characters") or []) for bundle in sessions)
    return {
        "campaign": {
            "id": campaign.id,
            "name": campaign.name,
            "updated_at": campaign.updated_at.isoformat(),
        },
        "sessions": [_session_summary(bundle["session"]) for bundle in sessions],
        "includes": {
            "gm_private": dossier is not None,
            "messages": messages,
            "save_slots": saves,
            "characters": characters,
            "assets": False,
        },
    }


def _normalized_manifest(
    manifest: dict[str, Any],
    campaign: dict[str, Any],
    sessions: list[dict[str, Any]],
) -> dict[str, Any]:
    if manifest:
        return manifest
    messages = sum(len(bundle.get("messages") or []) for bundle in sessions)
    saves = sum(len(bundle.get("save_slots") or []) for bundle in sessions)
    characters = sum(len(bundle.get("characters") or []) for bundle in sessions)
    return {
        "campaign": {
            "id": campaign.get("id"),
            "name": campaign.get("name"),
            "updated_at": campaign.get("updated_at") or "",
        },
        "sessions": [_session_summary(bundle["session"]) for bundle in sessions],
        "includes": {
            "gm_private": True,
            "messages": messages,
            "save_slots": saves,
            "characters": characters,
            "assets": False,
        },
    }


def _campaign_payload(campaign: Campaign) -> dict[str, Any]:
    return {
        "id": campaign.id,
        "name": campaign.name,
        "description": campaign.description,
        "starting_level": campaign.starting_level,
        "session_ids": list(campaign.session_ids or []),
        "current_session_index": campaign.current_session_index,
        "character_ids": list(campaign.character_ids or []),
        "xp_pool": dict(campaign.xp_pool or {}),
        "created_at": campaign.created_at.isoformat(),
        "updated_at": campaign.updated_at.isoformat(),
    }


def _dossier_payload(dossier: CampaignDossier) -> dict[str, Any]:
    return {
        "id": dossier.id,
        "campaign_id": dossier.campaign_id,
        "player_contract": dossier.player_contract or {},
        "gm_dossier": dossier.gm_dossier or {},
        "played_canon": dossier.played_canon or {},
        "import_sources": list(dossier.import_sources or []),
        "forge_job": dossier.forge_job or {},
        "active_chapter_id": dossier.active_chapter_id,
        "generation_status": dossier.generation_status,
        "created_at": dossier.created_at.isoformat(),
        "updated_at": dossier.updated_at.isoformat(),
    }


def _session_payload(session: Session) -> dict[str, Any]:
    return {
        "id": session.id,
        "name": session.name,
        "status": session.status.value,
        "created_at": session.created_at.isoformat(),
        "updated_at": session.updated_at.isoformat(),
    }


def _game_state_payload(game_state: GameState) -> dict[str, Any]:
    return {
        "id": game_state.id,
        "session_id": game_state.session_id,
        "turn_number": game_state.turn_number,
        "round_number": game_state.round_number,
        "state_data": game_state.state_data or {},
        "updated_at": game_state.updated_at.isoformat(),
    }


def _character_payload(character: Character) -> dict[str, Any]:
    return {
        "id": character.id,
        "name": character.name,
        "player_name": character.player_name,
        "is_ai": character.is_ai,
        "species": character.species,
        "char_class": character.char_class,
        "level": character.level,
        "background": character.background,
        "ability_scores": character.ability_scores or {},
        "hp_current": character.hp_current,
        "hp_max": character.hp_max,
        "hp_temp": character.hp_temp,
        "xp": character.xp,
        "gp": character.gp,
        "sp": character.sp,
        "cp": character.cp,
        "equipment": list(character.equipment or []),
        "spell_slots": dict(character.spell_slots or {}),
        "hit_dice": dict(character.hit_dice or {}),
        "known_spells": list(character.known_spells or []),
        "conditions": list(character.conditions or []),
        "proficiencies": dict(character.proficiencies or {}),
        "personality": dict(character.personality or {}),
        "session_id": character.session_id,
        "created_at": character.created_at.isoformat(),
        "updated_at": character.updated_at.isoformat(),
    }


def _message_payload(message: Message) -> dict[str, Any]:
    return {
        "id": message.id,
        "session_id": message.session_id,
        "role": message.role.value,
        "speaker": message.speaker,
        "message_type": message.message_type.value,
        "content": message.content,
        "metadata": message.metadata_,
        "created_at": message.created_at.isoformat(),
    }


def _save_slot_payload(save_slot: SaveSlot) -> dict[str, Any]:
    return {
        "id": save_slot.id,
        "session_id": save_slot.session_id,
        "name": save_slot.name,
        "phase": save_slot.phase,
        "turn_number": save_slot.turn_number,
        "round_number": save_slot.round_number,
        "state_data": save_slot.state_data or {},
        "characters_snapshot": list(save_slot.characters_snapshot or []),
        "created_at": save_slot.created_at.isoformat(),
    }


def _session_summary(session_data: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": session_data.get("id"),
        "name": session_data.get("name"),
        "status": session_data.get("status"),
        "created_at": session_data.get("created_at"),
        "updated_at": session_data.get("updated_at"),
    }


def _session_from_payload(data: dict[str, Any]) -> Session:
    return Session(
        id=data["id"],
        name=data["name"],
        status=SessionStatus(str(data["status"]).lower()),
        created_at=_parse_datetime(data.get("created_at")),
        updated_at=_parse_datetime(data.get("updated_at")),
    )


def _character_from_payload(data: dict[str, Any], session_id: str) -> Character:
    return Character(
        id=data["id"],
        name=data["name"],
        player_name=data.get("player_name"),
        is_ai=bool(data.get("is_ai", False)),
        species=data["species"],
        char_class=data["char_class"],
        level=int(data.get("level", 1) or 1),
        background=data.get("background"),
        ability_scores=dict(data.get("ability_scores") or {}),
        hp_current=int(data.get("hp_current", 0) or 0),
        hp_max=int(data.get("hp_max", 0) or 0),
        hp_temp=int(data.get("hp_temp", 0) or 0),
        xp=int(data.get("xp", 0) or 0),
        gp=int(data.get("gp", 0) or 0),
        sp=int(data.get("sp", 0) or 0),
        cp=int(data.get("cp", 0) or 0),
        equipment=list(data.get("equipment") or []),
        spell_slots=dict(data.get("spell_slots") or {}),
        hit_dice=dict(data.get("hit_dice") or {}),
        known_spells=list(data.get("known_spells") or []),
        conditions=list(data.get("conditions") or []),
        proficiencies=dict(data.get("proficiencies") or {}),
        personality=dict(data.get("personality") or {}),
        session_id=session_id,
        created_at=_parse_datetime(data.get("created_at")),
        updated_at=_parse_datetime(data.get("updated_at")),
    )


def _game_state_from_payload(data: dict[str, Any], session_id: str) -> GameState:
    return GameState(
        id=data["id"],
        session_id=session_id,
        turn_number=int(data.get("turn_number", 0) or 0),
        round_number=int(data.get("round_number", 0) or 0),
        state_data=migrate_state_data(data.get("state_data") or {}),
        updated_at=_parse_datetime(data.get("updated_at")),
    )


def _message_from_payload(data: dict[str, Any], session_id: str) -> Message:
    return Message(
        id=data["id"],
        session_id=session_id,
        role=MessageRole(str(data["role"]).lower()),
        speaker=data["speaker"],
        message_type=MessageType(str(data["message_type"]).lower()),
        content=data["content"],
        metadata_=data.get("metadata"),
        created_at=_parse_datetime(data.get("created_at")),
    )


def _save_slot_from_payload(data: dict[str, Any], session_id: str) -> SaveSlot:
    return SaveSlot(
        id=data["id"],
        session_id=session_id,
        name=data["name"],
        phase=SessionStatus(str(data["phase"]).lower()).value,
        turn_number=int(data.get("turn_number", 0) or 0),
        round_number=int(data.get("round_number", 0) or 0),
        state_data=migrate_state_data(data.get("state_data") or {}),
        characters_snapshot=list(data.get("characters_snapshot") or []),
        created_at=_parse_datetime(data.get("created_at")),
    )


def _dossier_from_payload(data: dict[str, Any], campaign: Campaign) -> CampaignDossier:
    contract = campaign_dossier_service.sanitize_player_contract(
        data.get("player_contract") or {},
        campaign,
        brief={},
    )
    gm_dossier = campaign_dossier_service.sanitize_gm_dossier(
        data.get("gm_dossier") or {},
        campaign,
        contract,
    )
    played_canon = campaign_dossier_service.sanitize_played_canon(data.get("played_canon") or {})
    generation_status = str(data.get("generation_status") or "empty")
    if generation_status not in campaign_dossier_service.VALID_STATUSES:
        generation_status = "empty"
    return CampaignDossier(
        id=data["id"],
        campaign_id=campaign.id,
        player_contract=contract,
        gm_dossier=gm_dossier,
        played_canon=played_canon,
        import_sources=list(data.get("import_sources") or []),
        forge_job=dict(data.get("forge_job") or {}),
        active_chapter_id=str(data.get("active_chapter_id") or ""),
        generation_status=generation_status,
        created_at=_parse_datetime(data.get("created_at")),
        updated_at=_parse_datetime(data.get("updated_at")),
    )


def _validate_game_state(data: Any, session_id: str, index: int) -> None:
    if not isinstance(data, dict):
        raise ChronicleArchiveError(f"sessions[{index}].game_state must be an object.")
    _require_uuid(data.get("id"), f"sessions[{index}].game_state.id")
    if data.get("session_id") != session_id:
        raise ChronicleArchiveError(f"sessions[{index}].game_state.session_id mismatch.")
    migrate_state_data(data.get("state_data") or {})


def _validate_character(
    data: dict[str, Any],
    session_id: str,
    session_idx: int,
    char_idx: int,
) -> None:
    prefix = f"sessions[{session_idx}].characters[{char_idx}]"
    _require_uuid(data.get("id"), f"{prefix}.id")
    _require_text(data.get("name"), f"{prefix}.name")
    _require_text(data.get("species"), f"{prefix}.species")
    _require_text(data.get("char_class"), f"{prefix}.char_class")
    if data.get("session_id") not in (None, session_id):
        raise ChronicleArchiveError(f"{prefix}.session_id mismatch.")


def _validate_message(
    data: dict[str, Any],
    session_id: str,
    session_idx: int,
    msg_idx: int,
) -> None:
    prefix = f"sessions[{session_idx}].messages[{msg_idx}]"
    _require_uuid(data.get("id"), f"{prefix}.id")
    if data.get("session_id") != session_id:
        raise ChronicleArchiveError(f"{prefix}.session_id mismatch.")
    try:
        MessageRole(str(data.get("role")).lower())
        MessageType(str(data.get("message_type")).lower())
    except ValueError as exc:
        raise ChronicleArchiveError(f"{prefix} role/type is invalid.") from exc
    _require_text(data.get("speaker"), f"{prefix}.speaker")
    if not isinstance(data.get("content"), str):
        raise ChronicleArchiveError(f"{prefix}.content must be a string.")


def _validate_save_slot(
    data: dict[str, Any],
    session_id: str,
    session_idx: int,
    save_idx: int,
) -> None:
    prefix = f"sessions[{session_idx}].save_slots[{save_idx}]"
    _require_uuid(data.get("id"), f"{prefix}.id")
    if data.get("session_id") != session_id:
        raise ChronicleArchiveError(f"{prefix}.session_id mismatch.")
    _require_text(data.get("name"), f"{prefix}.name")
    _coerce_session_status(data.get("phase"), f"{prefix}.phase")
    migrate_state_data(data.get("state_data") or {})
    if not isinstance(data.get("characters_snapshot") or [], list):
        raise ChronicleArchiveError(f"{prefix}.characters_snapshot must be a list.")


def _validate_dossier(data: Any, campaign_id: str) -> dict[str, Any] | None:
    if data is None:
        return None
    if not isinstance(data, dict):
        raise ChronicleArchiveError("dossier must be an object or null.")
    _require_uuid(data.get("id"), "dossier.id")
    if data.get("campaign_id") != campaign_id:
        raise ChronicleArchiveError("dossier.campaign_id mismatch.")
    return data


def _archive_ids(archive: dict[str, Any]) -> dict[str, list[str]]:
    ids = {
        "campaigns": [archive["campaign"]["id"]],
        "dossiers": [],
        "sessions": [],
        "game_states": [],
        "characters": [],
        "messages": [],
        "save_slots": [],
    }
    dossier = archive.get("dossier")
    if isinstance(dossier, dict):
        ids["dossiers"].append(dossier["id"])
    for bundle in archive["sessions"]:
        ids["sessions"].append(bundle["session"]["id"])
        if bundle.get("game_state"):
            ids["game_states"].append(bundle["game_state"]["id"])
        ids["characters"].extend(item["id"] for item in bundle.get("characters", []))
        ids["messages"].extend(item["id"] for item in bundle.get("messages", []))
        ids["save_slots"].extend(item["id"] for item in bundle.get("save_slots", []))
    return ids


def _active_session_id(campaign: Campaign) -> str | None:
    ids = list(campaign.session_ids or [])
    if not ids:
        return None
    index = max(0, min(int(campaign.current_session_index or 0), len(ids) - 1))
    return ids[index]


def _list_of_dicts(value: Any, label: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ChronicleArchiveError(f"{label} must be a list of objects.")
    return value


def _string_list(value: Any, label: str) -> list[str]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ChronicleArchiveError(f"{label} must be a list of strings.")
    return value


def _require_uuid(value: Any, label: str) -> str:
    text = str(value or "").strip()
    try:
        uuid.UUID(text)
    except ValueError as exc:
        raise ChronicleArchiveError(f"{label} must be a UUID.") from exc
    return text


def _require_text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ChronicleArchiveError(f"{label} must be a non-empty string.")
    return value


def _coerce_session_status(value: Any, label: str) -> SessionStatus:
    try:
        return SessionStatus(str(value).lower())
    except ValueError as exc:
        raise ChronicleArchiveError(f"{label} is not a valid session phase.") from exc


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip():
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            parsed = datetime.utcnow()
    else:
        parsed = datetime.utcnow()
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(UTC).replace(tzinfo=None)
    return parsed


def _now_iso() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _is_nonportable_url(url: str) -> bool:
    parsed = urlparse(url)
    if parsed.scheme in {"file", ""}:
        return True
    host = (parsed.hostname or "").casefold()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"} or host.endswith(".local")
