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

_SCENE_INTERACTION_INTENTS = {
    "approach",
    "talk",
    "examine",
    "listen",
    "search",
    "use",
    "custom",
}

_MAGIC_CLUE_MARKERS = (
    "abyssal",
    "arcane",
    "azur",
    "energie",
    "énergie",
    "faille",
    "fissure",
    "luminescent",
    "lueur",
    "magie",
    "magique",
    "ozone",
    "rituel",
    "rune",
    "siphon",
    "soufre",
    "vortex",
)

_HIDDEN_CLUE_MARKERS = (
    "cache",
    "caché",
    "dissimul",
    "indice",
    "mecanisme",
    "mécanisme",
    "piege",
    "piège",
    "secret",
    "serrure",
    "trace",
)

_DANGEROUS_INTERACTION_MARKERS = (
    "brule",
    "brûle",
    "chaud",
    "corros",
    "electr",
    "électr",
    "instable",
    "luminescent",
    "ozone",
    "siphon",
    "soufre",
    "vibr",
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
                    f"J'observe {npc_name} avec perspicacité pour jauger son état et sa sincérité."
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
                    str(exit_data.get(key) or "") for key in ("label", "leads_to", "description")
                )
        for poi in scene.get("pois", []) or []:
            if isinstance(poi, dict):
                sources.extend(
                    str(poi.get(key) or "") for key in ("name", "description", "action_hint")
                )
    return sources


def enrich_scene_poi_mechanics(scene: dict[str, Any]) -> None:
    """Ajoute des mécaniques conservatrices aux interactions POI à enjeu clair."""
    for poi in scene.get("pois", []) or []:
        if not isinstance(poi, dict):
            continue
        interactions = poi.get("interactions")
        if not isinstance(interactions, list):
            continue
        for interaction in interactions:
            if not isinstance(interaction, dict):
                continue
            mechanics = infer_poi_interaction_mechanics(
                poi,
                str(interaction.get("intent") or "custom"),
                interaction,
            )
            if mechanics:
                interaction["mechanics"] = mechanics


def resolve_scene_interaction_context(
    active: ActiveSession,
    *,
    poi_id: str | None,
    interaction_id: str | None,
    interaction_intent: str | None,
) -> dict[str, Any] | None:
    """Retrouve l'interaction de scène côté backend et infère ses mécaniques."""
    if not poi_id:
        return None
    scene = active.state_data.get("current_scene")
    if not isinstance(scene, dict):
        return None
    poi = _find_poi(scene, poi_id)
    if not poi:
        return None
    interaction = _find_poi_interaction(poi, interaction_id, interaction_intent)
    intent = (
        str((interaction or {}).get("intent") or interaction_intent or "custom").strip().lower()
    )
    if intent not in _SCENE_INTERACTION_INTENTS:
        intent = "custom"
    mechanics = infer_poi_interaction_mechanics(poi, intent, interaction)
    return {
        "poi_id": str(poi.get("id") or poi_id),
        "poi_name": str(poi.get("name") or poi_id),
        "interaction_id": str((interaction or {}).get("id") or interaction_id or intent),
        "interaction_label": str((interaction or {}).get("label") or intent),
        "interaction_intent": intent,
        "mechanics": mechanics or {},
    }


def infer_poi_interaction_mechanics(
    poi: dict[str, Any],
    intent: str,
    interaction: dict[str, Any] | None = None,
) -> dict[str, Any]:
    explicit = interaction.get("mechanics") if isinstance(interaction, dict) else None
    if isinstance(explicit, dict):
        return _normalize_poi_mechanics(explicit)

    text = _poi_text(poi)
    kind = normalize_text(str(poi.get("kind") or ""))
    normalized_intent = normalize_text(intent)
    if normalized_intent in {"talk", "approach"}:
        return {}

    safe_observation = normalized_intent in {"examine", "listen", "search"}
    mechanics: dict[str, Any] = {"safe_observation": safe_observation}

    is_dangerous = kind == "hazard" or _contains_any(text, _DANGEROUS_INTERACTION_MARKERS)
    if is_dangerous and normalized_intent in {"use", "custom"}:
        mechanics["safe_observation"] = False
        mechanics["roll"] = {
            "type": "save",
            "ability": "dex",
            "skill": "Acrobatics",
            "dc": 14,
            "reason": "scene_poi_hazard",
        }
        mechanics["reveal_tier"] = "surface"
        return mechanics

    if _contains_any(text, _MAGIC_CLUE_MARKERS):
        mechanics["roll"] = {
            "type": "check",
            "ability": "int",
            "skill": "Arcana",
            "dc": 12,
            "reason": "scene_poi_magic",
        }
        mechanics["reveal_tier"] = "interpreted"
        return mechanics

    if is_dangerous and normalized_intent in {"examine", "search"}:
        mechanics["roll"] = {
            "type": "check",
            "ability": "int",
            "skill": "Investigation",
            "dc": 13,
            "reason": "scene_poi_hazard_observation",
        }
        mechanics["reveal_tier"] = "interpreted"
        return mechanics

    if _contains_any(text, _HIDDEN_CLUE_MARKERS) or normalized_intent == "search":
        mechanics["roll"] = {
            "type": "check",
            "ability": "int",
            "skill": "Investigation",
            "dc": 14,
            "reason": "scene_poi_search",
        }
        mechanics["reveal_tier"] = "interpreted"
        return mechanics

    return {}


def _find_poi(scene: dict[str, Any], poi_id: str) -> dict[str, Any] | None:
    for poi in scene.get("pois", []) or []:
        if isinstance(poi, dict) and str(poi.get("id") or "") == str(poi_id):
            return poi
    return None


def _find_poi_interaction(
    poi: dict[str, Any],
    interaction_id: str | None,
    interaction_intent: str | None,
) -> dict[str, Any] | None:
    interactions = poi.get("interactions")
    if not isinstance(interactions, list):
        return None
    if interaction_id:
        for interaction in interactions:
            if isinstance(interaction, dict) and str(interaction.get("id") or "") == str(
                interaction_id
            ):
                return interaction
    if interaction_intent:
        normalized_intent = normalize_text(interaction_intent)
        for interaction in interactions:
            if (
                isinstance(interaction, dict)
                and normalize_text(str(interaction.get("intent") or "")) == normalized_intent
            ):
                return interaction
    return None


def _normalize_poi_mechanics(value: dict[str, Any]) -> dict[str, Any]:
    mechanics: dict[str, Any] = {}
    roll = _normalize_roll_params(value.get("roll"))
    if roll:
        mechanics["roll"] = roll
    if isinstance(value.get("safe_observation"), bool):
        mechanics["safe_observation"] = value["safe_observation"]
    reveal_tier = str(value.get("reveal_tier") or "").strip().lower()
    if reveal_tier in {"surface", "interpreted", "deep"}:
        mechanics["reveal_tier"] = reveal_tier
    return mechanics


def _normalize_roll_params(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    ability = str(value.get("ability") or "").strip().lower()[:3]
    if ability not in {"str", "dex", "con", "int", "wis", "cha"}:
        return None
    roll_type = str(value.get("type") or "check").strip().lower()
    if value.get("save") is True:
        roll_type = "save"
    if roll_type not in {"check", "save"}:
        roll_type = "check"
    try:
        dc = int(value.get("dc") or 12)
    except (TypeError, ValueError):
        dc = 12
    normalized = {
        "type": roll_type,
        "ability": ability,
        "dc": max(5, min(dc, 30)),
    }
    skill = str(value.get("skill") or "").strip()
    if skill:
        normalized["skill"] = skill[:40]
    reason = str(value.get("reason") or "").strip()
    if reason:
        normalized["reason"] = reason[:80]
    return normalized


def _poi_text(poi: dict[str, Any]) -> str:
    return normalize_text(
        " ".join(
            str(poi.get(key) or "")
            for key in ("name", "kind", "description", "action_hint", "icon")
        )
    )


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    normalized = normalize_text(text)
    return any(normalize_text(marker) in normalized for marker in markers)


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
        "on_fill": _default_clock_on_fill(label),
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
) -> list[dict[str, Any]]:
    clocks = _clock_list(active, create=False)
    if not clocks:
        return []
    changed = False
    newly_filled: list[dict[str, Any]] = []
    for clock in clocks:
        status = str(clock.get("status") or "active")
        if status == "filled":
            clock["status"] = "resolving"
            newly_filled.append(clock)
            changed = True
            await event_bus.publish_to_session(
                session_id,
                EventType.CLOCK_UPDATED,
                dict(clock),
                source=source,
            )
            continue
        if status != "active":
            continue
        if str(clock.get("tick_on") or "player_action") != "player_action":
            continue
        maximum = max(1, int(clock.get("max") or 4))
        current = min(maximum, int(clock.get("current") or 0) + 1)
        if current == clock.get("current"):
            continue
        clock["current"] = current
        if current >= maximum:
            clock["status"] = "resolving"
            newly_filled.append(clock)
        changed = True
        await event_bus.publish_to_session(
            session_id,
            EventType.CLOCK_UPDATED,
            dict(clock),
            source=source,
        )
    if changed:
        active.mark_dirty()
    return newly_filled


async def resolve_scene_clock_crises(
    *,
    session_id: str,
    active: ActiveSession,
    event_bus: Any,
    clocks: list[dict[str, Any]],
    actor_id: str | None,
    db: Any | None = None,
    source: str,
) -> list[dict[str, Any]]:
    resolved: list[dict[str, Any]] = []
    for clock in clocks:
        if str(clock.get("status") or "") != "resolving":
            continue
        if clock.get("resolved_at_turn") is not None:
            continue
        on_fill = _normalize_clock_on_fill(clock.get("on_fill"), str(clock.get("label") or ""))
        mode = str(on_fill.get("mode") or "roll")
        narration = str(on_fill.get("narration") or _default_clock_crisis_text(clock)).strip()
        if narration:
            await _publish_clock_narration(session_id, event_bus, narration, db, source)

        roll_payload: dict[str, Any] | None = None
        if mode == "roll":
            roll_payload = _execute_clock_roll(on_fill.get("roll"), active, actor_id)
            if roll_payload:
                roll_payload["clock_id"] = clock.get("id")
                roll_payload["clock_label"] = clock.get("label")
                await event_bus.publish_to_session(
                    session_id,
                    EventType.ROLL_RESULT,
                    roll_payload,
                    source=source,
                )
                if db is not None:
                    from app.services.message_service import persist_roll_result

                    await persist_roll_result(session_id, roll_payload, db)
                outcome = _clock_roll_outcome_text(clock, roll_payload)
                await _publish_clock_narration(session_id, event_bus, outcome, db, source)

        next_clock = on_fill.get("next_clock")
        clock["status"] = "resolved"
        clock["resolved_at_turn"] = active.turn_number
        if roll_payload:
            clock["resolution"] = {
                "success": roll_payload.get("success"),
                "total": roll_payload.get("total"),
                "dc": roll_payload.get("dc"),
            }
        active.mark_dirty()
        await event_bus.publish_to_session(
            session_id,
            EventType.CLOCK_UPDATED,
            dict(clock),
            source=source,
        )
        resolved.append(clock)
        if isinstance(next_clock, dict):
            await start_scene_clock(
                session_id=session_id,
                active=active,
                event_bus=event_bus,
                params=next_clock,
                source=source,
            )
    return resolved


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
    if status not in {"active", "paused", "filled", "resolving", "resolved"}:
        status = "active"
    clock = {
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
    on_fill = (
        _normalize_clock_on_fill(params.get("on_fill"), label)
        if isinstance(params.get("on_fill"), dict)
        else None
    )
    if on_fill:
        clock["on_fill"] = on_fill
    return clock


def _default_clock_on_fill(label: str) -> dict[str, Any]:
    # On NE pré-cuit PAS la narration : elle est (re)calculée à la résolution avec
    # l'horloge complète (label + severity) via _default_clock_crisis_text, pour
    # rester un phénomène concret sans figer un texte partiel à la création.
    return {
        "mode": "roll",
        "roll": {
            "type": "save",
            "ability": "dex",
            "skill": "Acrobatics",
            "dc": 14,
            "reason": "scene_clock_crisis",
        },
    }


def _normalize_clock_on_fill(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        return _default_clock_on_fill(label)
    mode = str(value.get("mode") or "roll").strip().lower()
    if mode not in {"roll", "narrative", "transition"}:
        mode = "roll"
    normalized: dict[str, Any] = {"mode": mode}
    roll = _normalize_roll_params(value.get("roll"))
    if roll:
        normalized["roll"] = roll
    elif mode == "roll":
        normalized["roll"] = _default_clock_on_fill(label)["roll"]
    # Narration custom du MJ respectée si fournie ; sinon laissée vide pour que la
    # résolution retombe sur le fallback déterministe concret (cf. _default_clock_on_fill).
    narration = str(value.get("narration") or "").strip()
    if narration:
        normalized["narration"] = narration[:600]
    next_clock = value.get("next_clock")
    if isinstance(next_clock, dict):
        normalized["next_clock"] = next_clock
    return normalized


def _execute_clock_roll(
    roll: Any,
    active: ActiveSession,
    actor_id: str | None,
) -> dict[str, Any] | None:
    roll_params = _normalize_roll_params(roll)
    if not roll_params:
        return None
    from app.game.roll_executor import execute_roll_request

    payload = execute_roll_request(roll_params, actor_id, active)
    if not payload:
        return None
    success_label = "réussite" if payload.get("success") else "échec"
    label = str(payload.get("label") or "Jet de sauvegarde")
    payload.setdefault(
        "summary",
        f"{label} : {payload.get('total')} vs DD {payload.get('dc')} ({success_label})",
    )
    return payload


# Classes de menace inférées depuis le label d'horloge (interne). Le label sert
# UNIQUEMENT à choisir un phénomène physique concret ; il n'est jamais rendu tel
# quel dans la narration joueur (il ne vit que dans le badge UI).
_CLOCK_THREAT_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("dock", ("dock", "quai", "entrepot", "amarre", "pilotis", "ponton", "embarcad")),
    ("fire", ("incendie", "flamme", "feu", "brasier", "fournaise", "fumee")),
    ("ritual", ("rituel", "rune", "arcane", "incantation", "invocation", "sceau", "siphon")),
    ("flood", ("inondation", "submersion", "maree", "crue", "vague", "noyade", "deluge")),
    ("collapse", ("effondrement", "plafond", "voute", "galerie", "eboulement", "structure")),
    ("pursuit", ("poursuite", "garde", "patrouille", "alerte", "traque", "renfort")),
    ("explosion", ("explosion", "bombe", "baril", "poudre", "detonation", "charge")),
)

# Phénomène physique concret au moment où la menace se déchaîne (aucun acteur, on
# décrit le monde ; jamais le label ni un placeholder "personnage exposé").
_CLOCK_CRISIS_BY_KIND: dict[str, str] = {
    "dock": (
        "Les amarres cèdent l'une après l'autre dans un fracas de bois, et une portion "
        "du pilotis s'affaisse vers l'eau noire."
    ),
    "fire": (
        "Les flammes franchissent la dernière cloison d'un seul élan ; une vague de "
        "chaleur et une fumée âcre engloutissent l'espace."
    ),
    "ritual": (
        "Les runes virent à l'écarlate et l'air se met à vibrer d'une pression sourde, "
        "prêt à se déchirer d'un instant à l'autre."
    ),
    "flood": (
        "L'eau s'engouffre d'un coup, noire et glacée, et le niveau grimpe à hauteur de "
        "cuisse en quelques secondes."
    ),
    "collapse": (
        "Une fissure court au plafond dans un grondement profond ; des blocs de pierre "
        "commencent à pleuvoir."
    ),
    "pursuit": (
        "Des cris et un martèlement de bottes convergent de toutes parts : l'étau vient "
        "de se refermer."
    ),
    "explosion": (
        "Une onde de chaleur précède le grondement : la déflagration est sur le point de "
        "tout balayer."
    ),
    "generic": (
        "La tension se rompt d'un coup ; tout bascule autour dans un danger immédiat et "
        "bien physique."
    ),
}

# Conséquences concrètes par classe de menace. Le succès "coûte" toujours quelque
# chose (pas de simple esquive sans effet) ; l'échec aggrave la position.
# Clauses rédigées au présent / en « se fait + infinitif », sans pronom « il » ni
# participe s'accordant au sujet, pour rester justes quel que soit le genre du PC
# (« Aria », « Bram »…). Les participes présents (« noyés », « brisé », « coupé »,
# « bouchée ») s'accordent à leur propre substantif, jamais au personnage.
_CLOCK_OUTCOME_BY_KIND: dict[str, dict[str, str]] = {
    "dock": {
        "success": (
            "se jette hors de la section qui s'effondre et retombe sur une planche encore "
            "solide — au prix d'un genou ouvert et d'un paquetage à moitié noyé."
        ),
        "fail": (
            "bascule avec la section qui cède et s'enfonce jusqu'à la taille dans l'eau "
            "noire et le bois brisé ; sa position devient franchement périlleuse."
        ),
    },
    "fire": {
        "success": (
            "traverse le rideau de flammes d'un bond et s'en sort — manche roussie, "
            "poumons brûlants de fumée."
        ),
        "fail": (
            "se fait rattraper par les flammes, vêtements fumants et souffle court ; le "
            "passage derrière n'est plus qu'un mur de feu."
        ),
    },
    "ritual": {
        "success": (
            "détourne la décharge au dernier instant, mais l'onde lui laisse les oreilles "
            "sifflantes et la peau marquée d'un givre arcanique."
        ),
        "fail": (
            "encaisse la décharge de plein fouet, bascule au sol, les sens noyés sous une "
            "lumière mordante ; le rituel, lui, a fini sa course."
        ),
    },
    "flood": {
        "success": (
            "s'agrippe à une saillie et garde la tête hors de l'eau — au prix d'un bain "
            "glacé et d'une partie du matériel emportée par le courant."
        ),
        "fail": (
            "se fait happer par la crue et rouler contre la paroi, reprend pied en "
            "grelottant, l'eau désormais à hauteur de poitrine."
        ),
    },
    "collapse": {
        "success": (
            "plonge à couvert juste avant l'éboulement et s'en tire avec une épaule "
            "contusionnée sous la poussière et les gravats."
        ),
        "fail": (
            "disparaît à demi sous la chute de pierres et doit s'arracher des décombres ; "
            "l'issue, derrière, est maintenant bouchée."
        ),
    },
    "pursuit": {
        "success": (
            "se faufile hors de l'étau au dernier moment — mais on a vu son visage, et "
            "l'alerte court déjà devant."
        ),
        "fail": (
            "se fait rattraper et plaquer contre le mur, se dégage de justesse, mais la "
            "traque sait désormais exactement où chercher."
        ),
    },
    "explosion": {
        "success": (
            "se jette derrière un abri à l'instant du souffle — tympans bourdonnants, une "
            "coupure chaude à la tempe."
        ),
        "fail": (
            "se fait cueillir par la déflagration et jeter plusieurs mètres en arrière, le "
            "souffle coupé, au milieu d'un décor en ruine."
        ),
    },
    "generic": {
        "success": (
            "réagit juste à temps et garde l'équilibre — non sans récolter une mauvaise "
            "contusion dans la bousculade."
        ),
        "fail": (
            "encaisse le choc de plein fouet, se relève tant bien que mal, mais la "
            "situation alentour a nettement empiré."
        ),
    },
}


def _clock_threat_kind(label: str) -> str:
    normalized = normalize_text(label)
    for kind, markers in _CLOCK_THREAT_KEYWORDS:
        if any(marker in normalized for marker in markers):
            return kind
    return "generic"


def _default_clock_crisis_text(clock: dict[str, Any]) -> str:
    kind = _clock_threat_kind(str(clock.get("label") or ""))
    text = _CLOCK_CRISIS_BY_KIND.get(kind, _CLOCK_CRISIS_BY_KIND["generic"])
    if normalize_text(str(clock.get("severity") or "")) == "critical":
        text = f"{text} Il n'y a plus une seconde à perdre."
    return text


def _clock_roll_outcome_text(clock: dict[str, Any], roll_payload: dict[str, Any]) -> str:
    name = str(roll_payload.get("character_name") or "Le personnage").strip() or "Le personnage"
    kind = _clock_threat_kind(str(clock.get("label") or ""))
    outcome = _CLOCK_OUTCOME_BY_KIND.get(kind, _CLOCK_OUTCOME_BY_KIND["generic"])
    clause = outcome["success" if roll_payload.get("success") else "fail"]
    return f"{name} {clause}"


async def _publish_clock_narration(
    session_id: str,
    event_bus: Any,
    text: str,
    db: Any | None,
    source: str,
) -> None:
    await event_bus.publish_to_session(
        session_id,
        EventType.NARRATION,
        {
            "text": text,
            "speaker": "Maître du Jeu",
            "speaker_kind": "gm",
            "entry_kind": "narration",
        },
        source=source,
    )
    if db is not None:
        from app.services.message_service import persist_narration

        await persist_narration(session_id, text, "Maître du Jeu", db)


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
