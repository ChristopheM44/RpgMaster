"""Scene state source-of-truth helpers.

The local scene is stored inside ``ActiveSession.state_data["current_scene"]``.
This module applies incremental patches to that JSON blob without replacing the
whole layout, so discoveries and party positions can persist like they would at
a real table.
"""
from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.game.session_manager import ActiveSession
from app.services import local_map_service

_VISIBILITIES = {"visible", "subtle", "hidden"}
_DISCOVERY_STATES = {"undiscovered", "discovered", "examined", "resolved", "locked", "open"}
_NPC_STATUSES = {"present", "absent", "missing", "hidden", "left", "abducted", "dead"}

_POI_TEXT_FIELDS = {
    "name": 120,
    "kind": 40,
    "icon": 48,
    "description": 360,
    "action_hint": 220,
    "element_id": 80,
    "state": 32,
    "visibility": 16,
    "physical_state": 160,
}

_ELEMENT_TEXT_FIELDS = {
    "name": 120,
    "kind": 32,
    "description": 280,
    "terrain_type": 32,
    "visibility": 16,
    "state": 32,
    "physical_state": 160,
}


def apply_scene_update(active: ActiveSession, params: dict[str, Any]) -> dict[str, Any] | None:
    """Merge a GM ``scene_update`` action into the current scene.

    Returns the updated full scene, or ``None`` when no current scene exists.
    """
    scene = active.state_data.get("current_scene")
    if not isinstance(scene, dict):
        return None

    updated = deepcopy(scene)
    cols = _clamp_int(updated.get("cols"), default=12, minimum=3, maximum=24)
    rows = _clamp_int(updated.get("rows"), default=12, minimum=3, maximum=24)
    updated["cols"] = cols
    updated["rows"] = rows
    updated.setdefault("cell_size_m", 1.5)
    updated.setdefault("pois", [])
    updated.setdefault("exits", [])
    updated.setdefault("party_positions", {})

    _merge_pois(updated, params, cols, rows)
    _merge_elements(updated, params, cols, rows)
    _merge_party_positions(updated, params, cols, rows)
    _merge_scene_fields(updated, params)
    _apply_discoveries(updated, params)
    _merge_npc_updates(active, updated, params)

    local_map_service.enrich_scene_layout(updated)
    active.state_data["current_scene"] = updated
    active.mark_dirty()
    return updated


def _merge_pois(scene: dict[str, Any], params: dict[str, Any], cols: int, rows: int) -> None:
    pois = [poi for poi in scene.get("pois", []) if isinstance(poi, dict) and poi.get("id")]
    by_id = {str(poi["id"]): dict(poi) for poi in pois}

    for raw in _items(params, "remove_poi_ids", "remove_pois"):
        by_id.pop(str(raw), None)

    for raw in _items(params, "upsert_pois", "pois"):
        existing = by_id.get(str(raw.get("id"))) if isinstance(raw, dict) else None
        poi = _normalize_poi(raw, cols, rows, existing=existing)
        if poi:
            by_id[poi["id"]] = poi

    for raw in _items(params, "update_pois", "poi_updates"):
        if not isinstance(raw, dict):
            continue
        poi_id = str(raw.get("id") or "").strip()
        if not poi_id or poi_id not in by_id:
            continue
        patch = _normalize_poi_patch(raw, cols, rows)
        by_id[poi_id] = {**by_id[poi_id], **patch, "id": poi_id}

    scene["pois"] = list(by_id.values())[:64]


def _merge_elements(scene: dict[str, Any], params: dict[str, Any], cols: int, rows: int) -> None:
    elements = [
        element
        for element in scene.get("elements", [])
        if isinstance(element, dict) and element.get("id")
    ]
    by_id = {str(element["id"]): dict(element) for element in elements}

    for raw in _items(params, "remove_element_ids", "remove_elements"):
        by_id.pop(str(raw), None)

    for raw in _items(params, "upsert_elements", "elements"):
        element = _normalize_element(raw, cols, rows)
        if element:
            existing = by_id.get(element["id"], {})
            by_id[element["id"]] = {**existing, **element}

    for raw in _items(params, "update_elements", "element_updates"):
        if not isinstance(raw, dict):
            continue
        element_id = str(raw.get("id") or "").strip()
        if not element_id or element_id not in by_id:
            continue
        patch = _normalize_element_patch(raw, cols, rows)
        by_id[element_id] = {**by_id[element_id], **patch, "id": element_id}

    if by_id:
        scene["elements"] = list(by_id.values())[:96]
    else:
        scene.pop("elements", None)


def _merge_party_positions(
    scene: dict[str, Any],
    params: dict[str, Any],
    cols: int,
    rows: int,
) -> None:
    party_positions = scene.setdefault("party_positions", {})
    if not isinstance(party_positions, dict):
        party_positions = {}
        scene["party_positions"] = party_positions

    raw_positions = params.get("party_positions") or params.get("move_party")
    if isinstance(raw_positions, dict):
        for char_id, raw_position in raw_positions.items():
            position = _normalize_position(raw_position, cols, rows)
            if position is not None:
                party_positions[str(char_id)] = position


def _merge_scene_fields(scene: dict[str, Any], params: dict[str, Any]) -> None:
    for field, max_len in (
        ("description", 1500),
        ("terrain", 80),
        ("scene_theme", 40),
        ("physical_state", 180),
        ("state", 40),
    ):
        value = _clean_text(params.get(field), max_len=max_len)
        if value:
            scene[field] = value
    facts = _normalize_facts(params.get("facts"))
    if facts:
        scene["facts"] = _merged_unique(scene.get("facts"), facts, limit=24)


def _apply_discoveries(scene: dict[str, Any], params: dict[str, Any]) -> None:
    discovered_ids = {
        str(item)
        for item in _items(params, "discovered_ids", "discover", "discovered")
        if str(item).strip()
    }
    if not discovered_ids:
        return
    for collection_name in ("pois", "elements"):
        for item in scene.get(collection_name, []) or []:
            if not isinstance(item, dict) or str(item.get("id") or "") not in discovered_ids:
                continue
            item["discovered"] = True
            if item.get("visibility") == "hidden":
                item["visibility"] = "subtle"
            item.setdefault("state", "discovered")


def _merge_npc_updates(
    active: ActiveSession,
    scene: dict[str, Any],
    params: dict[str, Any],
) -> None:
    raw_updates = _items(params, "npc_updates", "entities")
    if not raw_updates:
        return
    npc_states = active.state_data.setdefault("npc_states", {})
    if not isinstance(npc_states, dict):
        npc_states = {}
        active.state_data["npc_states"] = npc_states
    scene_id = str(scene.get("scene_id") or "")
    for raw in raw_updates:
        if not isinstance(raw, dict):
            continue
        npc_id = str(raw.get("id") or raw.get("npc_id") or "").strip()
        if not npc_id:
            continue
        npc = npc_states.setdefault(npc_id, {})
        if not isinstance(npc, dict):
            npc = {}
            npc_states[npc_id] = npc
        name = _clean_text(raw.get("name"), max_len=120)
        if name:
            npc["name"] = name
        status = _clean_text(raw.get("status"), max_len=32).lower()
        if status in _NPC_STATUSES:
            npc["status"] = status
            if status == "present":
                npc["last_location"] = (
                    _clean_text(raw.get("last_location"), max_len=80) or scene_id
                )
            elif status in {"absent", "missing", "hidden", "left", "abducted", "dead"}:
                npc["last_location"] = _clean_text(raw.get("last_location"), max_len=80) or ""
        if isinstance(raw.get("known_to_party"), bool):
            npc["known_to_party"] = raw["known_to_party"]
        note = _clean_text(raw.get("note"), max_len=240)
        if note:
            npc["notes"] = _merged_unique(npc.get("notes"), [note], limit=12)
        position = _normalize_position(raw.get("position"), int(scene["cols"]), int(scene["rows"]))
        if position is not None:
            npc["position"] = position
            _upsert_npc_poi(scene, npc_id, npc.get("name") or npc_id, position)
        if status in {"absent", "missing", "hidden", "left", "abducted", "dead"}:
            _remove_npc_poi(scene, npc_id)


def _upsert_npc_poi(
    scene: dict[str, Any],
    npc_id: str,
    name: Any,
    position: dict[str, int],
) -> None:
    pois = scene.setdefault("pois", [])
    for poi in pois:
        if isinstance(poi, dict) and str(poi.get("id") or "") == npc_id:
            poi.update({
                "name": str(name),
                "kind": "npc",
                "icon": "npc",
                "position": position,
            })
            return
    pois.append({
        "id": npc_id,
        "name": str(name),
        "kind": "npc",
        "icon": "npc",
        "position": position,
        "state": "present",
        "visibility": "visible",
        "discovered": True,
    })


def _remove_npc_poi(scene: dict[str, Any], npc_id: str) -> None:
    filtered = []
    for poi in scene.get("pois", []) or []:
        if not isinstance(poi, dict):
            continue
        if str(poi.get("id") or "") == npc_id and str(poi.get("kind") or "").casefold() == "npc":
            continue
        filtered.append(poi)
    scene["pois"] = filtered


def _normalize_poi(
    raw: Any,
    cols: int,
    rows: int,
    *,
    existing: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    poi_id = _clean_text(raw.get("id"), max_len=80)
    if not poi_id:
        return None
    base = dict(existing or {})
    position = _normalize_position(raw.get("position"), cols, rows)
    if position is None and "position" not in base:
        return None
    patch = _normalize_poi_patch(raw, cols, rows)
    patch["id"] = poi_id
    if position is not None:
        patch["position"] = position
    normalized = {**base, **patch}
    normalized.setdefault("name", poi_id)
    normalized.setdefault("kind", "point")
    normalized.setdefault("icon", "marker")
    return normalized


def _normalize_poi_patch(raw: dict[str, Any], cols: int, rows: int) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for field, max_len in _POI_TEXT_FIELDS.items():
        value = _clean_text(raw.get(field), max_len=max_len)
        if not value:
            continue
        if field == "visibility" and value not in _VISIBILITIES:
            continue
        if field == "state" and value not in _DISCOVERY_STATES:
            continue
        patch[field] = value
    if isinstance(raw.get("discovered"), bool):
        patch["discovered"] = raw["discovered"]
    position = _normalize_position(raw.get("position"), cols, rows)
    if position is not None:
        patch["position"] = position
    facts = _normalize_facts(raw.get("facts"))
    if facts:
        patch["facts"] = facts
    if isinstance(raw.get("interactions"), list):
        patch["interactions"] = [item for item in raw["interactions"] if isinstance(item, dict)][:5]
    return patch


def _normalize_element(raw: Any, cols: int, rows: int) -> dict[str, Any] | None:
    element = local_map_service.normalize_scene_element(raw, cols, rows)
    if element is None:
        return None
    patch = _normalize_element_patch(raw, cols, rows) if isinstance(raw, dict) else {}
    return {**element, **patch}


def _normalize_element_patch(raw: dict[str, Any], cols: int, rows: int) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    for field, max_len in _ELEMENT_TEXT_FIELDS.items():
        value = _clean_text(raw.get(field), max_len=max_len)
        if not value:
            continue
        if field == "visibility" and value not in _VISIBILITIES:
            continue
        if field == "state" and value not in _DISCOVERY_STATES:
            continue
        patch[field] = value
    for field in ("blocks_movement", "opaque", "interactive", "discovered"):
        if isinstance(raw.get(field), bool):
            patch[field] = raw[field]
    if isinstance(raw.get("geometry"), dict):
        normalized = local_map_service.normalize_scene_element(
            {**raw, "id": raw.get("id") or "patch_element"},
            cols,
            rows,
        )
        if normalized:
            patch["geometry"] = normalized["geometry"]
    facts = _normalize_facts(raw.get("facts"))
    if facts:
        patch["facts"] = facts
    return patch


def _items(params: dict[str, Any], *keys: str) -> list[Any]:
    for key in keys:
        value = params.get(key)
        if isinstance(value, list):
            return value
    return []


def _normalize_position(position: Any, cols: int, rows: int) -> dict[str, int] | None:
    if not isinstance(position, dict):
        return None
    return {
        "col": _clamp_int(position.get("col"), default=0, minimum=0, maximum=cols - 1),
        "row": _clamp_int(position.get("row"), default=0, minimum=0, maximum=rows - 1),
    }


def _normalize_facts(value: Any) -> list[str]:
    if isinstance(value, str):
        value = [value]
    if not isinstance(value, list):
        return []
    facts = []
    for item in value:
        text = _clean_text(item, max_len=180)
        if text:
            facts.append(text)
    return facts[:12]


def _merged_unique(existing: Any, additions: list[str], *, limit: int) -> list[str]:
    merged: list[str] = []
    for item in list(existing or []) + additions:
        text = _clean_text(item, max_len=220)
        if text and text not in merged:
            merged.append(text)
    return merged[-limit:]


def _clean_text(value: Any, *, max_len: int) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return text[:max_len] if text else ""


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(parsed, maximum))
