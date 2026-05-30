"""Deterministic social scene memory and optional scene clocks."""
from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.game.event_bus import EventType
from app.game.session_manager import ActiveSession
from app.game.social_resolution import ATTITUDE_ORDER, SocialResolution

_GENERIC_TALK_MARKERS = (
    "adresse la parole",
    "adresser la parole",
    "m avance vers",
    "m'approche de",
    "je parle",
    "parler",
    "salut",
    "bonjour",
)

_MODERN_WEAPON_MARKERS = (
    "ak47",
    "ak-47",
    "bazooka",
    "bazouka",
    "bombe",
    "c4",
    "dynamite",
    "fusil d'assaut",
    "grenade",
    "kalachnikov",
    "lance roquette",
    "lance-roquette",
    "mitrailleuse",
    "pistolet",
    "revolver",
    "roquette",
)

_HOSTILE_MARKERS = (
    "abat",
    "attaque",
    "explose",
    "frappe",
    "lance",
    "tire",
    "tuer",
    "tue",
    "viser",
)

_CLOCK_TRIGGER_PATTERNS = (
    r"\btoutes?\s+les\s+(?:\d+|[a-z]+)\s+(?:secondes?|minutes?|heures?)\b",
    r"\b(?:vibration|bourdonnement)\s+(?:reguliere?|periodique|a intervalle)\b",
    r"\bavant\s+(?:midi|minuit|l'aube|la nuit|le soir|le lever|le coucher)\b",
    r"\bcompte\s*[àa]\s*rebours\b",
    r"\b\d+\s+(?:secondes?|minutes?|heures?)\s+avant\b",
    r"\b(?:rituel|incendie|bombe|explosion|poursuite|fuite)\b",
)


def normalize_text(value: str | None) -> str:
    text = unicodedata.normalize("NFD", value or "")
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", text.casefold()).strip()


def ensure_dialogue_state(active: ActiveSession, npc_id: str) -> dict[str, Any]:
    npc_states = active.state_data.setdefault("npc_states", {})
    if not isinstance(npc_states, dict):
        npc_states = {}
        active.state_data["npc_states"] = npc_states
    npc = npc_states.setdefault(npc_id, {})
    if not isinstance(npc, dict):
        npc = {}
        npc_states[npc_id] = npc
    state = npc.setdefault("dialogue_state", {})
    if not isinstance(state, dict):
        state = {}
        npc["dialogue_state"] = state
    state.setdefault("stage", "unmet")
    state.setdefault("talk_count", 0)
    state.setdefault("generic_repeat_count", 0)
    state.setdefault("patience", 3)
    state.setdefault("revealed_keys", [])
    state.setdefault("last_player_intent", None)
    return state


def is_generic_npc_talk(text: str | None) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    if "?" in (text or ""):
        return False
    return any(marker in normalized for marker in _GENERIC_TALK_MARKERS)


def prepare_npc_dialogue_state(active: ActiveSession, npc_id: str, player_text: str | None) -> None:
    state = ensure_dialogue_state(active, npc_id)
    stage = str(state.get("stage") or "unmet")
    generic = is_generic_npc_talk(player_text)
    state["talk_count"] = int(state.get("talk_count") or 0) + 1
    state["last_player_intent"] = "generic_talk" if generic else "specific_message"
    if stage == "unmet":
        state["stage"] = "greeted"
    elif generic and stage in {"briefing_given", "dismissed", "angered"}:
        state["generic_repeat_count"] = int(state.get("generic_repeat_count") or 0) + 1
        state["patience"] = max(0, int(state.get("patience") or 0) - 1)
    active.mark_dirty()


def finalize_npc_dialogue_state(
    active: ActiveSession,
    npc_id: str,
    player_text: str | None,
) -> None:
    state = ensure_dialogue_state(active, npc_id)
    generic = is_generic_npc_talk(player_text)
    if generic and state.get("stage") in {"unmet", "greeted"}:
        state["stage"] = "briefing_given"
    if int(state.get("generic_repeat_count") or 0) >= 2 and state.get("stage") != "angered":
        state["stage"] = "dismissed"
    state["last_interaction_turn"] = active.state_data.get("turn_number", 0)
    apply_contextual_npc_interactions(active, npc_id)
    active.mark_dirty()


def apply_contextual_npc_interactions(active: ActiveSession, npc_id: str) -> None:
    scene = active.state_data.get("current_scene")
    if not isinstance(scene, dict):
        return
    npc = active.state_data.get("npc_states", {}).get(npc_id, {})
    npc_name = str(npc.get("name") or npc_id) if isinstance(npc, dict) else npc_id
    destination_label = _destination_label(active)
    for poi in scene.get("pois", []) or []:
        if not isinstance(poi, dict) or str(poi.get("id") or "") != npc_id:
            continue
        poi["interactions"] = [
            {
                "id": "ask_details",
                "label": "Demander des précisions",
                "intent": "talk",
                "prompt": (
                    f"Je demande à {npc_name} des précisions utiles, "
                    "sans lui faire répéter tout le briefing."
                ),
                "icon": "clue",
            },
            {
                "id": "read_attitude",
                "label": "Jauger le PNJ",
                "intent": "talk",
                "prompt": (
                    f"J'observe {npc_name} avec perspicacité pour jauger "
                    "son état et sa sincérité."
                ),
                "icon": "clue",
            },
            {
                "id": "ask_support",
                "label": "Demander de l'aide",
                "intent": "talk",
                "prompt": (
                    f"Je demande à {npc_name} s'il peut fournir une aide concrète "
                    "ou une avance pour cette mission."
                ),
                "icon": "chest",
            },
            {
                "id": "follow_objective",
                "label": destination_label,
                "intent": "custom",
                "prompt": _destination_prompt(destination_label, npc_name),
                "icon": "exit-dir",
            },
        ]
        return


def _destination_label(active: ActiveSession) -> str:
    text = " ".join(_state_text_sources(active))
    normalized = normalize_text(text)
    if "dock" in normalized or "quai" in normalized:
        return "Partir aux docks"
    if "entrepot" in normalized:
        return "Aller à l'entrepôt"
    return "Suivre l'objectif"


def _destination_prompt(label: str, npc_name: str) -> str:
    if "docks" in normalize_text(label):
        return f"Je prends congé de {npc_name} et me dirige vers les docks."
    if "entrepot" in normalize_text(label):
        return f"Je prends congé de {npc_name} et me dirige vers l'entrepôt indiqué."
    return f"Je prends congé de {npc_name} et me prépare à suivre l'objectif indiqué."


def _state_text_sources(active: ActiveSession) -> list[str]:
    sources: list[str] = []
    for quest in active.state_data.get("quests", []) or []:
        if isinstance(quest, dict):
            sources.extend(str(quest.get(key) or "") for key in ("title", "summary", "urgency"))
    scene = active.state_data.get("current_scene")
    if isinstance(scene, dict):
        sources.append(str(scene.get("description") or ""))
        for exit_data in scene.get("exits", []) or []:
            if isinstance(exit_data, dict):
                sources.extend(
                    str(exit_data.get(key) or "")
                    for key in ("label", "leads_to", "description")
                )
        for poi in scene.get("pois", []) or []:
            if isinstance(poi, dict):
                sources.extend(
                    str(poi.get(key) or "")
                    for key in ("name", "description", "action_hint")
                )
    return sources


def detect_impossible_hostile_action(
    text: str | None,
    active: ActiveSession | None = None,
    actor_id: str | None = None,
) -> str | None:
    normalized = normalize_text(text)
    if not normalized:
        return None
    weapon = next((marker for marker in _MODERN_WEAPON_MARKERS if marker in normalized), None)
    if not weapon:
        return None
    if _actor_or_campaign_has_item(active, actor_id, weapon):
        return None
    if not any(marker in normalized for marker in _HOSTILE_MARKERS):
        return None
    return weapon


def _actor_or_campaign_has_item(
    active: ActiveSession | None,
    actor_id: str | None,
    weapon_marker: str,
) -> bool:
    if active is None:
        return False
    needle = normalize_text(weapon_marker).replace("-", " ")
    characters = active.state_data.get("characters")
    actor = characters.get(actor_id) if isinstance(characters, dict) and actor_id else None
    equipment = actor.get("equipment") if isinstance(actor, dict) else []
    if isinstance(equipment, list):
        for item in equipment:
            if not isinstance(item, dict):
                continue
            item_text = normalize_text(
                " ".join(str(item.get(key) or "") for key in ("id", "name", "name_fr"))
            ).replace("-", " ")
            if needle and needle in item_text:
                return True

    campaign_context = active.state_data.get("campaign_context")
    custom_items = campaign_context.get("items") if isinstance(campaign_context, dict) else []
    if isinstance(custom_items, list):
        for item in custom_items:
            if not isinstance(item, dict):
                continue
            item_text = normalize_text(
                " ".join(str(item.get(key) or "") for key in ("id", "name", "name_fr"))
            ).replace("-", " ")
            if needle and needle in item_text:
                return True
    return False


async def publish_impossible_hostile_action(
    *,
    session_id: str,
    active: ActiveSession,
    event_bus: Any,
    player_text: str,
    actor_id: str | None,
    npc_id: str | None,
    weapon_marker: str,
    db: Any | None = None,
) -> None:
    npc_name = _npc_name(active, npc_id) if npc_id else "la cible"
    text = (
        f"L'objet évoqué ({weapon_marker}) n'existe pas dans votre équipement ni dans "
        f"la réalité établie de cette scène. {npc_name} comprend toutefois l'intention "
        "hostile et se raidit aussitôt. Voulez-vous vraiment attaquer avec une arme "
        "que vous possédez réellement ?"
    )
    active.state_data["pending_clarification"] = {
        "type": "impossible_hostile_action",
        "actor_id": actor_id,
        "target_id": npc_id,
        "original_text": player_text,
        "message": text,
    }
    if npc_id:
        _apply_hostile_social_consequence(active, npc_id)
        await event_bus.publish_to_session(
            session_id,
            EventType.SOCIAL_OUTCOME,
            _social_payload(active, npc_id),
            source="narrative_flow",
        )
    active.mark_dirty()
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {
            "text": text,
            "speaker": "Maître du Jeu",
            "speaker_kind": "gm",
            "entry_kind": "narration",
        },
        source="narrative_flow",
    )
    if db is not None:
        from app.services.message_service import persist_narration

        await persist_narration(session_id, text, "Maître du Jeu", db)


def _apply_hostile_social_consequence(active: ActiveSession, npc_id: str) -> None:
    npc_states = active.state_data.setdefault("npc_states", {})
    npc = npc_states.setdefault(npc_id, {})
    if not isinstance(npc, dict):
        npc = {}
        npc_states[npc_id] = npc
    old = SocialResolution.normalize_attitude(npc.get("attitude", "indifferent"))
    old_index = ATTITUDE_ORDER.index(old)
    npc["attitude"] = ATTITUDE_ORDER[max(0, old_index - 1)]
    notes = list(npc.get("notes", []))
    notes.append("A perçu une intention hostile impossible ou anachronique.")
    npc["notes"] = notes
    dialogue_state = ensure_dialogue_state(active, npc_id)
    dialogue_state["stage"] = "angered"
    dialogue_state["patience"] = 0


def _social_payload(active: ActiveSession, npc_id: str) -> dict[str, Any]:
    npc = active.state_data.get("npc_states", {}).get(npc_id, {})
    previous = "indifferent"
    attitude = "indifferent"
    if isinstance(npc, dict):
        attitude = SocialResolution.normalize_attitude(npc.get("attitude"))
        previous = ATTITUDE_ORDER[min(ATTITUDE_ORDER.index(attitude) + 1, len(ATTITUDE_ORDER) - 1)]
    return {
        "npc_id": npc_id,
        "previous_attitude": previous,
        "attitude": attitude,
        "note": "Le PNJ se méfie après une intention hostile impossible.",
        "clamped": False,
        "source": "engine_impossible_action",
    }


def _npc_name(active: ActiveSession, npc_id: str | None) -> str:
    if not npc_id:
        return "La cible"
    npc = active.state_data.get("npc_states", {}).get(npc_id)
    if isinstance(npc, dict) and npc.get("name"):
        return str(npc["name"])
    scene = active.state_data.get("current_scene")
    if isinstance(scene, dict):
        for poi in scene.get("pois", []) or []:
            if isinstance(poi, dict) and str(poi.get("id") or "") == npc_id:
                return str(poi.get("name") or npc_id)
    return npc_id


def infer_clock_start_from_opening(
    response_text: str,
    active: ActiveSession,
) -> dict[str, Any] | None:
    if active.state_data.get("scene_clocks"):
        return None
    text = " ".join([response_text, *_state_text_sources(active)])
    normalized = normalize_text(text)
    if not normalized:
        return None
    if not any(re.search(pattern, normalized) for pattern in _CLOCK_TRIGGER_PATTERNS):
        return None
    label = "Menace imminente"
    if "dock" in normalized or "quai" in normalized or "entrepot" in normalized:
        label = "Menace aux docks"
    elif "rituel" in normalized:
        label = "Rituel en cours"
    elif "incendie" in normalized:
        label = "Incendie"
    return {
        "id": normalize_text(label).replace(" ", "_") or "scene_clock",
        "label": label,
        "scope": "scene",
        "current": 0,
        "max": 4,
        "severity": "high",
        "status": "active",
        "tick_on": "player_action",
    }


async def start_scene_clock(
    *,
    session_id: str,
    active: ActiveSession,
    event_bus: Any,
    params: dict[str, Any],
    source: str,
) -> dict[str, Any] | None:
    clock = normalize_clock(params)
    if clock is None:
        return None
    clocks = _clock_list(active)
    idx = next((i for i, item in enumerate(clocks) if item.get("id") == clock["id"]), -1)
    if idx >= 0:
        clocks[idx] = {**clocks[idx], **clock}
    else:
        clocks.append(clock)
    active.mark_dirty()
    await event_bus.publish_to_session(
        session_id,
        EventType.CLOCK_UPDATED,
        clock,
        source=source,
    )
    return clock


async def advance_scene_clocks(
    *,
    session_id: str,
    active: ActiveSession,
    event_bus: Any,
    source: str,
) -> None:
    clocks = _clock_list(active, create=False)
    if not clocks:
        return
    changed = False
    for clock in clocks:
        if str(clock.get("status") or "active") != "active":
            continue
        if str(clock.get("tick_on") or "player_action") != "player_action":
            continue
        maximum = max(1, int(clock.get("max") or 4))
        current = min(maximum, int(clock.get("current") or 0) + 1)
        if current == clock.get("current"):
            continue
        clock["current"] = current
        if current >= maximum:
            clock["status"] = "filled"
        changed = True
        await event_bus.publish_to_session(
            session_id,
            EventType.CLOCK_UPDATED,
            dict(clock),
            source=source,
        )
    if changed:
        active.mark_dirty()


def normalize_clock(params: dict[str, Any]) -> dict[str, Any] | None:
    label = str(params.get("label") or params.get("name") or "").strip()
    clock_id = str(params.get("id") or normalize_text(label).replace(" ", "_")).strip()
    if not clock_id or not label:
        return None
    try:
        maximum = int(params.get("max") or params.get("steps") or 4)
    except (TypeError, ValueError):
        maximum = 4
    try:
        current = int(params.get("current") or 0)
    except (TypeError, ValueError):
        current = 0
    maximum = max(1, min(maximum, 12))
    current = max(0, min(current, maximum))
    severity = str(params.get("severity") or "medium").strip().lower()
    if severity not in {"low", "medium", "high", "critical"}:
        severity = "medium"
    status = str(params.get("status") or "active").strip().lower()
    if status not in {"active", "paused", "filled", "resolved"}:
        status = "active"
    return {
        "id": clock_id[:80],
        "label": label[:120],
        "scope": str(params.get("scope") or "scene")[:40],
        "current": current,
        "max": maximum,
        "severity": severity,
        "status": status,
        "tick_on": str(params.get("tick_on") or "player_action")[:40],
        "linked_quest_id": params.get("linked_quest_id"),
    }


def _clock_list(active: ActiveSession, *, create: bool = True) -> list[dict[str, Any]]:
    clocks = active.state_data.get("scene_clocks")
    if isinstance(clocks, list):
        if any(not isinstance(clock, dict) for clock in clocks):
            clocks = [clock for clock in clocks if isinstance(clock, dict)]
            active.state_data["scene_clocks"] = clocks
        return clocks
    if create:
        clocks = []
        active.state_data["scene_clocks"] = clocks
        return clocks
    return []
