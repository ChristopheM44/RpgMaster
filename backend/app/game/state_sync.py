"""Small helpers for keeping active character snapshots aligned."""
from __future__ import annotations

from typing import Any, Optional

from app.game.session_manager import ActiveSession


def sync_character_state(
    active: Optional[ActiveSession],
    character_id: str,
    *,
    hp: Optional[int] = None,
    hp_max: Optional[int] = None,
    level: Optional[int] = None,
    xp: Optional[int] = None,
    gp: Optional[int] = None,
    sp: Optional[int] = None,
    cp: Optional[int] = None,
    xp_to_next_level: Optional[int] = None,
    ability_scores: Optional[dict[str, int]] = None,
    pending_asi: Optional[bool] = None,
    equipment: Optional[list[dict[str, Any]]] = None,
    spell_slots: Optional[dict[str, Any]] = None,
    hit_dice: Optional[dict[str, Any]] = None,
    conditions: Optional[list[str]] = None,
) -> bool:
    """Update character and combatant snapshots inside an active session."""
    if active is None:
        return False

    changed = False
    characters = active.state_data.setdefault("characters", {})
    cdata = characters.get(character_id)
    if cdata is not None:
        changed = _set_if_provided(cdata, "hp", hp) or changed
        changed = _set_if_provided(cdata, "hp_max", hp_max) or changed
        changed = _set_if_provided(cdata, "level", level) or changed
        changed = _set_if_provided(cdata, "xp", xp) or changed
        changed = _set_if_provided(cdata, "gp", gp) or changed
        changed = _set_if_provided(cdata, "sp", sp) or changed
        changed = _set_if_provided(cdata, "cp", cp) or changed
        changed = _set_if_provided(cdata, "xp_to_next_level", xp_to_next_level) or changed
        changed = _set_if_provided(cdata, "ability_scores", ability_scores) or changed
        changed = _set_if_provided(cdata, "pending_asi", pending_asi) or changed
        changed = _set_if_provided(cdata, "equipment", equipment) or changed
        changed = _set_if_provided(cdata, "spell_slots", spell_slots) or changed
        changed = _set_if_provided(cdata, "hit_dice", hit_dice) or changed
        changed = _set_if_provided(cdata, "conditions", conditions) or changed

    combatants = active.state_data.get("combatants", {})
    combatant = combatants.get(character_id)
    if combatant is not None:
        changed = _set_if_provided(combatant, "hp", hp) or changed
        changed = _set_if_provided(combatant, "hp_max", hp_max) or changed
        changed = _set_if_provided(combatant, "level", level) or changed
        changed = _set_if_provided(combatant, "conditions", conditions) or changed

    if changed:
        active.mark_dirty()
    return changed


def _set_if_provided(target: dict[str, Any], key: str, value: Any) -> bool:
    if value is None:
        return False
    if target.get(key) == value:
        return False
    target[key] = value
    return True
