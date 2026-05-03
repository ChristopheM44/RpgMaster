"""Encounter-intro helpers for the game WebSocket facade."""
from __future__ import annotations

import inspect
import logging
import re
from collections.abc import Awaitable
from typing import Any, Callable, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.schemas import GMResponse
from app.game.event_bus import EventType
from app.game.gm_response_executor import GMResponseExecutor
from app.models.session import SessionStatus

logger = logging.getLogger(__name__)

_ENCOUNTER_PAUSE_MARKERS = (
    "pas un pas",
    "recule",
    "halte",
    "ne bougez",
    "rendez",
    "posez vos armes",
    "pose tes armes",
    "sommation",
    "menace",
    "a nous",
    "à nous",
    "que faites-vous",
    "que faites vous",
)

_IMMEDIATE_ATTACK_MARKERS = (
    "attaquent",
    "attaque aussitot",
    "attaque aussitôt",
    "chargent",
    "fondent sur",
    "se ruent",
    "tirent",
    "frappent",
)


def encounter_intro_combatants(combatants_info: dict[str, Any]) -> list[dict[str, Any]]:
    """Compact enemy snapshot for the encounter-intro prompt."""
    enemies: list[dict[str, Any]] = []
    for combatant_id, info in combatants_info.items():
        if info.get("is_player", False):
            continue
        enemies.append({
            "id": combatant_id,
            "name": info.get("name", combatant_id),
            "hp": info.get("hp"),
            "hp_max": info.get("hp_max"),
            "monster_id": info.get("monster_id"),
            "species": info.get("species"),
            "cr": info.get("cr"),
        })
    return enemies


def is_unhelpful_intro(text: Optional[str]) -> bool:
    if not text or not text.strip():
        return True
    lowered = text.casefold()
    return "temporairement indisponible" in lowered or "systeme llm" in lowered


def is_async_callable(candidate: Any) -> bool:
    if inspect.iscoroutinefunction(candidate):
        return True
    candidate_type = type(candidate)
    return (
        candidate_type.__module__ == "unittest.mock"
        and candidate_type.__name__ == "AsyncMock"
    )


async def generate_encounter_intro(
    session_id: str,
    active: Any,
    db: AsyncSession,
    combatants_info: dict[str, Any],
    *,
    gm_agent: Any,
    event_bus: Any,
    load_recent_messages: Callable[[str, AsyncSession], Awaitable[list[Any]]],
    source: str = "ws_game",
) -> Optional[str]:
    """Ask the GM for a one-shot cinematic encounter intro when available."""
    run_intro = getattr(gm_agent, "run_encounter_intro", None)
    if not callable(run_intro) or not is_async_callable(run_intro):
        return None

    response: Any = None
    await event_bus.publish_to_session(
        session_id,
        EventType.AI_THINKING,
        {"agent_kind": "gm", "thinking": True},
        source=source,
    )
    try:
        recent_messages = await load_recent_messages(session_id, db)
        response = await run_intro(
            game_state={**active.state_data, "phase": SessionStatus.ENCOUNTER_START.value},
            combatants=encounter_intro_combatants(combatants_info),
            messages=recent_messages,
        )
    except Exception as exc:
        logger.warning("generate_encounter_intro: intro LLM ignoree : %s", exc)
        return None
    finally:
        await event_bus.publish_to_session(
            session_id,
            EventType.AI_THINKING,
            {"agent_kind": "gm", "thinking": False},
            source=source,
        )

    await execute_intro_scene_layout(session_id, active, response, event_bus=event_bus)
    narration = getattr(response, "narration", "")
    if is_unhelpful_intro(narration):
        return None
    start_mode = str(getattr(response, "start_mode", "") or "").strip().lower()
    if start_mode in {"pause", "combat"}:
        active.state_data["_encounter_intro_start_mode"] = start_mode
    return str(narration).strip()


async def execute_intro_scene_layout(
    session_id: str,
    active: Any,
    response: Any,
    *,
    event_bus: Any,
    source: str = "ws_game",
) -> None:
    scene_actions = [
        action
        for action in getattr(response, "actions", []) or []
        if getattr(action, "type", "") == "scene_layout"
    ]
    if not scene_actions:
        return

    scene_response = GMResponse(narration="", actions=scene_actions[:1])
    await GMResponseExecutor(event_bus, source=source).execute_gm_response(
        scene_response,
        active,
        session_id=session_id,
    )


def normalized_phrase(text: Optional[str]) -> str:
    if not text:
        return ""
    normalized = text.casefold().replace("’", "'")
    return re.sub(r"\s+", " ", normalized)


def should_pause_for_encounter_intro(text: Optional[str]) -> bool:
    """Return True when the intro reads like a threat/sommation, not an attack."""
    normalized = normalized_phrase(text)
    if not normalized:
        return False
    if any(marker in normalized for marker in _IMMEDIATE_ATTACK_MARKERS):
        return False
    return (
        any(marker in normalized for marker in _ENCOUNTER_PAUSE_MARKERS)
        or "«" in normalized
        or '"' in normalized
    )


async def pause_at_encounter_start(
    session_id: str,
    active: Any,
    db: AsyncSession,
    pending: dict[str, Any] | None,
    intro_text: str,
    *,
    session_manager: Any,
    event_bus: Any,
    session_state_payload: Callable[[], dict[str, Any]],
    persist_narration: Callable[[str, str, str, AsyncSession], Awaitable[Any]],
    source: str = "ws_game",
) -> None:
    """Publish a roleplay encounter opening without rolling initiative yet."""
    active.turn_manager.reset()
    active.state_data.pop("combatants", None)
    active.state_data.pop("grid_positions", None)
    active.state_data.pop("grid_config", None)
    active.state_data.pop("grid_decoration", None)

    pending_encounter = dict(pending or {})
    pending_encounter["intro_played"] = True
    pending_encounter["intro_text"] = intro_text
    active.state_data["pending_encounter"] = pending_encounter
    active.phase = SessionStatus.ENCOUNTER_START
    active.state_data["phase"] = SessionStatus.ENCOUNTER_START.value
    active.mark_dirty()
    await session_manager.save_state(session_id, db)

    await event_bus.publish_to_session(
        session_id,
        EventType.PHASE_CHANGE,
        {"phase": SessionStatus.ENCOUNTER_START.value},
        source=source,
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.SESSION_STATE,
        session_state_payload(),
        source=source,
    )
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {"text": intro_text, "speaker": "Maître du Jeu"},
        source=source,
    )
    await persist_narration(session_id, intro_text, "Maître du Jeu", db)
