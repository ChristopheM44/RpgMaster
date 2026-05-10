"""Execution des actions mecaniques demandees par le MJ.

Ce module ne parle pas au LLM. Il applique les actions structurees deja
produites par le GM agent, publie les evenements mecaniques correspondants et
retourne les jets en attente pour une narration d'outcome.
"""
from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.agents.schemas import AgentResponse, GMResponse
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession
from app.game.state_sync import sync_character_state
from app.services import campaign_dossier_service, map_service

logger = logging.getLogger(__name__)

CANON_DIRTY_ACTIONS = {
    "journal_update",
    "quest_add",
    "chronicle_add",
    "state_transition",
    "social_outcome",
    "region_map_update",
    "city_map_update",
    "node_status_update",
}

SCENE_POI_INTERACTION_INTENTS = {
    "approach",
    "talk",
    "examine",
    "listen",
    "search",
    "use",
    "custom",
}


class GMExecutionResult(BaseModel):
    """Resultat de l'application d'une reponse GM."""

    pending_rolls: list[dict[str, Any]] = Field(default_factory=list)
    executed_actions: list[dict[str, Any]] = Field(default_factory=list)
    canon_dirty: bool = False


class GMResponseExecutor:
    """Applique les actions GM sans appeler le LLM."""

    def __init__(
        self,
        event_bus_instance: Any = event_bus,
        *,
        source: str = "action_pipeline",
    ) -> None:
        self._event_bus = event_bus_instance
        self._source = source

    async def execute_gm_response(
        self,
        response: AgentResponse | GMResponse,
        active: ActiveSession,
        db: Optional[Any] = None,
        *,
        session_id: Optional[str] = None,
        fallback_actor_id: Optional[str] = None,
    ) -> GMExecutionResult:
        """Execute toutes les actions d'une reponse GM.

        ``db`` est requis pour les actions persistantes au niveau campagne
        (cartes region/ville). Les actions qui n'en ont pas besoin l'ignorent.
        """
        result = GMExecutionResult()
        actual_session_id = session_id or active.session_id

        for gm_action in response.actions:
            params: dict[str, Any] = dict(gm_action.params)
            if gm_action.target and "target" not in params:
                params["target"] = gm_action.target

            if gm_action.type == "roll_request":
                roll_evt = self.execute_roll_request(params, fallback_actor_id, active)
                if roll_evt:
                    result.pending_rolls.append(roll_evt)
                    await self._event_bus.publish_to_session(
                        actual_session_id,
                        EventType.ROLL_RESULT,
                        roll_evt,
                        source=self._source,
                    )
                result.executed_actions.append(
                    {"type": gm_action.type, "target": gm_action.target, "params": params}
                )
                continue

            await self.execute_action(
                actual_session_id,
                gm_action.type,
                params,
                active,
                db=db,
            )
            result.executed_actions.append(
                {"type": gm_action.type, "target": gm_action.target, "params": params}
            )
            if gm_action.type in CANON_DIRTY_ACTIONS:
                result.canon_dirty = True

        return result

    def execute_roll_request(
        self,
        params: dict[str, Any],
        fallback_actor_id: Optional[str],
        active: ActiveSession,
    ) -> Optional[dict[str, Any]]:
        """Execute un jet demande par le MJ et retourne un payload ROLL_RESULT."""
        from app.game.roll_executor import execute_roll_request

        return execute_roll_request(params, fallback_actor_id, active)

    async def execute_action(
        self,
        session_id: str,
        action_type: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Optional[Any] = None,
    ) -> None:
        """Applique une action mecanique GM et publie les evenements associes."""
        if action_type == "damage_apply":
            await self._apply_damage(session_id, params, active)
        elif action_type in ("condition_add", "condition_remove", "condition_changed"):
            await self._apply_condition(session_id, action_type, params, active)
        elif action_type == "combatant_status":
            await self._apply_combatant_status(session_id, params, active)
        elif action_type == "encounter_setup":
            self._apply_encounter_setup(params, active)
        elif action_type == "state_transition":
            self._apply_state_transition(params, active)
        elif action_type == "journal_update":
            await self._apply_journal_update(session_id, params, active)
        elif action_type == "quest_add":
            await self._apply_quest_add(session_id, params, active)
        elif action_type == "chronicle_add":
            await self._apply_chronicle_add(session_id, params, active)
        elif action_type == "scene_layout":
            await self._apply_scene_layout(session_id, params, active)
        elif action_type == "social_outcome":
            await self._apply_social_outcome(session_id, params, active)
        elif action_type == "region_map_update":
            await self._apply_region_map_update(session_id, params, active, db)
        elif action_type == "city_map_update":
            await self._apply_city_map_update(session_id, params, active, db)
        elif action_type == "node_status_update":
            await self._apply_node_status_update(session_id, params, active, db)
        else:
            logger.warning("GMResponseExecutor : type d'action GM inconnu '%s'.", action_type)

    async def _apply_damage(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        target_id = params.get("target")
        amount = int(params.get("amount", 0))
        combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
        if not target_id or target_id not in combatants:
            logger.debug("damage_apply : cible '%s' non trouvee dans state_data.", target_id)
            return

        old_hp = int(combatants[target_id].get("hp", 0))
        new_hp = max(0, old_hp - amount)
        combatants[target_id]["hp"] = new_hp
        sync_character_state(active, target_id, hp=new_hp)
        active.mark_dirty()
        await self._event_bus.publish_to_session(
            session_id,
            EventType.HP_CHANGED,
            {"combatant_id": target_id, "delta": -amount, "hp": new_hp},
            source=self._source,
        )

        if new_hp == 0 and combatants[target_id].get("is_player", False):
            cdata = combatants[target_id]
            if "death_saves" not in cdata:
                cdata["death_saves"] = {"successes": 0, "failures": 0, "stable": False}
            conditions = list(cdata.get("conditions", []))
            if "inconscient" not in conditions:
                conditions.append("inconscient")
                cdata["conditions"] = conditions
                sync_character_state(active, target_id, conditions=conditions)
                await self._event_bus.publish_to_session(
                    session_id,
                    EventType.CONDITION_CHANGED,
                    {"combatant_id": target_id, "condition": "inconscient", "added": True},
                    source=self._source,
                )

    async def _apply_condition(
        self,
        session_id: str,
        action_type: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        target_id = params.get("target")
        condition = params.get("condition", "")
        added = bool(params.get("added", True))
        if action_type == "condition_remove":
            added = False
        elif action_type == "condition_add":
            added = True

        combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
        if target_id and target_id in combatants and condition:
            conditions = list(combatants[target_id].get("conditions", []))
            if added and condition not in conditions:
                conditions.append(condition)
            elif not added:
                conditions = [c for c in conditions if c != condition]
            combatants[target_id]["conditions"] = conditions
            sync_character_state(active, target_id, conditions=conditions)
            active.mark_dirty()

        await self._event_bus.publish_to_session(
            session_id,
            EventType.CONDITION_CHANGED,
            {"combatant_id": target_id, "condition": condition, "added": added},
            source=self._source,
        )

    async def _apply_combatant_status(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        target_id = params.get("target")
        status = str(params.get("status", "")).strip().lower()
        reason = str(params.get("reason", status or "resolved"))
        valid_statuses = {"active", "defeated", "surrendered", "fled"}
        if status not in valid_statuses:
            logger.warning(
                "combatant_status ignore : statut invalide '%s' - params=%s",
                status,
                params,
            )
            return

        combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
        if not target_id or target_id not in combatants:
            logger.warning(
                "combatant_status ignore : cible '%s' introuvable - params=%s",
                target_id,
                params,
            )
            return

        combatants[target_id]["status"] = status
        active.mark_dirty()
        await self._event_bus.publish_to_session(
            session_id,
            EventType.COMBATANT_STATUS_CHANGED,
            {
                "combatant_id": target_id,
                "combatant_name": combatants[target_id].get("name", target_id),
                "status": status,
                "reason": reason,
            },
            source=self._source,
        )

    @staticmethod
    def _apply_encounter_setup(params: dict[str, Any], active: ActiveSession) -> None:
        monster_ids = params.get("monster_ids", [])
        context = params.get("context", "")
        if monster_ids:
            active.state_data["pending_encounter"] = {
                "monster_ids": monster_ids,
                "context": context,
            }
            active.mark_dirty()
            logger.info("encounter_setup : pending_encounter defini avec %s", monster_ids)

    @staticmethod
    def _apply_state_transition(params: dict[str, Any], active: ActiveSession) -> None:
        target_phase = (
            params.get("to")
            or params.get("target")
            or params.get("phase")
            or params.get("new_phase")
            or ""
        )
        target_phase = str(target_phase).upper()

        if target_phase == "COMBAT":
            if active.state_data.get("pending_encounter"):
                active.state_data["pending_phase_transition"] = "COMBAT"
                active.mark_dirty()
                logger.info(
                    "state_transition : passage en COMBAT programme (pending_encounter=%s)",
                    active.state_data["pending_encounter"].get("monster_ids"),
                )
            else:
                logger.warning(
                    "state_transition COMBAT ignore : aucun pending_encounter defini "
                    "(le MJ devrait emettre encounter_setup avant state_transition)."
                )
        elif target_phase:
            logger.info(
                "state_transition %s : non implemente (scope actuel : COMBAT uniquement).",
                target_phase,
            )
        else:
            logger.debug("state_transition recue sans phase cible : %s", params)

    async def _apply_journal_update(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        journal: dict[str, Any] = active.state_data.setdefault(
            "adventure_journal",
            {
                "location_region": None,
                "location_place": None,
                "time_of_day": "morning",
                "day_number": 1,
                "calendar_date": None,
                "weather": None,
            },
        )
        for key in (
            "location_region",
            "location_place",
            "time_of_day",
            "day_number",
            "calendar_date",
            "weather",
        ):
            if key in params and params[key] is not None:
                journal[key] = params[key]
        active.mark_dirty()
        await self._event_bus.publish_to_session(
            session_id,
            EventType.JOURNAL_UPDATED,
            {"journal": dict(journal)},
            source=self._source,
        )

    async def _apply_quest_add(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        quest_id = params.get("id")
        if not quest_id:
            logger.warning("quest_add ignore : id manquant - params=%s", params)
            return

        quests: list[dict[str, Any]] = active.state_data.setdefault("quests", [])
        idx = next((i for i, q in enumerate(quests) if q.get("id") == quest_id), -1)
        quest_entry = {
            "id": quest_id,
            "category": params.get("category", "secondaire"),
            "title": params.get("title", quest_id),
            "summary": params.get("summary", ""),
            "urgency": params.get("urgency"),
            "status": params.get("status", "active"),
        }
        if idx >= 0:
            quests[idx] = {**quests[idx], **quest_entry}
        else:
            quests.append(quest_entry)
        active.mark_dirty()
        await self._event_bus.publish_to_session(
            session_id,
            EventType.QUEST_UPDATED,
            {"quests": list(quests)},
            source=self._source,
        )

    async def _apply_chronicle_add(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        chronicle_id = params.get("id")
        kind = params.get("kind")
        if not chronicle_id or kind not in ("npc", "location"):
            logger.warning("chronicle_add ignore : id ou kind invalide - params=%s", params)
            return

        chronicle: list[dict[str, Any]] = active.state_data.setdefault("chronicle", [])
        idx = next((i for i, e in enumerate(chronicle) if e.get("id") == chronicle_id), -1)
        entry = {
            "id": chronicle_id,
            "kind": kind,
            "name": params.get("name", chronicle_id),
            "note": params.get("note", ""),
        }
        if idx >= 0:
            chronicle[idx] = {**chronicle[idx], **entry}
        else:
            chronicle.append(entry)
        active.mark_dirty()
        await self._event_bus.publish_to_session(
            session_id,
            EventType.CHRONICLE_UPDATED,
            {"chronicle": list(chronicle)},
            source=self._source,
        )

    async def _apply_scene_layout(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        layout = self._normalize_scene_layout(params)
        if not layout:
            logger.warning("scene_layout ignore : params invalides - %s", params)
            return

        active.state_data["current_scene"] = layout
        self._register_scene_npcs(layout, active)
        active.mark_dirty()
        await self._event_bus.publish_to_session(
            session_id,
            EventType.SCENE_LAYOUT_CHANGED,
            {"scene": layout},
            source=self._source,
        )

    async def _apply_social_outcome(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        npc_id = str(params.get("npc_id") or params.get("target") or "").strip()
        attitude_shift = str(params.get("attitude_shift") or "").strip().lower()
        note = str(params.get("note") or "").strip()
        new_quest = params.get("new_quest")

        if not npc_id:
            logger.warning("social_outcome ignore : npc_id manquant - params=%s", params)
            return

        npc_states = active.state_data.setdefault("npc_states", {})
        npc = npc_states.setdefault(npc_id, {})
        if isinstance(npc, dict):
            old_attitude = npc.get("attitude", "indifferent")
            if attitude_shift:
                npc["attitude"] = attitude_shift
            if note:
                notes = list(npc.get("notes", []))
                notes.append(note)
                npc["notes"] = notes
            npc["last_interaction_turn"] = active.state_data.get("turn_number", 0)

            if isinstance(new_quest, dict):
                quest_id = str(new_quest.get("id") or "").strip()
                if quest_id:
                    quests: list[dict[str, Any]] = active.state_data.setdefault("quests", [])
                    if not isinstance(quests, list):
                        quests = []
                        active.state_data["quests"] = quests
                    idx = next(
                        (i for i, quest in enumerate(quests) if quest.get("id") == quest_id),
                        -1,
                    )
                    quest_entry = {
                        "id": quest_id,
                        "category": new_quest.get("category", "secondaire"),
                        "title": new_quest.get("title", quest_id),
                        "summary": new_quest.get("summary", ""),
                        "urgency": new_quest.get("urgency"),
                        "status": new_quest.get("status", "active"),
                    }
                    if idx >= 0:
                        quests[idx] = {**quests[idx], **quest_entry}
                    else:
                        quests.append(quest_entry)
            active.mark_dirty()

            payload: dict[str, Any] = {
                "npc_id": npc_id,
                "attitude": npc.get("attitude", old_attitude),
                "note": note,
            }
            if isinstance(new_quest, dict):
                payload["new_quest"] = new_quest

            await self._event_bus.publish_to_session(
                session_id,
                EventType.SOCIAL_OUTCOME,
                payload,
                source=self._source,
            )

    async def _apply_region_map_update(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Optional[Any],
    ) -> None:
        campaign = (
            await campaign_dossier_service.campaign_for_session(session_id, db)
            if db is not None
            else None
        )
        if campaign is not None:
            dossier = await campaign_dossier_service.get_or_create_dossier(campaign.id, db)
            gm_dossier = campaign_dossier_service.sanitize_gm_dossier_map_defaults(
                dossier.gm_dossier or {}
            )
        else:
            gm_dossier = self._state_world_maps(active)

        try:
            region_map = map_service.merge_region_map_patch(
                gm_dossier.get("region_map"),
                params,
            )
        except map_service.MapPatchError as exc:
            logger.warning("region_map_update ignore : patch invalide - %s", exc)
            return

        if campaign is not None:
            dossier = await campaign_dossier_service.update_campaign_maps(
                campaign.id,
                db,
                region_map=region_map,
            )
            public_maps = campaign_dossier_service.public_campaign_maps(dossier.gm_dossier or {})
        else:
            gm_dossier["region_map"] = region_map
            active.state_data["world_maps"] = gm_dossier
            active.mark_dirty()
            public_maps = campaign_dossier_service.public_campaign_maps(gm_dossier)

        await self._event_bus.publish_to_session(
            session_id,
            EventType.REGION_MAP_UPDATED,
            {
                "region_map": public_maps["region_map"],
                "active_city_id": public_maps["active_city_id"],
            },
            source=self._source,
        )

    async def _apply_city_map_update(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Optional[Any],
    ) -> None:
        campaign = (
            await campaign_dossier_service.campaign_for_session(session_id, db)
            if db is not None
            else None
        )
        if campaign is not None:
            dossier = await campaign_dossier_service.get_or_create_dossier(campaign.id, db)
            gm_dossier = campaign_dossier_service.sanitize_gm_dossier_map_defaults(
                dossier.gm_dossier or {}
            )
        else:
            gm_dossier = self._state_world_maps(active)

        city_id = str(params.get("city_id") or "").strip()
        if not city_id:
            logger.warning("city_map_update ignore : city_id manquant - params=%s", params)
            return
        city_maps = dict(gm_dossier.get("city_maps") or {})
        try:
            city_maps[city_id] = map_service.merge_city_map_patch(
                city_maps.get(city_id),
                params,
            )
        except map_service.MapPatchError as exc:
            logger.warning("city_map_update ignore : patch invalide - %s", exc)
            return

        if campaign is not None:
            dossier = await campaign_dossier_service.update_campaign_maps(
                campaign.id,
                db,
                city_maps=city_maps,
                active_city_id=city_id,
            )
            public_maps = campaign_dossier_service.public_campaign_maps(dossier.gm_dossier or {})
        else:
            gm_dossier["city_maps"] = city_maps
            gm_dossier["active_city_id"] = city_id
            active.state_data["world_maps"] = gm_dossier
            active.mark_dirty()
            public_maps = campaign_dossier_service.public_campaign_maps(gm_dossier)

        await self._event_bus.publish_to_session(
            session_id,
            EventType.CITY_MAP_UPDATED,
            {
                "city_map": public_maps["city_maps"].get(city_id),
                "active_city_id": public_maps["active_city_id"],
            },
            source=self._source,
        )

    async def _apply_node_status_update(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Optional[Any],
    ) -> None:
        campaign = (
            await campaign_dossier_service.campaign_for_session(session_id, db)
            if db is not None
            else None
        )
        if campaign is not None:
            dossier = await campaign_dossier_service.get_or_create_dossier(campaign.id, db)
            gm_dossier = campaign_dossier_service.sanitize_gm_dossier_map_defaults(
                dossier.gm_dossier or {}
            )
        else:
            gm_dossier = self._state_world_maps(active)

        scope = str(params.get("scope") or "").strip().lower()

        try:
            if scope == "region":
                region_map = map_service.update_region_node_status(
                    gm_dossier.get("region_map"),
                    params,
                )
                if campaign is not None:
                    dossier = await campaign_dossier_service.update_campaign_maps(
                        campaign.id,
                        db,
                        region_map=region_map,
                    )
                    public_maps = campaign_dossier_service.public_campaign_maps(
                        dossier.gm_dossier or {}
                    )
                else:
                    gm_dossier["region_map"] = region_map
                    active.state_data["world_maps"] = gm_dossier
                    active.mark_dirty()
                    public_maps = campaign_dossier_service.public_campaign_maps(gm_dossier)
                await self._event_bus.publish_to_session(
                    session_id,
                    EventType.REGION_MAP_UPDATED,
                    {
                        "region_map": public_maps["region_map"],
                        "active_city_id": public_maps["active_city_id"],
                    },
                    source=self._source,
                )
                return

            if scope == "city":
                city_id = str(params.get("city_id") or "").strip()
                city_maps = dict(gm_dossier.get("city_maps") or {})
                if not city_id or city_id not in city_maps:
                    logger.warning("node_status_update city ignore : city_id invalide.")
                    return
                city_maps[city_id] = map_service.update_city_node_status(
                    city_maps.get(city_id),
                    params,
                )
                if campaign is not None:
                    dossier = await campaign_dossier_service.update_campaign_maps(
                        campaign.id,
                        db,
                        city_maps=city_maps,
                        active_city_id=city_id,
                    )
                    public_maps = campaign_dossier_service.public_campaign_maps(
                        dossier.gm_dossier or {}
                    )
                else:
                    gm_dossier["city_maps"] = city_maps
                    gm_dossier["active_city_id"] = city_id
                    active.state_data["world_maps"] = gm_dossier
                    active.mark_dirty()
                    public_maps = campaign_dossier_service.public_campaign_maps(gm_dossier)
                await self._event_bus.publish_to_session(
                    session_id,
                    EventType.CITY_MAP_UPDATED,
                    {
                        "city_map": public_maps["city_maps"].get(city_id),
                        "active_city_id": public_maps["active_city_id"],
                    },
                    source=self._source,
                )
                return
        except map_service.MapPatchError as exc:
            logger.warning("node_status_update ignore : patch invalide - %s", exc)
            return

        logger.warning("node_status_update ignore : scope invalide - params=%s", params)

    @staticmethod
    def _state_world_maps(active: ActiveSession) -> dict[str, Any]:
        world_maps = active.state_data.get("world_maps")
        if not isinstance(world_maps, dict):
            world_maps = campaign_dossier_service.empty_world_maps()
        world_maps = campaign_dossier_service.sanitize_gm_dossier_map_defaults(world_maps)
        active.state_data["world_maps"] = world_maps
        return world_maps

    @staticmethod
    def _register_scene_npcs(layout: dict[str, Any], active: ActiveSession) -> None:
        npc_states = active.state_data.setdefault("npc_states", {})
        if not isinstance(npc_states, dict):
            npc_states = {}
            active.state_data["npc_states"] = npc_states

        location = str(
            layout.get("scene_id")
            or layout.get("terrain")
            or active.state_data.get("adventure_journal", {}).get("location_place")
            or ""
        )
        for poi in layout.get("pois", []) or []:
            if not isinstance(poi, dict):
                continue
            kind = str(poi.get("kind") or "").strip().casefold()
            icon = str(poi.get("icon") or "").strip().casefold()
            if kind != "npc" and icon != "npc":
                continue
            npc_id = str(poi.get("id") or "").strip()
            if not npc_id:
                continue
            npc = npc_states.setdefault(npc_id, {})
            if not isinstance(npc, dict):
                npc = {}
                npc_states[npc_id] = npc
            npc.setdefault("name", str(poi.get("name") or npc_id))
            npc.setdefault("attitude", "indifferent")
            npc.setdefault(
                "personality_hint",
                str(poi.get("description") or poi.get("action_hint") or "présence locale"),
            )
            if location:
                npc["last_location"] = location

    @classmethod
    def _normalize_scene_layout(cls, params: dict[str, Any]) -> dict[str, Any]:
        raw = params.get("scene") or params.get("layout") or params
        if not isinstance(raw, dict):
            return {}

        cols = cls._clamp_int(raw.get("cols"), default=8, minimum=3, maximum=24)
        rows = cls._clamp_int(raw.get("rows"), default=8, minimum=3, maximum=24)
        try:
            cell_size_m = float(raw.get("cell_size_m", 1.5))
        except (TypeError, ValueError):
            cell_size_m = 1.5
        cell_size_m = max(0.5, min(cell_size_m, 6.0))

        layout: dict[str, Any] = {
            "cols": cols,
            "rows": rows,
            "cell_size_m": cell_size_m,
            "terrain": str(raw.get("terrain") or "unknown"),
            "pois": [],
            "exits": [],
            "party_positions": {},
        }
        raw_scene_id = cls._clean_optional_text(raw.get("scene_id"), max_len=80)
        if raw_scene_id:
            layout["scene_id"] = raw_scene_id

        for idx, poi in enumerate(raw.get("pois", []) or []):
            if not isinstance(poi, dict):
                continue
            position = cls._normalize_position(poi.get("position"), cols, rows)
            if position is None:
                continue
            poi_id = str(poi.get("id") or f"poi_{idx + 1}")
            normalized_poi = {
                "id": poi_id,
                "name": str(poi.get("name") or poi_id),
                "kind": str(poi.get("kind") or "point"),
                "position": position,
                "icon": str(poi.get("icon") or "marker"),
            }
            description = cls._clean_optional_text(poi.get("description"))
            action_hint = cls._clean_optional_text(poi.get("action_hint"), max_len=140)
            if description:
                normalized_poi["description"] = description
            if action_hint:
                normalized_poi["action_hint"] = action_hint
            interactions = cls._normalize_poi_interactions(poi.get("interactions"))
            if interactions:
                normalized_poi["interactions"] = interactions
            layout["pois"].append(normalized_poi)

        for idx, exit_data in enumerate(raw.get("exits", []) or []):
            if not isinstance(exit_data, dict):
                continue
            position = cls._normalize_position(exit_data.get("position"), cols, rows)
            if position is None:
                continue
            exit_id = str(exit_data.get("id") or f"exit_{idx + 1}")
            normalized_exit = {
                "id": exit_id,
                "label": str(exit_data.get("label") or exit_id),
                "position": position,
                "leads_to": str(exit_data.get("leads_to") or ""),
            }
            description = cls._clean_optional_text(exit_data.get("description"))
            if description:
                normalized_exit["description"] = description
            layout["exits"].append(normalized_exit)

        party_positions = raw.get("party_positions") or {}
        if isinstance(party_positions, dict):
            for char_id, position_data in party_positions.items():
                position = cls._normalize_position(position_data, cols, rows)
                if position is not None:
                    layout["party_positions"][str(char_id)] = position

        layout["pois"] = [
            poi
            for poi in layout["pois"]
            if not cls._is_duplicate_exit_poi(poi, layout["exits"])
        ]

        if "scene_id" not in layout:
            stable_basis = repr((
                layout["cols"],
                layout["rows"],
                layout["terrain"],
                [(poi["id"], poi["position"]) for poi in layout["pois"]],
                [(exit_data["id"], exit_data["position"]) for exit_data in layout["exits"]],
            ))
            layout["scene_id"] = "scene_" + hashlib.sha1(
                stable_basis.encode("utf-8")
            ).hexdigest()[:12]

        return layout

    @classmethod
    def _normalize_poi_interactions(cls, value: Any) -> list[dict[str, Any]]:
        if not isinstance(value, list):
            return []

        interactions: list[dict[str, Any]] = []
        for idx, raw in enumerate(value):
            if not isinstance(raw, dict):
                continue

            label = cls._clean_optional_text(raw.get("label"), max_len=48)
            if not label:
                continue

            intent = str(raw.get("intent") or "custom").strip().lower()
            if intent not in SCENE_POI_INTERACTION_INTENTS:
                intent = "custom"

            interaction: dict[str, Any] = {
                "id": cls._clean_optional_text(raw.get("id"), max_len=48) or f"custom_{idx + 1}",
                "label": label,
                "intent": intent,
            }

            prompt = cls._clean_optional_text(raw.get("prompt"), max_len=180)
            icon = cls._clean_optional_text(raw.get("icon"), max_len=48)
            if prompt:
                interaction["prompt"] = prompt
            if icon:
                interaction["icon"] = icon
            if isinstance(raw.get("default"), bool):
                interaction["default"] = raw["default"]

            interactions.append(interaction)
            if len(interactions) >= 5:
                break

        return interactions

    @classmethod
    def _is_duplicate_exit_poi(
        cls,
        poi: dict[str, Any],
        exits: list[dict[str, Any]],
    ) -> bool:
        if not cls._is_exit_like_scene_poi(poi):
            return False
        return any(
            exit_data.get("id") == poi.get("id")
            or cls._positions_equal(exit_data.get("position"), poi.get("position"))
            for exit_data in exits
        )

    @staticmethod
    def _is_exit_like_scene_poi(poi: dict[str, Any]) -> bool:
        searchable = " ".join(
            str(poi.get(key, ""))
            for key in ("id", "name", "kind", "icon")
        ).casefold()
        normalized = re.sub(r"[^a-z0-9_ -]+", " ", searchable)
        tokens = set(normalized.replace("_", " ").replace("-", " ").split())
        return bool(tokens & {
            "exit",
            "sortie",
            "issue",
            "door",
            "porte",
            "gate",
            "portail",
            "grille",
            "sas",
            "passage",
            "secret",
            "hidden",
            "cache",
        })

    @staticmethod
    def _positions_equal(first: Any, second: Any) -> bool:
        if not isinstance(first, dict) or not isinstance(second, dict):
            return False
        return first.get("col") == second.get("col") and first.get("row") == second.get("row")

    @staticmethod
    def _clean_optional_text(value: Any, max_len: int = 220) -> str:
        if value is None:
            return ""
        text = str(value).strip()
        if not text:
            return ""
        return text[:max_len]

    @staticmethod
    def _normalize_position(
        position: Any,
        cols: int,
        rows: int,
    ) -> Optional[dict[str, int]]:
        if not isinstance(position, dict):
            return None
        return {
            "col": GMResponseExecutor._clamp_int(
                position.get("col"), default=0, minimum=0, maximum=cols - 1
            ),
            "row": GMResponseExecutor._clamp_int(
                position.get("row"), default=0, minimum=0, maximum=rows - 1
            ),
        }

    @staticmethod
    def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            parsed = default
        return max(minimum, min(parsed, maximum))


async def execute_gm_response(
    response: AgentResponse | GMResponse,
    active: ActiveSession,
    db: Optional[Any] = None,
    *,
    session_id: Optional[str] = None,
    fallback_actor_id: Optional[str] = None,
    event_bus_instance: Any = event_bus,
    source: str = "action_pipeline",
) -> GMExecutionResult:
    """Fonction pratique gardant l'API explicite du lot 1.4."""
    executor = GMResponseExecutor(event_bus_instance, source=source)
    return await executor.execute_gm_response(
        response,
        active,
        db,
        session_id=session_id,
        fallback_actor_id=fallback_actor_id,
    )
