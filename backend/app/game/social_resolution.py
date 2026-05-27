"""Deterministic bounds for durable NPC social outcomes.

Also contains social-detection helpers (markers, text classification,
target resolution, DC calculation) extracted from action_pipeline.py.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from app.engine.ability_checks import Ability

ATTITUDE_ORDER = ["hostile", "unfriendly", "indifferent", "friendly", "helpful"]
_ATTITUDE_INDEX = {name: index for index, name in enumerate(ATTITUDE_ORDER)}

# ---------------------------------------------------------------------------
# Social markers & text classification
# ---------------------------------------------------------------------------

_SOCIAL_COMBAT_MARKERS = (
    "rends toi",
    "rends-toi",
    "rendez vous",
    "rendez-vous",
    "pose tes armes",
    "posez vos armes",
    "depose",
    "dépose",
    "clemence",
    "clémence",
    "parlement",
    "negoc",
    "négoc",
    "intimid",
    "persuad",
)


def _normalized_text(text: Optional[str]) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold().replace("'", "'"))


def _is_combat_social_text(text: Optional[str]) -> bool:
    normalized = _normalized_text(text)
    return any(marker in normalized for marker in _SOCIAL_COMBAT_MARKERS)


_SOCIAL_EXPLORATION_MARKERS: dict[str, str] = {
    "persuad": "persuasion",
    "convainc": "persuasion",
    "enjoindre": "persuasion",
    "supplier": "persuasion",
    "plaider": "persuasion",
    "intimid": "intimidation",
    "menac": "intimidation",
    "terrifier": "intimidation",
    "brandir": "intimidation",
    "perspicac": "insight",
    "detecter le mensonge": "insight",
    "sonder": "insight",
    "lire": "insight",
    "deviner": "insight",
    "tromp": "deception",
    "mentir": "deception",
    "feindre": "deception",
    "bluffer": "deception",
    "parlement": "persuasion",
    "negoc": "persuasion",
    "négoc": "persuasion",
    "charmer": "persuasion",
    "seduire": "persuasion",
    "séduire": "persuasion",
    "soudoyer": "persuasion",
    "reconcilier": "persuasion",
    "demande": "persuasion",
    "demander": "persuasion",
    "implorer": "persuasion",
    "flatter": "persuasion",
}

_ABILITY_SHORT_KEYS: dict[str, str] = {
    "strength": "str",
    "dexterity": "dex",
    "constitution": "con",
    "intelligence": "int",
    "wisdom": "wis",
    "charisma": "cha",
}


def _is_social_exploration_text(text: Optional[str]) -> bool:
    normalized = _normalized_text(text)
    return any(marker in normalized for marker in _SOCIAL_EXPLORATION_MARKERS)


def _detect_social_skill(text: Optional[str]) -> Optional[str]:
    normalized = _normalized_text(text)
    for marker, skill in _SOCIAL_EXPLORATION_MARKERS.items():
        if marker in normalized:
            return skill
    return None


_DESCRIPTION_STOP_WORDS = frozenset(
    {
        "un",
        "une",
        "des",
        "le",
        "la",
        "les",
        "du",
        "de",
        "au",
        "aux",
        "et",
        "ou",
        "ni",
        "mais",
        "donc",
        "car",
        "a",
        "à",
        "en",
        "dans",
        "sur",
        "sous",
        "par",
        "pour",
        "avec",
        "vers",
        "chez",
        "sans",
        "entre",
        "contre",
        "ce",
        "cet",
        "cette",
        "ces",
        "son",
        "sa",
        "ses",
        "leur",
        "leurs",
        "mon",
        "ma",
        "mes",
        "ton",
        "ta",
        "tes",
        "notre",
        "nos",
        "votre",
        "vos",
        "qui",
        "que",
        "quoi",
        "dont",
        "où",
        "il",
        "elle",
        "ils",
        "elles",
        "lui",
        "eux",
        "moi",
        "toi",
        "soi",
        "est",
        "sont",
        "etre",
        "être",
        "avoir",
        "ont",
        "fait",
        "faire",
        "tres",
        "très",
        "bien",
        "plus",
        "moins",
        "tout",
        "tous",
        "toute",
        "encore",
        "deja",
        "déjà",
        "aussi",
        "alors",
        "ainsi",
        "homme",
        "femme",
        "personne",
        "gens",
    }
)


def _description_keywords(description: str) -> set[str]:
    """Extract salient keywords from an NPC description for fuzzy matching."""
    normalized = _normalized_text(description)
    tokens = re.findall(r"[a-zà-ÿ]+", normalized)
    return {token for token in tokens if len(token) >= 3 and token not in _DESCRIPTION_STOP_WORDS}


def _is_npc_poi(poi: Any) -> bool:
    if not isinstance(poi, dict):
        return False
    kind = str(poi.get("kind") or "").strip().casefold()
    icon = str(poi.get("icon") or "").strip().casefold()
    return kind == "npc" or icon == "npc"


def _poi_by_id(state_data: dict[str, Any], target_id: Optional[str]) -> Optional[dict[str, Any]]:
    if not target_id:
        return None
    scene = state_data.get("current_scene", {})
    pois = scene.get("pois", []) if isinstance(scene, dict) else []
    for poi in pois:
        if not isinstance(poi, dict):
            continue
        if str(poi.get("id") or "") == target_id:
            return poi
    return None


def _detect_social_target_id(text: Optional[str], state_data: dict[str, Any]) -> Optional[str]:
    """Extrai l'identifiant d'un PNJ cible depuis le texte du joueur.

    Stratégie en deux passes :
    1. Match par nom exact (substring) dans `npc_states` puis dans les POIs.
    2. Match par mots-clés saillants de la description (PNJ anonymes, où le
       joueur ne peut désigner le PNJ que par sa description).
    """
    if not text:
        return None
    normalized = _normalized_text(text)
    npc_states = state_data.get("npc_states", {})
    if not isinstance(npc_states, dict):
        npc_states = {}
    scene = state_data.get("current_scene", {})
    pois = scene.get("pois", []) if isinstance(scene, dict) else []

    # 1a. Recherche par nom exact dans npc_states.
    for npc_id, npc in npc_states.items():
        if not isinstance(npc, dict):
            continue
        name = str(npc.get("name", "")).casefold()
        if name and name in normalized:
            return npc_id

    # 1b. Recherche par nom exact dans les POIs de la scène.
    for poi in pois:
        if not isinstance(poi, dict):
            continue
        name = str(poi.get("name", "")).casefold()
        if name and name in normalized:
            return str(poi.get("id", name))

    player_tokens = _description_keywords(normalized)
    if not player_tokens:
        return None

    # 1c. Match par token saillant du nom (prénom propre, surnom unique).
    for npc_id, npc in npc_states.items():
        if not isinstance(npc, dict):
            continue
        name_tokens = _description_keywords(str(npc.get("name", "")))
        if name_tokens & player_tokens:
            return npc_id

    for poi in pois:
        if not isinstance(poi, dict) or not _is_npc_poi(poi):
            continue
        name_tokens = _description_keywords(str(poi.get("name", "")))
        if name_tokens & player_tokens:
            poi_id = str(poi.get("id") or "").strip()
            if poi_id:
                return poi_id

    # 2. Match par mots-clés de description (PNJ anonymes / désignations
    # descriptives type "l'homme au chapeau").

    candidates: list[tuple[str, int, bool]] = []
    seen_ids: set[str] = set()

    for poi in pois:
        if not isinstance(poi, dict) or not _is_npc_poi(poi):
            continue
        poi_id = str(poi.get("id") or "").strip()
        description = str(poi.get("description") or "")
        if not poi_id or not description:
            continue
        common = player_tokens & _description_keywords(description)
        if common:
            candidates.append((poi_id, len(common), True))
            seen_ids.add(poi_id)

    for npc_id, npc in npc_states.items():
        if not isinstance(npc, dict) or npc_id in seen_ids:
            continue
        description = str(npc.get("description") or "")
        if not description:
            continue
        common = player_tokens & _description_keywords(description)
        if common:
            candidates.append((str(npc_id), len(common), False))

    if not candidates:
        return None

    present_count = sum(1 for _, _, is_present in candidates if is_present)
    threshold = 1 if present_count == 1 else 2
    valid = [c for c in candidates if c[1] >= threshold]
    if not valid:
        return None

    # Score décroissant, puis PNJ présents prioritaires.
    valid.sort(key=lambda c: (-c[1], not c[2]))
    return valid[0][0]


def _is_valid_npc_target_id(target_id: Optional[str], state_data: dict[str, Any]) -> bool:
    if not target_id:
        return False
    npc_states = state_data.get("npc_states", {})
    if isinstance(npc_states, dict) and target_id in npc_states:
        return True
    poi = _poi_by_id(state_data, target_id)
    return _is_npc_poi(poi)


def resolve_npc_target_id(
    text: Optional[str],
    state_data: dict[str, Any],
    explicit_target_id: Optional[str] = None,
) -> Optional[str]:
    """Retourne une cible PNJ valide, jamais un coffre/porte/indice."""
    if _is_valid_npc_target_id(explicit_target_id, state_data):
        return explicit_target_id

    detected = _detect_social_target_id(text, state_data)
    if _is_valid_npc_target_id(detected, state_data):
        return detected
    return None


def _ability_short_key(ability: Ability | str | None) -> str:
    if isinstance(ability, Ability):
        return _ABILITY_SHORT_KEYS.get(ability.value, "cha")
    text = str(ability or "charisma").strip().lower()
    return _ABILITY_SHORT_KEYS.get(text, text[:3] or "cha")


def _normalized_skill_proficiencies(char_data: dict[str, Any]) -> set[str]:
    raw = char_data.get("skill_proficiencies", [])
    if not isinstance(raw, list):
        return set()
    return {
        str(skill).strip().lower().replace(" ", "_").replace("-", "_")
        for skill in raw
        if str(skill).strip()
    }


def _calculate_social_dc(
    state_data: dict[str, Any],
    social_target_id: Optional[str],
    skill: Optional[str],
) -> int:
    base = 15
    if social_target_id:
        npc_states = state_data.get("npc_states", {})
        npc = npc_states.get(social_target_id, {})
        attitude = str(npc.get("attitude", "")).lower()
        attitude_dcs = {
            "hostile": 20,
            "unfriendly": 18,
            "indifferent": 15,
            "friendly": 12,
            "helpful": 10,
        }
        base = attitude_dcs.get(attitude, 15)

    if skill == "insight":
        base = max(10, base - 2)
    elif skill == "deception":
        base = min(30, base + 2)

    campaign_context = state_data.get("campaign_context", {})
    chapter = campaign_context.get("active_chapter", {})
    for dc_entry in chapter.get("indicative_dcs", []):
        if str(dc_entry.get("ability", "")).lower() in {
            "cha",
            "wis",
            str(skill)[:3],
        }:
            base = int(dc_entry.get("dc", base))
            break

    return max(5, min(base, 30))


@dataclass(frozen=True)
class SocialRollContext:
    target_id: str
    success: bool


class SocialResolution:
    """Apply deterministic attitude bounds after an engine-resolved social roll."""

    @staticmethod
    def roll_context(roll_results: Optional[dict[str, Any]]) -> Optional[SocialRollContext]:
        if not isinstance(roll_results, dict):
            return None
        roll_type = roll_results.get("type")
        if roll_type not in (None, "skill_check"):
            return None
        target_id = str(
            roll_results.get("social_target_id")
            or roll_results.get("target_id")
            or ""
        ).strip()
        if not target_id or not isinstance(roll_results.get("success"), bool):
            return None
        return SocialRollContext(target_id=target_id, success=bool(roll_results["success"]))

    @staticmethod
    def normalize_attitude(value: Any) -> str:
        text = str(value or "").strip().lower()
        return text if text in _ATTITUDE_INDEX else "indifferent"

    @classmethod
    def bounded_attitude(
        cls,
        previous_attitude: Any,
        proposed_attitude: Optional[str],
        *,
        success: bool,
    ) -> tuple[str, bool]:
        previous = cls.normalize_attitude(previous_attitude)
        previous_index = _ATTITUDE_INDEX[previous]

        if (
            proposed_attitude is None
            or str(proposed_attitude).strip().lower() not in _ATTITUDE_INDEX
        ):
            proposed = previous
            invalid = proposed_attitude is not None
        else:
            proposed = str(proposed_attitude).strip().lower()
            invalid = False

        proposed_index = _ATTITUDE_INDEX[proposed]
        if success:
            low = previous_index
            high = min(previous_index + 1, len(ATTITUDE_ORDER) - 1)
        else:
            low = max(previous_index - 1, 0)
            high = previous_index

        bounded_index = max(low, min(proposed_index, high))
        bounded = ATTITUDE_ORDER[bounded_index]
        return bounded, invalid or bounded != proposed

    @classmethod
    def default_attitude(cls, previous_attitude: Any, *, success: bool) -> str:
        previous = cls.normalize_attitude(previous_attitude)
        if not success:
            return previous
        index = min(_ATTITUDE_INDEX[previous] + 1, len(ATTITUDE_ORDER) - 1)
        return ATTITUDE_ORDER[index]

    @classmethod
    def outcome_payload(
        cls,
        *,
        npc_id: str,
        previous_attitude: Any,
        attitude: str,
        note: str = "",
        roll_context: Optional[SocialRollContext] = None,
        clamped: bool = False,
        source: str,
        new_quest: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "npc_id": npc_id,
            "attitude": attitude,
            "previous_attitude": cls.normalize_attitude(previous_attitude),
            "note": note,
            "clamped": clamped,
            "source": source,
        }
        if roll_context is not None:
            payload["roll_success"] = roll_context.success
        if isinstance(new_quest, dict):
            payload["new_quest"] = new_quest
        return payload
