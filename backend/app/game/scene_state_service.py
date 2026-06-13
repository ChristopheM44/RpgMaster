"""Scene state source-of-truth helpers.

The local scene is stored inside ``ActiveSession.state_data["current_scene"]``.
This module applies incremental patches to that JSON blob without replacing the
whole layout, so discoveries and party positions can persist like they would at
a real table.
"""

from __future__ import annotations

import logging
from copy import deepcopy
from typing import Any

from app.game.session_manager import ActiveSession
from app.schemas.campaign_content import normalize_content_id
from app.services import local_map_service

logger = logging.getLogger(__name__)

_VISIBILITIES = {"visible", "subtle", "hidden"}
_DISCOVERY_STATES = {"undiscovered", "discovered", "examined", "resolved", "locked", "open"}
_NPC_STATUSES = {"present", "absent", "missing", "hidden", "left", "abducted", "dead"}
# Statuses that pull the NPC off the scene's visible map (POI removed, location cleared).
_DEPARTED_STATUSES = {"absent", "missing", "hidden", "left", "abducted", "dead"}
# Subset meaning the NPC has truly left the party: the P2 guard requires an explicit
# cause before accepting one of these for an ``accompanying`` NPC ("hidden" stays out —
# it is a transient stealth state, not a departure).
_GONE_FROM_PARTY_STATUSES = {"absent", "missing", "left", "abducted", "dead"}
_DISPOSITIONS = {"accompanying", "stationary", "neutral"}

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
    inject_resident_npc_pois(active, updated)
    reconcile_scene_npcs(active, updated)

    journal = active.state_data.get("adventure_journal")
    journal = journal if isinstance(journal, dict) else {}
    time_of_day = journal.get("time_of_day")
    local_map_service.enrich_scene_layout(
        updated,
        time_of_day=str(time_of_day) if time_of_day else None,
    )
    active.state_data["current_scene"] = updated
    active.mark_dirty()
    return updated


def reconcile_scene_npcs(active: ActiveSession, scene: dict[str, Any]) -> None:
    """Project NPC identity from ``npc_states`` (authority) onto scene POIs.

    A single PNJ used to live in up to four places; ``name`` and
    ``known_to_party`` were duplicated between ``npc_states[id]`` and the scene
    POI with no single owner, which let the two diverge (real name leaking to
    companions, stale reveal flags). This function makes ``npc_states[id]`` the
    identity authority and keeps the POI a consistent *projection*:

    - ``known_to_party`` — npc_states wins on conflict; if only the POI carries
      it, npc_states adopts it; both ends converge.
    - ``name`` — npc_states wins when set (so a rename propagates to the visible
      POI); otherwise the POI name seeds npc_states.

    Writers only need to update ``npc_states``; the POI follows on the next
    scene write. Idempotent and side-effect-free beyond the passed scene and
    ``active.state_data['npc_states']``.
    """
    if not isinstance(scene, dict):
        return
    npc_states = active.state_data.setdefault("npc_states", {})
    if not isinstance(npc_states, dict):
        npc_states = {}
        active.state_data["npc_states"] = npc_states

    for poi in scene.get("pois", []) or []:
        if not isinstance(poi, dict):
            continue
        kind = str(poi.get("kind") or "").strip().casefold()
        icon = str(poi.get("icon") or "").strip().casefold()
        if kind != "npc" and icon != "npc":
            continue
        npc_id = str(poi.get("id") or "").strip()
        if not npc_id:
            continue

        npc = npc_states.get(npc_id)
        if not isinstance(npc, dict):
            npc = {}
            npc_states[npc_id] = npc

        # known_to_party: npc_states authority, converge both ends.
        if "known_to_party" in npc:
            resolved_known = bool(npc["known_to_party"])
        elif "known_to_party" in poi:
            resolved_known = bool(poi["known_to_party"])
        else:
            resolved_known = None
        if resolved_known is not None:
            npc["known_to_party"] = resolved_known
            poi["known_to_party"] = resolved_known

        # name: npc_states authority when set, else POI seeds it.
        npc_name = _clean_text(npc.get("name"), max_len=120)
        poi_name = _clean_text(poi.get("name"), max_len=120)
        if npc_name:
            poi["name"] = npc_name
        elif poi_name:
            npc["name"] = poi_name


def carry_accompanying_npcs(
    active: ActiveSession,
    old_scene: dict[str, Any] | None,
    new_layout: dict[str, Any],
) -> None:
    """Carry party-accompanying NPCs across a travel transition.

    When the GM replaces the scene with a ``scene_layout`` for a *different*
    place, NPCs travelling with the party (a hired guide, an escort) must
    follow. Otherwise they vanish silently: the LLM-authored layout rarely
    re-lists them and ``_filter_absent_npc_pois`` would drop them anyway —
    which the GM then rationalises into fiction ("the guide disappeared"), a
    transition artifact that the canon synthesis later freezes as truth.

    Rule: only NPCs explicitly flagged as travelling with the party are carried:
    either ``npc_states[id].disposition == "accompanying"`` or a scene POI carries
    ``disposition="accompanying"`` / ``accompanies_party=true``. Ordinary present
    NPCs (quest-givers, merchants, local witnesses) stay in their scene unless the
    GM or player establishes that they join the group.

    Carried NPCs keep ``status="present"`` and have ``last_location`` moved to
    the new scene so the absence filter keeps them, with a POI injected when the
    layout omits them. No-op when the new layout has no ``scene_id`` or names the
    same place.
    """
    if not isinstance(new_layout, dict):
        return
    new_scene_id = str(new_layout.get("scene_id") or "").strip()
    if not new_scene_id:
        return  # can't tell this is a distinct place — stay conservative
    old_scene_id = (
        str(old_scene.get("scene_id") or "").strip() if isinstance(old_scene, dict) else ""
    )
    if old_scene_id and old_scene_id == new_scene_id:
        return  # same place re-emitted, not a travel transition

    npc_states = active.state_data.setdefault("npc_states", {})
    if not isinstance(npc_states, dict):
        npc_states = {}
        active.state_data["npc_states"] = npc_states

    # NPC ids explicitly travelling from the scene being left.
    candidates: set[str] = set()
    if isinstance(old_scene, dict):
        for poi in old_scene.get("pois", []) or []:
            if not isinstance(poi, dict):
                continue
            poi_id = str(poi.get("id") or "").strip()
            disposition = str(poi.get("disposition") or "").strip().casefold()
            accompanies_party = poi.get("accompanies_party") is True
            if poi_id and (disposition == "accompanying" or accompanies_party):
                candidates.add(poi_id)
    # …plus any NPC already travelling with the party.
    for npc_id, npc in npc_states.items():
        if isinstance(npc, dict) and str(npc.get("disposition") or "").lower() == "accompanying":
            candidates.add(str(npc_id))

    existing_poi_ids = {
        str(poi.get("id") or "").strip()
        for poi in new_layout.get("pois", []) or []
        if isinstance(poi, dict)
    }

    for npc_id in candidates:
        npc = npc_states.get(npc_id)
        if not isinstance(npc, dict):
            continue
        if str(npc.get("disposition") or "").lower() == "stationary":
            continue
        if str(npc.get("status") or "present").lower() in _DEPARTED_STATUSES:
            continue
        # Carry it: travelling with the party, now in the new place.
        npc["status"] = "present"
        npc["disposition"] = "accompanying"
        npc["last_location"] = new_scene_id
        if npc_id in existing_poi_ids:
            continue
        pois = new_layout.setdefault("pois", [])
        if not isinstance(pois, list):
            continue
        pois.append(_make_npc_poi(npc_id, npc, _carry_position(new_layout)))
        existing_poi_ids.add(npc_id)


def inject_resident_npc_pois(active: ActiveSession, layout: dict[str, Any]) -> None:
    """Guarantee a POI for every NPC whose ``npc_states`` says it lives here.

    A resident NPC (``last_location == scene_id``, not departed) that the LLM
    omits from a ``scene_layout`` used to become invisible on the map: nothing
    re-listed it — ``carry_accompanying_npcs`` only covers NPCs travelling with
    the party, and ``_merge_npc_updates`` only upserts a POI when the update
    carries a position. Defensive mirror of the carry rule for stationary or
    local NPCs (the merchant stays visible in his own shop).

    Idempotent: NPCs already present as POIs are left untouched. No-op when the
    layout has no ``scene_id`` (residency can't be attributed).
    """
    if not isinstance(layout, dict):
        return
    scene_id = str(layout.get("scene_id") or "").strip()
    if not scene_id:
        return
    npc_states = active.state_data.get("npc_states")
    if not isinstance(npc_states, dict):
        return
    pois = layout.setdefault("pois", [])
    if not isinstance(pois, list):
        return

    cols = _clamp_int(layout.get("cols"), default=12, minimum=3, maximum=24)
    rows = _clamp_int(layout.get("rows"), default=12, minimum=3, maximum=24)
    existing_poi_ids: set[str] = set()
    taken: set[tuple[int, int]] = set()
    for poi in pois:
        if not isinstance(poi, dict):
            continue
        existing_poi_ids.add(str(poi.get("id") or "").strip())
        position = _normalize_position(poi.get("position"), cols, rows)
        if position is not None:
            taken.add((position["col"], position["row"]))

    for npc_id, npc in sorted(npc_states.items()):
        npc_id = str(npc_id).strip()
        if not npc_id or npc_id in existing_poi_ids or not isinstance(npc, dict):
            continue
        if str(npc.get("status") or "present").lower() in _DEPARTED_STATUSES:
            continue
        if str(npc.get("last_location") or "").strip() != scene_id:
            continue
        position = _normalize_position(npc.get("position"), cols, rows)
        if position is None or (position["col"], position["row"]) in taken:
            position = _free_position_near(_carry_position(layout), taken, cols, rows)
        taken.add((position["col"], position["row"]))
        pois.append(_make_npc_poi(npc_id, npc, position))
        existing_poi_ids.add(npc_id)
        logger.info("scene_layout : PNJ résident réinjecté (id=%s, scene_id=%s)", npc_id, scene_id)


def _make_npc_poi(npc_id: str, npc: dict[str, Any], position: dict[str, int]) -> dict[str, Any]:
    """Visible NPC POI projected from its ``npc_states`` entry (carry/inject shape)."""
    poi: dict[str, Any] = {
        "id": npc_id,
        "name": str(npc.get("name") or npc_id),
        "kind": "npc",
        "icon": "npc",
        "position": position,
        "state": "present",
        "visibility": "visible",
        "discovered": True,
    }
    known = npc.get("known_to_party")
    if isinstance(known, bool):
        poi["known_to_party"] = known
    return poi


def _free_position_near(
    base: dict[str, int],
    taken: set[tuple[int, int]],
    cols: int,
    rows: int,
) -> dict[str, int]:
    """First free cell at growing Chebyshev distance from ``base`` (deterministic scan)."""
    for radius in range(0, max(cols, rows)):
        for row in range(base["row"] - radius, base["row"] + radius + 1):
            for col in range(base["col"] - radius, base["col"] + radius + 1):
                if max(abs(col - base["col"]), abs(row - base["row"])) != radius:
                    continue
                if not (0 <= col < cols and 0 <= row < rows):
                    continue
                if (col, row) not in taken:
                    return {"col": col, "row": row}
    return dict(base)


def _carry_position(layout: dict[str, Any]) -> dict[str, int]:
    """Place a carried NPC next to the party in the new layout, else center."""
    cols = _clamp_int(layout.get("cols"), default=12, minimum=3, maximum=24)
    rows = _clamp_int(layout.get("rows"), default=12, minimum=3, maximum=24)
    party = layout.get("party_positions")
    if isinstance(party, dict):
        for raw_position in party.values():
            position = _normalize_position(raw_position, cols, rows)
            if position is not None:
                return {"col": min(position["col"] + 1, cols - 1), "row": position["row"]}
    return {"col": cols // 2, "row": rows // 2}


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

        disposition = _clean_text(raw.get("disposition"), max_len=20).lower()
        if disposition in _DISPOSITIONS:
            npc["disposition"] = disposition

        note = _clean_text(raw.get("note"), max_len=240)
        cause = note or _clean_text(raw.get("reason") or raw.get("cause"), max_len=240)

        status = _clean_text(raw.get("status"), max_len=32).lower()
        remove_poi = False
        if status in _NPC_STATUSES:
            current_disposition = str(npc.get("disposition") or "").lower()
            # P2 guard: an accompanying NPC cannot leave the party without an
            # explicit narrative cause — this blocks a transition artifact from
            # being frozen as "the guide vanished". A genuine departure just has
            # to say why (note/reason).
            blocked = (
                status in _GONE_FROM_PARTY_STATUSES
                and current_disposition == "accompanying"
                and not cause
            )
            if blocked:
                logger.warning(
                    "npc_update: départ '%s' ignoré pour PNJ accompagnant '%s' sans cause "
                    "explicite (anti-contamination)",
                    status,
                    npc_id,
                )
            else:
                npc["status"] = status
                if status == "present":
                    npc["last_location"] = (
                        _clean_text(raw.get("last_location"), max_len=80) or scene_id
                    )
                elif status in _DEPARTED_STATUSES:
                    npc["last_location"] = _clean_text(raw.get("last_location"), max_len=80) or ""
                    remove_poi = True
                    # a caused departure ends the accompanying state
                    if (
                        current_disposition == "accompanying"
                        and status in _GONE_FROM_PARTY_STATUSES
                    ):
                        npc["disposition"] = "neutral"

        if isinstance(raw.get("known_to_party"), bool):
            npc["known_to_party"] = raw["known_to_party"]
        if note:
            npc["notes"] = _merged_unique(npc.get("notes"), [note], limit=12)
        position = _normalize_position(raw.get("position"), int(scene["cols"]), int(scene["rows"]))
        if position is not None:
            npc["position"] = position
            _upsert_npc_poi(
                scene,
                npc_id,
                npc.get("name") or npc_id,
                position,
                known_to_party=npc.get("known_to_party"),
            )
        if remove_poi:
            _remove_npc_poi(scene, npc_id)


def _upsert_npc_poi(
    scene: dict[str, Any],
    npc_id: str,
    name: Any,
    position: dict[str, int],
    *,
    known_to_party: bool | None = None,
) -> None:
    pois = scene.setdefault("pois", [])
    for poi in pois:
        if isinstance(poi, dict) and str(poi.get("id") or "") == npc_id:
            poi.update(
                {
                    "name": str(name),
                    "kind": "npc",
                    "icon": "npc",
                    "position": position,
                }
            )
            if known_to_party is not None:
                poi["known_to_party"] = known_to_party
            return
    new_poi: dict[str, Any] = {
        "id": npc_id,
        "name": str(name),
        "kind": "npc",
        "icon": "npc",
        "position": position,
        "state": "present",
        "visibility": "visible",
        "discovered": True,
    }
    if known_to_party is not None:
        new_poi["known_to_party"] = known_to_party
    pois.append(new_poi)


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
    poi_id = normalize_content_id(raw.get("id"), max_len=80)
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
    if isinstance(raw.get("known_to_party"), bool):
        patch["known_to_party"] = raw["known_to_party"]
    position = _normalize_position(raw.get("position"), cols, rows)
    if position is not None:
        patch["position"] = position
    facts = _normalize_facts(raw.get("facts"))
    if facts:
        patch["facts"] = facts
    if isinstance(raw.get("interactions"), list):
        interactions: list[dict[str, Any]] = []
        for idx, item in enumerate(raw["interactions"]):
            if not isinstance(item, dict):
                continue
            entry = dict(item)
            entry["id"] = normalize_content_id(entry.get("id"), max_len=48) or f"custom_{idx + 1}"
            interactions.append(entry)
            if len(interactions) >= 5:
                break
        patch["interactions"] = interactions
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
