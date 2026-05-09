from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable, Sequence
from typing import Any, Optional

logger = logging.getLogger(__name__)

ELLIPSIS_ONLY_RESPONSES = {"...", "…"}


def recover_partial_json_response(
    raw: str,
    *,
    character_name: str,
    game_state: Optional[dict[str, Any]],
    safe_recovered_roleplay: Callable[
        [Optional[str], Optional[str], Optional[str], dict[str, Any]], str
    ],
) -> Optional[dict[str, Any]]:
    if "action_type" not in raw and "roleplay_text" not in raw:
        return None

    def _field(name: str) -> tuple[Optional[str], bool]:
        complete = re.search(rf'"{name}"\s*:\s*"((?:[^"\\]|\\.)*)"', raw, re.DOTALL)
        match = complete or re.search(rf'"{name}"\s*:\s*"((?:[^"\\]|\\.)*)', raw, re.DOTALL)
        if not match:
            return None, False
        try:
            return json.loads(f'"{match.group(1)}"'), complete is not None
        except json.JSONDecodeError:
            return (
                match.group(1).replace('\\"', '"').replace("\\n", "\n"),
                complete is not None,
            )

    action_type, _ = _field("action_type")
    action_description, _ = _field("action_description")
    roleplay_text, roleplay_complete = _field("roleplay_text")
    target, _ = _field("target")
    inner_reasoning, _ = _field("inner_reasoning")

    if not any([action_type, action_description, roleplay_text, target, inner_reasoning]):
        return None

    if roleplay_text and roleplay_complete:
        roleplay_source = roleplay_text
    else:
        logger.warning(
            "PlayerAgent[%s] : réponse JSON tronquée récupérée sans texte affichable complet.",
            character_name,
        )
        roleplay_source = safe_recovered_roleplay(
            action_type,
            action_description,
            target,
            game_state or {},
        )
    return {
        "action_type": action_type or "wait",
        "action_description": action_description or "Le personnage réagit prudemment.",
        "target": None if target in (None, "null") else target,
        "params": {},
        "roleplay_text": roleplay_source.strip()[:500],
        "inner_reasoning": inner_reasoning,
    }


def recover_structured_text_response(raw: str) -> Optional[dict[str, Any]]:
    stripped = raw.strip()
    if not stripped or ":" not in stripped:
        return None

    def _match(pattern: str) -> Optional[str]:
        match = re.search(pattern, raw, re.IGNORECASE | re.DOTALL)
        if not match:
            return None
        value = match.group(1).strip().strip(' "\'')
        return value or None

    action_type = _match(r"(?:action_type|type_action|action)\s*[:=]\s*([a-z_]+)")
    action_description = _match(
        r"(?:action_description|description_action|description)\s*[:=]\s*(.+?)(?:\n[\w_]+\s*[:=]|\Z)"
    )
    roleplay_text = _match(
        r"(?:roleplay_text|roleplay|texte|dialogue)\s*[:=]\s*(.+?)(?:\n[\w_]+\s*[:=]|\Z)"
    )
    target = _match(r"(?:target|cible)\s*[:=]\s*(.+?)(?:\n[\w_]+\s*[:=]|\Z)")
    reasoning = _match(
        r"(?:inner_reasoning|reasoning|raisonnement)\s*[:=]\s*(.+?)(?:\n[\w_]+\s*[:=]|\Z)"
    )

    if not any([action_type, action_description, roleplay_text, target, reasoning]):
        return None

    return {
        "action_type": action_type or "wait",
        "action_description": action_description or "Le personnage réagit prudemment.",
        "target": None if target in (None, "null") else target,
        "params": {},
        "roleplay_text": (roleplay_text or action_description or stripped)[:500],
        "inner_reasoning": reasoning,
    }


def recover_prose_action_response(
    raw: str,
    *,
    game_state: dict[str, Any],
    available_actions: Optional[Sequence[str]],
    combat_mode: bool,
    available_action_set: Callable[[Optional[Sequence[str]]], set[str]],
    infer_action_type_from_text: Callable[[str, set[str]], Optional[str]],
    find_referenced_combatant: Callable[[str, dict[str, Any]], Optional[str]],
    select_default_enemy_target: Callable[[dict[str, Any]], Optional[str]],
    infer_spell_name_from_text: Callable[[str, dict[str, Any]], Optional[str]],
    combatant_name: Callable[[dict[str, Any], Optional[str]], str],
    describe_inferred_action: Callable[[str, str, str], str],
) -> Optional[dict[str, Any]]:
    stripped = raw.strip()
    if not stripped or stripped in ELLIPSIS_ONLY_RESPONSES:
        return None

    available = available_action_set(available_actions)
    action_type = infer_action_type_from_text(stripped, available)
    target = find_referenced_combatant(stripped, game_state)

    if combat_mode and action_type is None and target and "attack" in available:
        action_type = "attack"

    if action_type is None:
        return None

    if combat_mode and action_type in {"attack", "cast_spell", "shove", "help"}:
        target = target or select_default_enemy_target(game_state)

    if action_type == "cast_spell":
        spell_name = infer_spell_name_from_text(stripped, game_state)
        if spell_name is None:
            if combat_mode and "attack" in available:
                action_type = "attack"
            else:
                return None
        params = {"spell_name": spell_name} if action_type == "cast_spell" else {}
    else:
        params = {}

    if combat_mode and action_type in {"attack", "cast_spell", "shove", "help"}:
        if target is None:
            if "dodge" in available:
                action_type = "dodge"
            elif "wait" in available:
                action_type = "wait"
            else:
                return None
            params = {}

    if action_type not in available:
        return None

    target_name = combatant_name(game_state, target)
    description = describe_inferred_action(action_type, target_name, stripped)
    return {
        "action_type": action_type,
        "action_description": description,
        "target": target,
        "params": params,
        "roleplay_text": stripped[:500],
        "inner_reasoning": "Action récupérée depuis une réponse non-JSON du LLM.",
    }


def build_default_combat_action(
    raw: str,
    *,
    character_name: str,
    game_state: dict[str, Any],
    available_actions: Optional[Sequence[str]],
    available_action_set: Callable[[Optional[Sequence[str]]], set[str]],
    select_default_enemy_target: Callable[[dict[str, Any]], Optional[str]],
    combatant_name: Callable[[dict[str, Any], Optional[str]], str],
) -> Optional[dict[str, Any]]:
    available = available_action_set(available_actions)
    target = select_default_enemy_target(game_state)
    target_name = combatant_name(game_state, target)
    stripped = raw.strip()

    if target and "attack" in available:
        roleplay_text = (
            stripped[:500]
            if stripped and stripped not in ELLIPSIS_ONLY_RESPONSES
            else f"{character_name} reprend l'initiative et attaque {target_name}."
        )
        return {
            "action_type": "attack",
            "action_description": f"Attaque {target_name}",
            "target": target,
            "params": {},
            "roleplay_text": roleplay_text,
            "inner_reasoning": (
                "Fallback combat : la réponse LLM était inexploitable, "
                "attaque de la cible ennemie vivante la plus fragile."
            ),
        }

    for fallback_type, description in (
        ("dodge", "Se met en défense"),
        ("wait", "Attend sur la défensive"),
    ):
        if fallback_type in available:
            return {
                "action_type": fallback_type,
                "action_description": description,
                "target": None,
                "params": {},
                "roleplay_text": (
                    stripped[:500]
                    if stripped and stripped not in ELLIPSIS_ONLY_RESPONSES
                    else f"{character_name} se remet en garde."
                ),
                "inner_reasoning": "Fallback combat : aucune cible ennemie exploitable trouvée.",
            }

    if available:
        action_type = sorted(available)[0]
        return {
            "action_type": action_type,
            "action_description": f"Action de secours : {action_type}",
            "target": None,
            "params": {},
            "roleplay_text": stripped[:500] or f"{character_name} agit prudemment.",
            "inner_reasoning": "Fallback combat : première action disponible.",
        }

    return None
