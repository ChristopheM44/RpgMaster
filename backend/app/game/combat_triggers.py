"""Heuristics for starting combat from narrative context.

The LLM is instructed to emit structured ``encounter_setup`` and
``state_transition`` actions, but live narration can still omit them.  These
helpers provide a conservative backend safety net for clear hostile scenes.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Optional

_MAX_INFERRED_COMBATANTS = 12

_MONSTER_ALIASES: dict[str, tuple[str, ...]] = {
    "bandit": ("bandit", "brigand", "malfrat", "hors la loi"),
    "cultist": ("cultiste", "adorateur", "fanatique"),
    "goblin": ("gobelin", "goblin"),
    "hobgoblin": ("hobgobelin", "hobgoblin"),
    "orc": ("orc", "orque"),
    "skeleton": ("squelette", "skeleton"),
    "zombie": ("zombie", "mort vivant"),
    "wolf": ("loup", "wolf"),
    "giant_spider": ("araignee geante", "giant spider"),
    "bugbear": ("bugbear", "gobelours"),
    "gnoll": ("gnoll",),
    "ogre": ("ogre",),
    "ghoul": ("goule", "ghoul"),
    "dire_wolf": ("loup terrible", "dire wolf"),
}

_NUMBER_WORDS: dict[str, int] = {
    "un": 1,
    "une": 1,
    "deux": 2,
    "trois": 3,
    "quatre": 4,
    "cinq": 5,
    "six": 6,
    "sept": 7,
    "huit": 8,
    "neuf": 9,
    "dix": 10,
    "onze": 11,
    "douze": 12,
}

_HOSTILE_PATTERNS = (
    r"\bembuscad",
    r"\bassaill",
    r"\battaqu",
    r"\bcharg",
    r"\bsurgi",
    r"\bbondiss",
    r"\bse\s+ru",
    r"\baux\s+armes\b",
    r"\blames?\s+au\s+clair\b",
    r"\bfleches?\s+pleuvent\b",
    r"\bennemis?\b",
    r"\bhostiles?\b",
    r"\bmenaces?\b",
)

_AGGRESSIVE_PATTERNS = (
    r"\b(?:j|je|nous|on)\s*(?:'|e\s+)?attaque\b",
    r"\b(?:j|je|nous|on)\s*(?:'|e\s+)?frappe\b",
    r"\b(?:j|je|nous|on)\s*(?:'|e\s+)?charge\b",
    r"\b(?:j|je|nous|on)\s*(?:'|e\s+)?tire\b",
    r"\b(?:j|je|nous|on)\s*(?:'|e\s+)?vise\b",
    r"\b(?:j|je)\s+me\s+jette\s+dans\s+la\s+melee\b",
    r"\baux\s+armes\b",
)

_AGGRESSIVE_ACTION_TYPES = {"attack", "shove"}


def _normalize(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.lower().replace("’", "'"))
    ascii_text = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"[-_]", " ", ascii_text)


def _alias_pattern(alias: str) -> str:
    parts = [re.escape(part) for part in alias.split()]
    return r"\b" + r"\s+".join(parts) + r"s?\b"


def _infer_count(prefix: str, matched_alias: str) -> int:
    window = prefix[-60:].strip()

    digit_matches = re.findall(r"\b(\d{1,2})\b", window)
    if digit_matches:
        return max(1, int(digit_matches[-1]))

    if re.search(r"\b(?:une?\s+)?douzaine\b", window):
        return 12
    if re.search(r"\b(?:une?\s+)?dizaine\b", window):
        return 10

    for word, value in sorted(_NUMBER_WORDS.items(), key=lambda item: -len(item[0])):
        if re.search(rf"\b{word}\b(?:\s+\w+){{0,4}}$", window):
            return value

    if re.search(r"\bplusieurs\b(?:\s+\w+){0,4}$", window):
        return 3
    if re.search(r"\bquelques\b(?:\s+\w+){0,4}$", window):
        return 3
    if re.search(r"\bdes\b(?:\s+\w+){0,4}$", window):
        return 3
    if re.search(r"\b(?:le|la|ce|cet|cette)\b(?:\s+\w+){0,4}$", window):
        return 1

    return 3 if matched_alias.endswith("s") else 1


def infer_monster_ids_from_text(text: Optional[str]) -> list[str]:
    """Infer SRD monster IDs from a French/English narrative snippet."""
    if not text:
        return []

    normalized = _normalize(text)
    counts: dict[str, int] = {}
    order: list[str] = []

    for monster_id, aliases in _MONSTER_ALIASES.items():
        best = 0
        for alias in aliases:
            for match in re.finditer(_alias_pattern(_normalize(alias)), normalized):
                count = _infer_count(normalized[: match.start()], match.group(0))
                best = max(best, count)
        if best > 0:
            counts[monster_id] = min(best, _MAX_INFERRED_COMBATANTS)
            order.append(monster_id)

    inferred: list[str] = []
    for monster_id in order:
        remaining = _MAX_INFERRED_COMBATANTS - len(inferred)
        if remaining <= 0:
            break
        inferred.extend([monster_id] * min(counts[monster_id], remaining))
    return inferred


def describes_hostile_encounter(text: Optional[str]) -> bool:
    """Return True when text clearly describes hostile enemies engaging."""
    if not text:
        return False
    normalized = _normalize(text)
    if not infer_monster_ids_from_text(text):
        return False
    return any(re.search(pattern, normalized) for pattern in _HOSTILE_PATTERNS)


def is_aggressive_player_intent(action_type: str, content: Optional[str]) -> bool:
    """Return True for explicit player intent to attack or force combat."""
    if action_type in _AGGRESSIVE_ACTION_TYPES:
        return True
    normalized = _normalize(content or "")
    return any(re.search(pattern, normalized) for pattern in _AGGRESSIVE_PATTERNS)


def _base_monster_id(target_id: Optional[str]) -> Optional[str]:
    if not target_id:
        return None
    normalized = target_id.strip().lower().replace("-", "_")
    if normalized in _MONSTER_ALIASES:
        return normalized
    if "_" in normalized:
        base = "_".join(normalized.rsplit("_", 1)[:-1])
        if base in _MONSTER_ALIASES:
            return base
    return None


def _phase_value(active: Any) -> str:
    phase = getattr(active, "phase", "")
    return getattr(phase, "value", str(phase)).lower()


def _prime_transition(
    active: Any,
    monster_ids: list[str],
    *,
    context: str,
    source: str,
) -> bool:
    if _phase_value(active) == "combat":
        return False

    pending = active.state_data.get("pending_encounter")
    if pending and pending.get("monster_ids"):
        active.state_data["pending_phase_transition"] = "COMBAT"
        active.mark_dirty()
        return True

    if not monster_ids:
        return False

    active.state_data["pending_encounter"] = {
        "monster_ids": monster_ids,
        "context": context[:280],
        "source": source,
    }
    active.state_data["pending_phase_transition"] = "COMBAT"
    active.mark_dirty()
    return True


def prime_combat_from_hostile_narration(
    active: Any,
    narration: Optional[str],
    *,
    source: str = "hostile_narration",
) -> bool:
    """Set pending encounter/transition when GM prose clearly starts combat."""
    if not describes_hostile_encounter(narration):
        return False
    return _prime_transition(
        active,
        infer_monster_ids_from_text(narration),
        context=narration or "",
        source=source,
    )


def prime_combat_from_aggressive_action(
    active: Any,
    *,
    action_type: str,
    content: Optional[str],
    target_id: Optional[str] = None,
) -> bool:
    """Set a combat transition from an explicit non-combat attack intent."""
    if not is_aggressive_player_intent(action_type, content):
        return False

    monster_ids = infer_monster_ids_from_text(content)
    if not monster_ids:
        base_id = _base_monster_id(target_id)
        if base_id:
            monster_ids = [base_id]

    return _prime_transition(
        active,
        monster_ids,
        context=content or action_type,
        source="aggressive_player_intent",
    )
