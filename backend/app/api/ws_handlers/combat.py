"""Combat helpers used by the game WebSocket facade."""
from __future__ import annotations

import re
from typing import Any, Optional

from app.api.ws_schemas import PlayerActionMessage
from app.game.constants import INACTIVE_STATUSES
from app.game.event_bus import EventType

TURN_BOUND_COMBAT_ACTIONS = {
    "attack",
    "cast_spell",
    "death_save",
    "disengage",
    "dash",
    "dodge",
    "end_turn",
    "equip",
    "free_text",
    "hide",
    "move",
    "shove",
    "stabilize",
    "use_item",
    "wait",
}

SOCIAL_COMBAT_MARKERS = (
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


def normalized_phrase(text: Optional[str]) -> str:
    if not text:
        return ""
    normalized = text.casefold().replace("’", "'")
    return re.sub(r"\s+", " ", normalized)


def is_combat_social_text(text: Optional[str]) -> bool:
    normalized = normalized_phrase(text)
    return any(marker in normalized for marker in SOCIAL_COMBAT_MARKERS)


def active_npc_ids(active: Any) -> list[str]:
    combatants: dict[str, Any] = active.state_data.get("combatants", {})
    result: list[str] = []
    for cid, cdata in combatants.items():
        if not isinstance(cdata, dict) or cdata.get("is_player", True):
            continue
        status = str(cdata.get("status", "active")).lower()
        try:
            hp = int(cdata.get("hp", 1))
        except (TypeError, ValueError):
            hp = 1
        if hp > 0 and status not in INACTIVE_STATUSES:
            result.append(cid)
    return result


def combat_target_id(action: PlayerActionMessage, active: Any) -> Optional[str]:
    if action.target_id:
        return action.target_id
    if action.action_type != "free_text" or not is_combat_social_text(action.content):
        return None
    active_npcs = active_npc_ids(active)
    return active_npcs[0] if len(active_npcs) == 1 else None


async def reject_out_of_turn_action(
    session_id: str,
    action: PlayerActionMessage,
    active: Any,
    *,
    event_bus: Any,
    source: str = "ws_game",
) -> bool:
    if action.action_type not in TURN_BOUND_COMBAT_ACTIONS or not action.character_id:
        return False
    current = active.turn_manager.current_turn
    if current is None:
        return False
    if action.action_type == "end_turn" and current.is_ai_controlled:
        return False
    if action.character_id == current.combatant_id:
        return False

    await event_bus.publish_to_session(
        session_id,
        EventType.ERROR,
        {
            "message": (
                f"Ce n'est pas le tour de ce personnage. "
                f"Tour actuel : {current.name}."
            )
        },
        source=source,
    )
    return True


def combat_end_reason_from_removed(removed: list[dict[str, Any]]) -> str:
    statuses = {str(item.get("status", "defeated")) for item in removed}
    if not statuses:
        return "victory"
    if statuses == {"surrendered"}:
        return "surrender"
    if statuses == {"fled"}:
        return "fled"
    if statuses & {"surrendered", "fled"}:
        return "resolved"
    return "victory"


def combat_end_text(reason: str) -> str:
    if reason == "surrender":
        return "Le dernier adversaire se rend. Le combat prend fin et le calme revient."
    if reason == "fled":
        return "Les derniers adversaires prennent la fuite. Le combat prend fin."
    if reason == "resolved":
        return "La menace est neutralisée. Le combat prend fin."
    return "Victoire ! Tous les ennemis ont été vaincus. Le calme revient."


def npc_removed_text(name: str, status: str) -> str:
    if status == "surrendered":
        return f"{name} se rend et quitte l'initiative."
    if status == "fled":
        return f"{name} fuit le combat !"
    return f"{name} a été vaincu !"
