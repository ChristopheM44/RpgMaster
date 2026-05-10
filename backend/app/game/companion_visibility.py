"""Helpers for AI companion-facing state and visible prose.

Companions behave like player characters: they can state intent, words, and
voluntary gestures, but the GM owns world consequences and NPC reactions.
"""
from __future__ import annotations

from copy import deepcopy
import logging
import re
import unicodedata
from typing import Any, Optional

logger = logging.getLogger(__name__)

_VISIBLE_STATE_KEYS = (
    "phase",
    "characters",
    "current_scene",
    "adventure_journal",
    "quests",
    "chronicle",
    "npc_states",
    "combatants",
    "grid_positions",
    "grid_config",
)

_PLAYED_CANON_LIST_KEYS = (
    "established_facts",
    "player_decisions",
    "revealed_secrets",
)

_WORLD_SUBJECTS = (
    "le bois",
    "la table",
    "les tables",
    "la chaise",
    "le banc",
    "la porte",
    "le sol",
    "les murs",
    "la foule",
    "les clients",
    "les gens",
    "l aubergiste",
    "le garde",
    "la garde",
)

_WORLD_RESULTS = (
    "craque",
    "craquent",
    "cede",
    "cedent",
    "se fissure",
    "se fissurent",
    "se fend",
    "se fendent",
    "se brise",
    "se brisent",
    "eclate",
    "eclatent",
    "tremble",
    "tremblent",
    "reagit",
    "reagissent",
    "se tait",
    "se taisent",
)

_NPC_REACTION_RESULTS = (
    "accepte",
    "refuse",
    "recule",
    "hesite",
    "palit",
    "se radoucit",
    "semble convaincu",
    "semble convaincue",
    "est convaincu",
    "est convaincue",
    "baisse les yeux",
    "s incline",
)

_FIRST_PERSON_MARKERS = (
    "je ",
    "j ",
    "nous ",
    "mon ",
    "ma ",
    "mes ",
    "notre ",
    "nos ",
)


def companion_visible_game_state(state_data: dict[str, Any]) -> dict[str, Any]:
    """Return a game-state view safe for AI player companions.

    The GM may see the full campaign context. Companions only see table-visible
    state plus facts already played or revealed.
    """
    visible: dict[str, Any] = {}
    for key in _VISIBLE_STATE_KEYS:
        if key in state_data:
            visible[key] = deepcopy(state_data[key])

    campaign_context = state_data.get("campaign_context")
    if isinstance(campaign_context, dict):
        played_canon = _visible_played_canon(campaign_context)
        if _has_visible_canon(played_canon):
            visible["campaign_context"] = {"played_canon": played_canon}

    return visible


def sanitize_companion_visible_text(
    text: str,
    *,
    character_name: Optional[str] = None,
) -> str:
    """Strip obvious GM-owned consequences from companion-visible prose."""
    original = str(text or "").strip()
    if not original:
        return original

    sanitized_sentences: list[str] = []
    for sentence in _split_sentences(original):
        cleaned = _sanitize_sentence(sentence)
        if cleaned and not _sentence_is_gm_owned(cleaned):
            sanitized_sentences.append(cleaned)

    sanitized = _clean_spacing(" ".join(sanitized_sentences))
    if not sanitized:
        sanitized = _fallback_safe_text(original)

    if sanitized != original:
        logger.warning(
            "Companion prose sanitized for %s: %r -> %r",
            character_name or "unknown",
            original,
            sanitized,
        )
    return sanitized


def _visible_played_canon(campaign_context: dict[str, Any]) -> dict[str, Any]:
    raw_canon = campaign_context.get("played_canon")
    canon = raw_canon if isinstance(raw_canon, dict) else {}
    raw_continuity = campaign_context.get("continuity")
    continuity = raw_continuity if isinstance(raw_continuity, dict) else {}

    visible: dict[str, Any] = {}
    for key in _PLAYED_CANON_LIST_KEYS:
        value = canon.get(key)
        if not isinstance(value, list):
            value = continuity.get(key)
        visible[key] = deepcopy(value) if isinstance(value, list) else []

    rolling_summary = canon.get("rolling_summary") or continuity.get("played_summary") or ""
    visible["rolling_summary"] = str(rolling_summary).strip()
    return visible


def _has_visible_canon(canon: dict[str, Any]) -> bool:
    return bool(
        canon.get("rolling_summary")
        or canon.get("established_facts")
        or canon.get("player_decisions")
        or canon.get("revealed_secrets")
    )


def _split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def _sanitize_sentence(sentence: str) -> str:
    parts = re.split(r"([,;])", sentence)
    if len(parts) == 1:
        return sentence.strip()

    kept = [parts[0].strip()]
    index = 1
    while index < len(parts):
        separator = parts[index]
        clause = parts[index + 1].strip() if index + 1 < len(parts) else ""
        if clause and _clause_is_gm_owned(clause):
            index += 2
            continue
        if clause:
            kept.append(separator)
            kept.append(" " + clause)
        index += 2

    return _clean_spacing("".join(kept))


def _clause_is_gm_owned(clause: str) -> bool:
    normalized = _normalize_for_match(clause)
    return _contains_world_result(normalized) or _contains_npc_reaction(normalized)


def _sentence_is_gm_owned(sentence: str) -> bool:
    normalized = _normalize_for_match(sentence)
    if _starts_with_first_person(normalized):
        return False
    return _contains_world_result(normalized) or _contains_npc_reaction(normalized)


def _contains_world_result(normalized: str) -> bool:
    return any(subject in normalized for subject in _WORLD_SUBJECTS) and any(
        result in normalized for result in _WORLD_RESULTS
    )


def _contains_npc_reaction(normalized: str) -> bool:
    has_reaction = any(result in normalized for result in _NPC_REACTION_RESULTS)
    if not has_reaction:
        return False
    if _starts_with_first_person(normalized):
        return False
    return bool(
        re.search(r"\b(azaka|il|elle|ils|elles|le garde|la garde|l aubergiste)\b", normalized)
    )


def _starts_with_first_person(normalized: str) -> bool:
    return normalized.startswith(_FIRST_PERSON_MARKERS)


def _fallback_safe_text(original: str) -> str:
    quote_match = re.search(r"([\"'`].+)$", original)
    if quote_match:
        return quote_match.group(1).strip()
    return original


def _clean_spacing(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"\s+([,;.!?])", r"\1", text)
    text = re.sub(r"([,;])(?=\S)", r"\1 ", text)
    return text


def _normalize_for_match(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(value).casefold().replace("\u2019", "'"))
    without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return re.sub(r"[^a-z0-9']+", " ", without_accents).strip().replace("'", " ")
