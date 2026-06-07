"""Execution des actions mecaniques demandees par le MJ.

Ce module ne parle pas au LLM. Il applique les actions structurees deja
produites par le GM agent, publie les evenements mecaniques correspondants et
retourne les jets en attente pour une narration d'outcome.
"""

from __future__ import annotations

import hashlib
import logging
import re
import uuid
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select

from app.agents.schemas import AgentResponse, GMResponse
from app.config import (
    get_image_generation_enabled,
    get_image_model,
    get_image_provider,
)
from app.engine.srd_data import find_equipment
from app.game import companion_refs
from app.game.event_bus import EventType, event_bus
from app.game.scene_theme import coerce_scene_theme
from app.game.session_manager import ActiveSession
from app.game.social_resolution import SocialResolution
from app.game.social_scene_state import enrich_scene_poi_mechanics, start_scene_clock
from app.game.state_sync import sync_character_state
from app.logging_utils import log_degraded
from app.models.character import Character
from app.schemas.campaign_content import normalize_content_id
from app.schemas.equipment import validate_equipment_item
from app.services import campaign_dossier_service, local_map_service, map_service
from app.services.currency_service import currency_service
from app.services.equipment_service import EquipmentService
from app.services.xp_service import xp_service

logger = logging.getLogger(__name__)

# Progression naturelle du Moment dans la journée.
# Utilisé quand un changement de lieu est détecté sans que le MJ n'ait
# explicitement mis à jour l'heure.
_TIME_OF_DAY_NEXT: dict[str, str] = {
    "dawn": "morning",
    "morning": "afternoon",
    "afternoon": "dusk",
    "dusk": "night",
    "night": "dawn",
}

# Limites de longueur de texte pour la normalisation des scènes MJ
_SCENE_DESCRIPTION_MAX_LEN = 1500  # description principale d'une scène (était 320)
_POI_ACTION_HINT_MAX_LEN = 300  # hint d'action d'un POI (était 140)
_POI_PROMPT_MAX_LEN = 400  # prompt d'une interaction POI (était 180)

CANON_DIRTY_ACTIONS = {
    "journal_update",
    "quest_add",
    "chronicle_add",
    "state_transition",
    "social_outcome",
    "clock_start",
    "scene_update",
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

REWARD_ACTIONS_REQUIRING_AUTHORITY = {"currency_grant", "loot_grant", "xp_grant"}
DIRECT_EFFECT_ACTIONS_REQUIRING_RESOLUTION = {"damage_apply", "combatant_status"}
REWARD_AUTHORITY_MARKERS = (
    "récompense",
    "recompense",
    "butin",
    "trésor",
    "tresor",
    "coffre",
    "bourse",
    "pièce",
    "piece",
    "pièces d'or",
    "pieces d'or",
    "potion",
    "vous trouvez",
    "vous ramassez",
    "vous gagnez",
    "vous recevez",
)


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
        db: Any | None = None,
        *,
        session_id: str | None = None,
        fallback_actor_id: str | None = None,
        social_roll_results: dict[str, Any] | None = None,
        provenance_context: dict[str, Any] | None = None,
    ) -> GMExecutionResult:
        """Execute toutes les actions d'une reponse GM.

        ``db`` est requis pour les actions persistantes au niveau campagne
        (cartes region/ville). Les actions qui n'en ont pas besoin l'ignorent.
        """
        result = GMExecutionResult()
        actual_session_id = session_id or active.session_id
        social_context = SocialResolution.roll_context(social_roll_results)
        social_outcome_targets: set[str] = set()

        for gm_action in response.actions:
            params: dict[str, Any] = dict(gm_action.params)
            if gm_action.target and "target" not in params:
                params["target"] = gm_action.target

            if not self._action_has_trusted_authority(
                gm_action.type,
                params,
                active,
                provenance_context,
                social_roll_results=social_roll_results,
            ):
                logger.warning(
                    "GMResponseExecutor : action sensible ignoree faute d'autorite "
                    "canonique (%s, params=%s).",
                    gm_action.type,
                    params,
                )
                continue

            if gm_action.type == "roll_request":
                # Si le MJ n'a pas désigné de cible et que l'action joueur adresse un
                # compagnon (« @shade examine… »), le jet revient à CE compagnon, pas à
                # l'humain émetteur (bug #3). Même détecteur que le routage de narration.
                roll_fallback = fallback_actor_id
                if not params.get("target"):
                    player_action = str((provenance_context or {}).get("player_action") or "")
                    addressed = companion_refs.find_mentioned_companion(
                        player_action,
                        companion_refs.companion_index(active),
                    )
                    if addressed:
                        roll_fallback = addressed
                roll_evt = self.execute_roll_request(params, roll_fallback, active)
                if roll_evt:
                    result.pending_rolls.append(roll_evt)
                    await self._event_bus.publish_to_session(
                        actual_session_id,
                        EventType.ROLL_RESULT,
                        roll_evt,
                        source=self._source,
                    )
                    from app.services.message_service import persist_roll_result

                    await persist_roll_result(actual_session_id, roll_evt, db)
                result.executed_actions.append(
                    {"type": gm_action.type, "target": gm_action.target, "params": params}
                )
                continue

            if gm_action.type == "stealth_event":
                stealth_evt = self._resolve_stealth_event(params, active)
                result.pending_rolls.append(stealth_evt)
                if stealth_evt.get("stealth_succeeded") and await self._apply_stealth_success(
                    actual_session_id,
                    params,
                    active,
                ):
                    result.canon_dirty = True
                result.executed_actions.append(
                    {"type": gm_action.type, "target": gm_action.target, "params": params}
                )
                continue

            if gm_action.type == "social_outcome":
                applied_npc_id = await self._apply_social_outcome(
                    actual_session_id,
                    params,
                    active,
                    social_roll_results=social_roll_results,
                )
                if applied_npc_id:
                    social_outcome_targets.add(applied_npc_id)
            else:
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

        if social_context and social_context.target_id not in social_outcome_targets:
            if await self._apply_default_social_outcome(
                actual_session_id,
                social_context.target_id,
                active,
                social_roll_results,
            ):
                result.canon_dirty = True

        return result

    def _action_has_trusted_authority(
        self,
        action_type: str,
        params: dict[str, Any],
        active: ActiveSession,
        provenance_context: dict[str, Any] | None,
        *,
        social_roll_results: dict[str, Any] | None,
    ) -> bool:
        """Refuse sensitive mutations when the player assertion is the only source."""
        if provenance_context is None:
            return True

        if action_type in REWARD_ACTIONS_REQUIRING_AUTHORITY:
            return self._reward_has_trusted_source(action_type, params, active, provenance_context)

        if action_type in DIRECT_EFFECT_ACTIONS_REQUIRING_RESOLUTION:
            return self._direct_effect_has_resolution(
                action_type,
                provenance_context,
                social_roll_results=social_roll_results,
            )

        return True

    def _reward_has_trusted_source(
        self,
        action_type: str,
        params: dict[str, Any],
        active: ActiveSession,
        provenance_context: dict[str, Any],
    ) -> bool:
        del params
        phase = self._phase_name(provenance_context.get("phase") or active.phase)
        if phase == "ENCOUNTER_END":
            return True

        if action_type in {"currency_grant", "loot_grant"} and self._scene_has_loot_source(active):
            return True

        if self._recent_gm_text_establishes_reward(provenance_context):
            return True

        return False

    def _direct_effect_has_resolution(
        self,
        action_type: str,
        provenance_context: dict[str, Any],
        *,
        social_roll_results: dict[str, Any] | None,
    ) -> bool:
        if action_type == "damage_apply" and self._has_resolved_roll(provenance_context):
            return True
        if action_type == "combatant_status" and (
            social_roll_results or self._has_resolved_roll(provenance_context)
        ):
            return True
        return False

    @staticmethod
    def _phase_name(value: Any) -> str:
        raw = getattr(value, "name", None) or getattr(value, "value", None) or value
        return str(raw or "").strip().upper()

    @staticmethod
    def _has_resolved_roll(provenance_context: dict[str, Any]) -> bool:
        roll_results = provenance_context.get("roll_results")
        if isinstance(roll_results, dict):
            return bool(roll_results)
        if isinstance(roll_results, list):
            return bool(roll_results)
        return False

    @staticmethod
    def _scene_has_loot_source(active: ActiveSession) -> bool:
        scene = active.state_data.get("current_scene")
        if not isinstance(scene, dict):
            return False
        for poi in scene.get("pois", []) or []:
            if not isinstance(poi, dict):
                continue
            kind = str(poi.get("kind") or "").strip().lower()
            icon = str(poi.get("icon") or "").strip().lower()
            if kind == "loot" or icon == "chest":
                return True
        return False

    @staticmethod
    def _recent_gm_text_establishes_reward(provenance_context: dict[str, Any]) -> bool:
        for message in provenance_context.get("recent_messages") or []:
            role = ""
            content = ""
            if isinstance(message, dict):
                role = str(message.get("role") or "").strip().lower()
                content = str(message.get("content") or "")
            else:
                role_value = getattr(message, "role", "")
                role = str(getattr(role_value, "value", role_value) or "").strip().lower()
                content = str(getattr(message, "content", "") or "")
            if role != "gm":
                continue
            normalized = content.casefold()
            if any(marker in normalized for marker in REWARD_AUTHORITY_MARKERS):
                return True
        return False

    def execute_roll_request(
        self,
        params: dict[str, Any],
        fallback_actor_id: str | None,
        active: ActiveSession,
    ) -> dict[str, Any] | None:
        """Execute un jet demande par le MJ et retourne un payload ROLL_RESULT."""
        from app.game.roll_executor import execute_roll_request

        return execute_roll_request(params, fallback_actor_id, active)

    @staticmethod
    def _resolve_stealth_event(
        params: dict[str, Any],
        active: ActiveSession,
    ) -> dict[str, Any]:
        from app.game.stealth_resolution import resolve_stealth_event

        return resolve_stealth_event(active, params)

    async def _apply_stealth_success(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> bool:
        raw_targets = params.get("target_npc_ids") or params.get("target_npc_id")
        if isinstance(raw_targets, str):
            target_ids = [raw_targets]
        elif isinstance(raw_targets, list):
            target_ids = [
                str(item).strip() for item in raw_targets if item is not None and str(item).strip()
            ]
        else:
            target_ids = []
        if not target_ids:
            return False

        event_type = str(params.get("event_type") or "").strip().lower()
        status = str(params.get("npc_status_on_success") or "").strip().lower()
        if not status:
            status = {
                "abduction": "abducted",
                "escape": "missing",
                "hide": "hidden",
                "move_unnoticed": "hidden",
            }.get(event_type, "missing")
        if status not in {"missing", "hidden", "abducted", "absent", "left"}:
            status = "missing"

        note = str(params.get("note_on_success") or params.get("note") or "").strip()
        npc_updates = [
            {
                "id": npc_id,
                "status": status,
                **({"note": note} if note else {}),
            }
            for npc_id in target_ids
        ]
        before = active.state_data.get("current_scene")
        await self._apply_scene_update(
            session_id,
            {"npc_updates": npc_updates},
            active,
        )
        return isinstance(before, dict)

    async def execute_action(
        self,
        session_id: str,
        action_type: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Any | None = None,
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
        elif action_type == "scene_update":
            await self._apply_scene_update(session_id, params, active)
        elif action_type == "scene_progress_update":
            await self._apply_scene_progress_update(session_id, params, active)
        elif action_type == "revelation":
            await self._apply_revelation(session_id, params, active, db)
        elif action_type == "social_outcome":
            await self._apply_social_outcome(session_id, params, active)
        elif action_type == "clock_start":
            await start_scene_clock(
                session_id=session_id,
                active=active,
                event_bus=self._event_bus,
                params=params,
                source=self._source,
            )
        elif action_type == "region_map_update":
            await self._apply_region_map_update(session_id, params, active, db)
        elif action_type == "city_map_update":
            await self._apply_city_map_update(session_id, params, active, db)
        elif action_type == "node_status_update":
            await self._apply_node_status_update(session_id, params, active, db)
        elif action_type == "xp_grant":
            await self._apply_xp_grant(session_id, params, active, db)
        elif action_type == "currency_grant":
            await self._apply_currency_grant(session_id, params, active, db)
        elif action_type == "currency_spend":
            await self._apply_currency_spend(session_id, params, active, db)
        elif action_type == "loot_grant":
            await self._apply_loot_grant(session_id, params, active, db)
        elif action_type == "item_remove":
            await self._apply_item_remove(session_id, params, active, db)
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
                "location_venue": None,
                "time_of_day": "morning",
                "day_number": 1,
                "calendar_date": None,
                "weather": None,
            },
        )
        # Sauvegarder l'ancien lieu pour détecter un changement de localisation
        old_place = str(journal.get("location_place") or "").strip()
        old_venue = str(journal.get("location_venue") or "").strip()

        for key in (
            "location_region",
            "location_place",
            "location_venue",
            "time_of_day",
            "day_number",
            "calendar_date",
            "weather",
        ):
            if key in params and params[key] is not None:
                journal[key] = params[key]

        # Si le lieu a changé mais que l'heure n'a pas été mise à jour par le MJ,
        # avancer automatiquement le Moment d'un cran.
        new_place = str(journal.get("location_place") or "").strip()
        new_venue = str(journal.get("location_venue") or "").strip()
        location_changed = (old_place != new_place) or (old_venue != new_venue)
        time_was_updated = "time_of_day" in params

        if location_changed and not time_was_updated:
            current_time = str(journal.get("time_of_day", "morning")).strip().lower()
            next_time = _TIME_OF_DAY_NEXT.get(current_time, "afternoon")
            journal["time_of_day"] = next_time
            if next_time == "dawn":
                journal["day_number"] = int(journal.get("day_number", 1)) + 1

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

    async def _apply_revelation(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Any | None,
    ) -> None:
        """Record a secret revealed in play, deterministically and immediately.

        Until now ``revealed_secrets`` was only ever populated *a posteriori* by
        the LLM canon synthesis, so the trace could lag a whole pass or hallucinate.
        This action writes the secret the moment the GM reveals it, into both
        readers of ``revealed_secrets``:

        - the in-session mirror ``campaign_context.played_canon`` (companion view),
        - the authoritative ``CampaignDossier.played_canon`` in DB (GM prompt view).

        Like ``scene_progress_update`` it is GM-only and publishes no player event.
        Surfacing revelations to the human player is a separate product decision.
        """
        del session_id
        if not isinstance(params, dict):
            return
        secret = str(params.get("secret") or params.get("text") or "").strip()
        if not secret:
            logger.warning("revelation ignore : 'secret' vide - params=%s", params)
            return
        secret = secret[:600]

        # 1) In-session mirror — read by the companion-visible filter.
        context = active.state_data.get("campaign_context")
        if isinstance(context, dict):
            canon = context.setdefault("played_canon", {})
            if not isinstance(canon, dict):
                canon = {}
                context["played_canon"] = canon
            revealed = list(canon.get("revealed_secrets") or [])
            if secret not in revealed:
                revealed.append(secret)
            canon["revealed_secrets"] = revealed
            active.mark_dirty()

        # 2) Authoritative DB dossier — read by build_gm_prompt_context.
        if db is None:
            return
        try:
            await campaign_dossier_service.record_revealed_secret(
                self._campaign_id(active),
                secret,
                db,
            )
        except Exception as exc:
            log_degraded(logger, "revelation (persistance dossier)", exc)

    async def _apply_scene_progress_update(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        """Store GM-only objective progress for the current scene.

        The state is intentionally internal: no event is published to players.
        """
        del session_id
        if not isinstance(params, dict):
            return

        scene_state = active.state_data.get("gm_scene_state")
        if not isinstance(scene_state, dict):
            scene_state = {}
            active.state_data["gm_scene_state"] = scene_state

        current_scene = active.state_data.get("current_scene")
        if not isinstance(current_scene, dict):
            current_scene = {}
        scene_id = (
            str(
                params.get("scene_id")
                or current_scene.get("scene_id")
                or current_scene.get("id")
                or "current"
            ).strip()
            or "current"
        )

        scene_entry = scene_state.get(scene_id)
        if not isinstance(scene_entry, dict):
            scene_entry = {"scene_id": scene_id, "obstacles": {}}
            scene_state[scene_id] = scene_entry
        scene_entry.setdefault("scene_id", scene_id)
        obstacles = scene_entry.get("obstacles")
        if not isinstance(obstacles, dict):
            obstacles = {}
            scene_entry["obstacles"] = obstacles

        self._merge_progress_fields(
            scene_entry,
            params,
            {
                "goal": ("goal", "scene_goal", "objective"),
                "status": ("status", "scene_status"),
                "summary": ("summary", "scene_summary"),
                "progress": ("progress", "scene_progress"),
                "max_progress": ("max_progress", "scene_max_progress"),
                "approaches": ("approaches", "visible_options", "options"),
                "revelations": ("revelations",),
                "failure_costs": ("failure_costs", "costs_on_failure"),
                "success_outcome": ("success_outcome", "outcome_on_success"),
                "next_hooks": ("next_hooks", "hooks"),
                "notes": ("notes", "gm_notes"),
            },
        )

        obstacle_inputs: list[dict[str, Any]] = []
        raw_obstacles = params.get("obstacles")
        if isinstance(raw_obstacles, list):
            obstacle_inputs.extend(item for item in raw_obstacles if isinstance(item, dict))
        if any(
            key in params
            for key in (
                "obstacle_id",
                "id",
                "name",
                "linked_poi_id",
                "failure_costs",
                "success_outcome",
            )
        ):
            obstacle_inputs.append(params)

        for obstacle_data in obstacle_inputs:
            obstacle_id = (
                str(
                    obstacle_data.get("obstacle_id")
                    or obstacle_data.get("id")
                    or obstacle_data.get("linked_poi_id")
                    or obstacle_data.get("name")
                    or "main"
                ).strip()
                or "main"
            )
            obstacle_entry = obstacles.get(obstacle_id)
            if not isinstance(obstacle_entry, dict):
                obstacle_entry = {"id": obstacle_id}
                obstacles[obstacle_id] = obstacle_entry
            obstacle_entry.setdefault("id", obstacle_id)
            self._merge_progress_fields(
                obstacle_entry,
                obstacle_data,
                {
                    "name": ("name", "label"),
                    "status": ("status",),
                    "progress": ("progress",),
                    "max_progress": ("max_progress",),
                    "approaches": ("approaches", "visible_options", "options"),
                    "revelations": ("revelations",),
                    "failure_costs": ("failure_costs", "costs_on_failure"),
                    "success_outcome": ("success_outcome", "outcome_on_success"),
                    "linked_poi_id": ("linked_poi_id", "poi_id"),
                    "notes": ("notes", "gm_notes"),
                },
            )

        active.mark_dirty()

    @staticmethod
    def _merge_progress_fields(
        target: dict[str, Any],
        source: dict[str, Any],
        aliases: dict[str, tuple[str, ...]],
    ) -> None:
        for output_key, input_keys in aliases.items():
            for input_key in input_keys:
                if input_key not in source:
                    continue
                value = source.get(input_key)
                if value in (None, ""):
                    continue
                target[output_key] = value
                break

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

        from app.game.scene_state_service import (
            carry_accompanying_npcs,
            reconcile_scene_npcs,
        )

        old_scene = active.state_data.get("current_scene")
        enrich_scene_poi_mechanics(layout)
        # Carry party-accompanying NPCs (a guide/escort) into the new place before
        # the absence filter runs, so a travel transition can't silently drop them.
        carry_accompanying_npcs(active, old_scene, layout)
        self._filter_absent_npc_pois(layout, active)
        active.state_data["current_scene"] = layout
        self._register_scene_npcs(layout, active)
        reconcile_scene_npcs(active, layout)
        active.mark_dirty()
        await self._event_bus.publish_to_session(
            session_id,
            EventType.SCENE_LAYOUT_CHANGED,
            {"scene": layout},
            source=self._source,
        )
        self._trigger_visual_asset_generation(session_id, layout, scope="scene")

    async def _apply_scene_update(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        from app.game.scene_state_service import apply_scene_update

        scene = apply_scene_update(active, params)
        if scene is None:
            logger.warning("scene_update ignore : aucune current_scene - %s", params)
            return
        await self._event_bus.publish_to_session(
            session_id,
            EventType.SCENE_LAYOUT_CHANGED,
            {"scene": scene},
            source=self._source,
        )

    async def _apply_social_outcome(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        *,
        social_roll_results: dict[str, Any] | None = None,
    ) -> str | None:
        npc_id = str(params.get("npc_id") or params.get("target") or "").strip()
        raw_attitude_shift = params.get("attitude_shift")
        attitude_shift = str(raw_attitude_shift or "").strip().lower()
        note = str(params.get("note") or "").strip()
        new_quest = params.get("new_quest")
        roll_context = SocialResolution.roll_context(social_roll_results)

        if not npc_id:
            logger.warning("social_outcome ignore : npc_id manquant - params=%s", params)
            return None
        if roll_context and npc_id != roll_context.target_id:
            logger.warning(
                "social_outcome ignore : PNJ '%s' different de la cible sociale '%s'",
                npc_id,
                roll_context.target_id,
            )
            return None

        npc_states = active.state_data.setdefault("npc_states", {})
        npc = npc_states.setdefault(npc_id, {})
        if isinstance(npc, dict):
            old_attitude = npc.get("attitude", "indifferent")
            clamped = False
            if attitude_shift:
                if roll_context:
                    next_attitude, clamped = SocialResolution.bounded_attitude(
                        old_attitude,
                        attitude_shift,
                        success=roll_context.success,
                    )
                else:
                    valid_attitudes = {
                        "hostile",
                        "unfriendly",
                        "indifferent",
                        "friendly",
                        "helpful",
                    }
                    next_attitude = (
                        attitude_shift
                        if attitude_shift in valid_attitudes
                        else SocialResolution.normalize_attitude(old_attitude)
                    )
                    clamped = next_attitude != attitude_shift
                npc["attitude"] = next_attitude
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

            payload = SocialResolution.outcome_payload(
                npc_id=npc_id,
                previous_attitude=old_attitude,
                attitude=SocialResolution.normalize_attitude(npc.get("attitude", old_attitude)),
                note=note,
                roll_context=roll_context,
                clamped=clamped,
                source="llm_bounded" if roll_context else "llm",
                new_quest=new_quest if isinstance(new_quest, dict) else None,
            )

            await self._event_bus.publish_to_session(
                session_id,
                EventType.SOCIAL_OUTCOME,
                payload,
                source=self._source,
            )
            return npc_id
        return None

    async def _apply_default_social_outcome(
        self,
        session_id: str,
        npc_id: str,
        active: ActiveSession,
        social_roll_results: dict[str, Any],
    ) -> bool:
        roll_context = SocialResolution.roll_context(social_roll_results)
        if roll_context is None:
            return False

        npc_states = active.state_data.setdefault("npc_states", {})
        if not isinstance(npc_states, dict):
            npc_states = {}
            active.state_data["npc_states"] = npc_states
        npc = npc_states.setdefault(npc_id, {})
        if not isinstance(npc, dict):
            npc = {}
            npc_states[npc_id] = npc

        old_attitude = npc.get("attitude", "indifferent")
        next_attitude = SocialResolution.default_attitude(
            old_attitude,
            success=roll_context.success,
        )
        npc.setdefault("name", npc_id)
        npc["attitude"] = next_attitude
        npc["last_interaction_turn"] = active.state_data.get("turn_number", 0)
        active.mark_dirty()

        await self._event_bus.publish_to_session(
            session_id,
            EventType.SOCIAL_OUTCOME,
            SocialResolution.outcome_payload(
                npc_id=npc_id,
                previous_attitude=old_attitude,
                attitude=next_attitude,
                roll_context=roll_context,
                clamped=False,
                source="engine_default",
            ),
            source=self._source,
        )
        return True

    async def _apply_region_map_update(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Any | None,
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
        self._ensure_map_visual_asset(region_map, map_kind="region")

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
        self._trigger_visual_asset_generation(session_id, region_map, scope="region")

    async def _apply_city_map_update(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Any | None,
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
        self._ensure_map_visual_asset(city_maps[city_id], map_kind="city")

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
        self._trigger_visual_asset_generation(session_id, city_maps.get(city_id, {}), scope="city")

    async def _apply_node_status_update(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Any | None,
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

    async def _apply_xp_grant(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Any | None,
    ) -> None:
        if db is None:
            logger.warning("xp_grant ignore : db requis.")
            return
        amount = self._safe_non_negative_int(params.get("amount"))
        if amount <= 0:
            logger.warning("xp_grant ignore : amount invalide - params=%s", params)
            return
        target = str(params.get("target") or "").strip()
        targets = self._xp_targets(target, active)
        if not targets:
            logger.warning("xp_grant ignore : cible invalide '%s'.", target)
            return
        for character_id in targets:
            await xp_service.grant_xp(
                session_id=session_id,
                character_id=character_id,
                amount=amount,
                db=db,
                active=active,
            )

    async def _apply_currency_grant(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Any | None,
    ) -> None:
        if db is None:
            logger.warning("currency_grant ignore : db requis.")
            return
        target = str(params.get("target") or "").strip()
        if not target or target == "party":
            logger.warning("currency_grant ignore : cible personnage concrete requise.")
            return
        gp, sp, cp = self._coin_params(params)
        if min(gp, sp, cp) < 0:
            logger.warning("currency_grant ignore : valeurs negatives interdites.")
            return
        await currency_service.grant_currency(
            session_id=session_id,
            character_id=target,
            gp=gp,
            sp=sp,
            cp=cp,
            db=db,
            active=active,
        )

    async def _apply_currency_spend(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Any | None,
    ) -> None:
        if db is None:
            logger.warning("currency_spend ignore : db requis.")
            return
        target = str(params.get("target") or "").strip()
        if not target or target == "party":
            logger.warning("currency_spend ignore : cible personnage concrete requise.")
            return
        if params.get("cost_gp") is not None:
            cost_gp: Any = params.get("cost_gp")
        else:
            gp, sp, cp = self._coin_params(params)
            cost_gp = Decimal(gp) + Decimal(sp) / Decimal(10) + Decimal(cp) / Decimal(100)
        await currency_service.spend_currency(
            session_id=session_id,
            character_id=target,
            cost_gp=cost_gp,
            db=db,
            active=active,
        )

    async def _apply_loot_grant(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Any | None,
    ) -> None:
        if db is None:
            logger.warning("loot_grant ignore : db requis.")
            return
        target = str(params.get("target") or "").strip()
        if not target or target == "party":
            logger.warning("loot_grant ignore : cible personnage concrete requise.")
            return
        result = await db.execute(select(Character).where(Character.id == target))
        char = result.scalar_one_or_none()
        if char is None:
            logger.warning("loot_grant ignore : personnage '%s' introuvable.", target)
            return
        equipment = list(char.equipment or [])
        raw_items = params.get("items") or []
        if isinstance(raw_items, dict):
            raw_items = [raw_items]
        custom_items = self._custom_items_by_id(active)
        granted_unique = self._granted_unique_items(active)
        added: list[dict[str, Any]] = []
        unique_granted_now: list[str] = []
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            template_id = normalize_content_id(raw.get("template_id") or raw.get("id"))
            if not template_id:
                continue
            custom_template = custom_items.get(template_id)
            if custom_template and bool(custom_template.get("unique")):
                if template_id in granted_unique:
                    logger.warning(
                        "loot_grant ignore : objet unique deja attribue '%s'.",
                        template_id,
                    )
                    continue
                granted_unique.add(template_id)
                unique_granted_now.append(template_id)
            try:
                item = self._instantiate_loot_item(template_id, raw, custom_template)
            except KeyError:
                logger.warning("loot_grant ignore : template inconnu '%s'.", template_id)
                continue
            equipment.append(item)
            added.append(item)
        if not added:
            return
        char.equipment = equipment
        await db.commit()
        await db.refresh(char)
        if unique_granted_now:
            self._mark_unique_items_in_state(active, unique_granted_now)
            campaign_id = self._campaign_id(active)
            if campaign_id:
                await campaign_dossier_service.record_granted_unique_items(
                    campaign_id,
                    unique_granted_now,
                    db,
                )
        sync_character_state(active, target, equipment=equipment)
        await self._event_bus.publish_to_session(
            session_id,
            EventType.EQUIPMENT_UPDATED,
            {"character_id": target, "equipment": equipment, "added": added, "source": "gm"},
            source=self._source,
        )

    async def _apply_item_remove(
        self,
        session_id: str,
        params: dict[str, Any],
        active: ActiveSession,
        db: Any | None,
    ) -> None:
        if db is None:
            logger.warning("item_remove ignore : db requis.")
            return
        target = str(params.get("target") or "").strip()
        item_id = str(params.get("item_id") or params.get("id") or "").strip()
        if not target or not item_id:
            logger.warning("item_remove ignore : target/item_id requis.")
            return
        try:
            result = await EquipmentService().remove_item(
                character_id=target,
                item_id=item_id,
                db=db,
                active=active,
            )
        except Exception as exc:
            logger.warning("item_remove ignore : %s", exc)
            return
        await self._event_bus.publish_to_session(
            session_id,
            EventType.EQUIPMENT_UPDATED,
            {
                "character_id": target,
                "equipment": result.equipment,
                "removed": item_id,
                "source": "gm",
            },
            source=self._source,
        )

    @staticmethod
    def _xp_targets(target: str, active: ActiveSession) -> list[str]:
        if target == "party":
            characters = active.state_data.get("characters", {})
            if isinstance(characters, dict):
                return [str(char_id) for char_id in characters.keys()]
            return []
        return [target] if target else []

    @staticmethod
    def _coin_params(params: dict[str, Any]) -> tuple[int, int, int]:
        return (
            GMResponseExecutor._safe_int_value(params.get("gp")),
            GMResponseExecutor._safe_int_value(params.get("sp")),
            GMResponseExecutor._safe_int_value(params.get("cp")),
        )

    @staticmethod
    def _safe_int_value(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    @staticmethod
    def _safe_non_negative_int(value: Any) -> int:
        return max(0, GMResponseExecutor._safe_int_value(value))

    @staticmethod
    def _custom_items_by_id(active: ActiveSession) -> dict[str, dict[str, Any]]:
        context = active.state_data.get("campaign_context")
        if not isinstance(context, dict):
            return {}
        items = context.get("items")
        if not isinstance(items, list):
            return {}
        out: dict[str, dict[str, Any]] = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            item_id = normalize_content_id(item.get("template_id") or item.get("id"))
            if item_id:
                out[item_id] = item
        return out

    @staticmethod
    def _granted_unique_items(active: ActiveSession) -> set[str]:
        context = active.state_data.get("campaign_context")
        if not isinstance(context, dict):
            return set()
        canon = context.get("played_canon")
        if not isinstance(canon, dict):
            return set()
        values = canon.get("granted_unique_items")
        if not isinstance(values, list):
            return set()
        return {normalized for item in values if (normalized := normalize_content_id(item))}

    @staticmethod
    def _mark_unique_items_in_state(active: ActiveSession, item_ids: list[str]) -> None:
        context = active.state_data.get("campaign_context")
        if not isinstance(context, dict):
            return
        canon = context.setdefault("played_canon", {})
        if not isinstance(canon, dict):
            canon = {}
            context["played_canon"] = canon
        granted = list(canon.get("granted_unique_items") or [])
        seen = {normalize_content_id(item) for item in granted}
        for item_id in item_ids:
            normalized = normalize_content_id(item_id)
            if normalized and normalized not in seen:
                granted.append(normalized)
                seen.add(normalized)
        canon["granted_unique_items"] = granted
        active.mark_dirty()

    @staticmethod
    def _campaign_id(active: ActiveSession) -> str:
        context = active.state_data.get("campaign_context")
        if not isinstance(context, dict):
            return ""
        return str(context.get("campaign_id") or "").strip()

    @staticmethod
    def _instantiate_loot_item(
        template_id: str,
        raw: dict[str, Any],
        custom_template: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        template = dict(custom_template or find_equipment(template_id))
        template.setdefault("template_id", template_id)
        template.setdefault("id", template_id)
        template["id"] = f"{template_id}_{uuid.uuid4().hex[:8]}"
        template["template_id"] = template_id
        template["quantity"] = max(1, int(raw.get("quantity", 1) or 1))
        if "identified" in raw:
            template["identified"] = bool(raw["identified"])
        if isinstance(raw.get("hidden_properties"), dict):
            template["hidden_properties"] = dict(raw["hidden_properties"])
        if "weight_lb" not in template and "weight" in template:
            template["weight_lb"] = template.get("weight", 0.0)
        return validate_equipment_item(template).model_dump(mode="json")

    @staticmethod
    def _state_world_maps(active: ActiveSession) -> dict[str, Any]:
        world_maps = active.state_data.get("world_maps")
        if not isinstance(world_maps, dict):
            world_maps = campaign_dossier_service.empty_world_maps()
        world_maps = campaign_dossier_service.sanitize_gm_dossier_map_defaults(world_maps)
        active.state_data["world_maps"] = world_maps
        return world_maps

    @staticmethod
    def _ensure_map_visual_asset(map_data: dict[str, Any], *, map_kind: str) -> None:
        if map_data.get("visual_asset") or not get_image_generation_enabled():
            return
        image_model = get_image_model()
        image_provider = get_image_provider()
        if not image_model or not image_provider:
            return
        map_data["visual_asset"] = local_map_service.build_graph_map_visual_asset(
            map_data,
            map_kind=map_kind,
            provider=image_provider,
            model=image_model,
        )

    @staticmethod
    def _trigger_visual_asset_generation(
        session_id: str,
        data: dict[str, Any],
        scope: str,
    ) -> None:
        """Fire-and-forget background image generation for a prompt_ready visual_asset."""
        visual_asset = data.get("visual_asset")
        if not isinstance(visual_asset, dict) or visual_asset.get("status") != "prompt_ready":
            return
        from app.game.async_tasks import create_logged_task
        from app.services.visual_asset_service import generate_visual_asset

        asset_copy = {**visual_asset}
        if scope == "city":
            asset_copy["_city_id"] = data.get("id")
        create_logged_task(
            generate_visual_asset(session_id, scope, asset_copy),
            name=f"visual_asset_{scope}_{session_id}",
        )

    @staticmethod
    def _register_scene_npcs(layout: dict[str, Any], active: ActiveSession) -> None:
        npc_states = active.state_data.setdefault("npc_states", {})
        if not isinstance(npc_states, dict):
            npc_states = {}
            active.state_data["npc_states"] = npc_states

        journal = active.state_data.get("adventure_journal") or {}
        location = str(
            layout.get("scene_id")
            or journal.get("location_venue")
            or layout.get("terrain")
            or journal.get("location_place")
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

    @staticmethod
    def _filter_absent_npc_pois(layout: dict[str, Any], active: ActiveSession) -> None:
        """Remove known NPC POIs whose stored location contradicts this scene."""
        npc_states = active.state_data.get("npc_states")
        if not isinstance(npc_states, dict):
            return
        scene_id = str(layout.get("scene_id") or "").strip()
        if not scene_id:
            return

        filtered: list[dict[str, Any]] = []
        for poi in layout.get("pois", []) or []:
            if not isinstance(poi, dict):
                continue
            kind = str(poi.get("kind") or "").strip().casefold()
            icon = str(poi.get("icon") or "").strip().casefold()
            npc_id = str(poi.get("id") or "").strip()
            is_npc = kind == "npc" or icon == "npc"
            npc = npc_states.get(npc_id) if npc_id else None
            last_location = (
                str(npc.get("last_location") or "").strip() if isinstance(npc, dict) else ""
            )
            if is_npc and last_location and last_location != scene_id:
                logger.warning(
                    "scene_layout : PNJ absent ignore (id=%s, last_location=%s, scene_id=%s)",
                    npc_id,
                    last_location,
                    scene_id,
                )
                continue
            filtered.append(poi)
        layout["pois"] = filtered

    @classmethod
    def _normalize_scene_layout(cls, params: dict[str, Any]) -> dict[str, Any]:
        raw = params.get("scene") or params.get("layout") or params
        if not isinstance(raw, dict):
            return {}

        cols = cls._clamp_int(raw.get("cols"), default=12, minimum=3, maximum=24)
        rows = cls._clamp_int(raw.get("rows"), default=12, minimum=3, maximum=24)
        try:
            cell_size_m = float(raw.get("cell_size_m", 1.5))
        except (TypeError, ValueError):
            cell_size_m = 1.5
        cell_size_m = max(0.5, min(cell_size_m, 6.0))

        scene_theme = coerce_scene_theme(
            raw.get("scene_theme"),
            raw.get("terrain"),
            raw.get("description"),
            " ".join(
                str(poi.get("name") or poi.get("description") or "")
                for poi in raw.get("pois", []) or []
                if isinstance(poi, dict)
            ),
            " ".join(
                str(exit_.get("label") or exit_.get("description") or exit_.get("leads_to") or "")
                for exit_ in raw.get("exits", []) or []
                if isinstance(exit_, dict)
            ),
        )

        layout: dict[str, Any] = {
            "cols": cols,
            "rows": rows,
            "cell_size_m": cell_size_m,
            "terrain": str(raw.get("terrain") or "unknown"),
            "scene_theme": scene_theme,
            "pois": [],
            "exits": [],
            "party_positions": {},
        }
        raw_scene_id = cls._clean_optional_text(raw.get("scene_id"), max_len=80)
        if raw_scene_id:
            layout["scene_id"] = raw_scene_id
        raw_description = cls._clean_optional_text(
            raw.get("description"),
            max_len=_SCENE_DESCRIPTION_MAX_LEN,
        )
        if raw_description:
            layout["description"] = raw_description
        for optional_text in ("state", "physical_state"):
            value = cls._clean_optional_text(raw.get(optional_text), max_len=180)
            if value:
                layout[optional_text] = value
        if isinstance(raw.get("facts"), list):
            facts = [cls._clean_optional_text(item, max_len=180) for item in raw.get("facts", [])]
            facts = [item for item in facts if item]
            if facts:
                layout["facts"] = facts[:24]

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
            action_hint = cls._clean_optional_text(
                poi.get("action_hint"),
                max_len=_POI_ACTION_HINT_MAX_LEN,
            )
            if description:
                normalized_poi["description"] = description
            if action_hint:
                normalized_poi["action_hint"] = action_hint
            for optional_text in ("state", "visibility", "physical_state"):
                value = cls._clean_optional_text(poi.get(optional_text), max_len=160)
                if value:
                    normalized_poi[optional_text] = value
            if isinstance(poi.get("discovered"), bool):
                normalized_poi["discovered"] = poi["discovered"]
            if isinstance(poi.get("facts"), list):
                facts = [
                    cls._clean_optional_text(item, max_len=180) for item in poi.get("facts", [])
                ]
                facts = [item for item in facts if item]
                if facts:
                    normalized_poi["facts"] = facts[:12]
            element_id = cls._clean_optional_text(poi.get("element_id"), max_len=80)
            if element_id:
                normalized_poi["element_id"] = element_id
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
            element_id = cls._clean_optional_text(exit_data.get("element_id"), max_len=80)
            if element_id:
                normalized_exit["element_id"] = element_id
            placement = cls._clean_optional_text(exit_data.get("placement"), max_len=24)
            if placement in {"edge", "embedded"}:
                normalized_exit["placement"] = placement
            if isinstance(exit_data.get("active"), bool):
                normalized_exit["active"] = exit_data["active"]
            layout["exits"].append(normalized_exit)

        party_positions = raw.get("party_positions") or {}
        if isinstance(party_positions, dict):
            for char_id, position_data in party_positions.items():
                position = cls._normalize_position(position_data, cols, rows)
                if position is not None:
                    layout["party_positions"][str(char_id)] = position

        layout["pois"] = [
            poi for poi in layout["pois"] if not cls._is_duplicate_exit_poi(poi, layout["exits"])
        ]

        normalized_elements = []
        for raw_element in raw.get("elements", []) or []:
            element = local_map_service.normalize_scene_element(raw_element, cols, rows)
            if element:
                for optional_text in ("state", "physical_state"):
                    value = cls._clean_optional_text(raw_element.get(optional_text), max_len=160)
                    if value:
                        element[optional_text] = value
                if isinstance(raw_element.get("facts"), list):
                    facts = [
                        cls._clean_optional_text(item, max_len=180)
                        for item in raw_element.get("facts", [])
                    ]
                    facts = [item for item in facts if item]
                    if facts:
                        element["facts"] = facts[:12]
                normalized_elements.append(element)
        if normalized_elements:
            layout["elements"] = normalized_elements

        visual_asset = local_map_service.normalize_visual_asset(raw.get("visual_asset"))
        if visual_asset:
            layout["visual_asset"] = visual_asset

        local_map_service.enrich_scene_layout(layout)

        if "visual_asset" not in layout and get_image_generation_enabled():
            image_model = get_image_model()
            image_provider = get_image_provider()
            if image_model and image_provider:
                layout["visual_asset"] = local_map_service.build_scene_visual_asset(
                    layout,
                    provider=image_provider,
                    model=image_model,
                )

        if "scene_id" not in layout:
            stable_basis = repr(
                (
                    layout["cols"],
                    layout["rows"],
                    layout["terrain"],
                    [(element["id"], element["kind"]) for element in layout.get("elements", [])],
                    [(poi["id"], poi["position"]) for poi in layout["pois"]],
                    [(exit_data["id"], exit_data["position"]) for exit_data in layout["exits"]],
                )
            )
            layout["scene_id"] = (
                "scene_" + hashlib.sha1(stable_basis.encode("utf-8")).hexdigest()[:12]
            )

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

            prompt = cls._clean_optional_text(raw.get("prompt"), max_len=_POI_PROMPT_MAX_LEN)
            icon = cls._clean_optional_text(raw.get("icon"), max_len=48)
            if prompt:
                interaction["prompt"] = prompt
            if icon:
                interaction["icon"] = icon
            if isinstance(raw.get("default"), bool):
                interaction["default"] = raw["default"]
            mechanics = cls._normalize_poi_interaction_mechanics(raw.get("mechanics"))
            if mechanics:
                interaction["mechanics"] = mechanics

            interactions.append(interaction)
            if len(interactions) >= 5:
                break

        return interactions

    @classmethod
    def _normalize_poi_interaction_mechanics(cls, value: Any) -> dict[str, Any]:
        if not isinstance(value, dict):
            return {}
        mechanics: dict[str, Any] = {}
        roll = value.get("roll")
        if isinstance(roll, dict):
            ability = cls._clean_optional_text(roll.get("ability"), max_len=12)
            if ability:
                ability = ability.lower()[:3]
            if ability in {"str", "dex", "con", "int", "wis", "cha"}:
                roll_type = cls._clean_optional_text(roll.get("type"), max_len=12) or "check"
                roll_type = "save" if roll.get("save") is True else roll_type.lower()
                if roll_type not in {"check", "save"}:
                    roll_type = "check"
                normalized_roll: dict[str, Any] = {
                    "type": roll_type,
                    "ability": ability,
                    "dc": cls._clamp_int(roll.get("dc"), default=12, minimum=5, maximum=30),
                }
                skill = cls._clean_optional_text(roll.get("skill"), max_len=40)
                reason = cls._clean_optional_text(roll.get("reason"), max_len=80)
                if skill:
                    normalized_roll["skill"] = skill
                if reason:
                    normalized_roll["reason"] = reason
                mechanics["roll"] = normalized_roll
        if isinstance(value.get("safe_observation"), bool):
            mechanics["safe_observation"] = value["safe_observation"]
        reveal_tier = cls._clean_optional_text(value.get("reveal_tier"), max_len=16)
        if reveal_tier in {"surface", "interpreted", "deep"}:
            mechanics["reveal_tier"] = reveal_tier
        return mechanics

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
            str(poi.get(key, "")) for key in ("id", "name", "kind", "icon")
        ).casefold()
        normalized = re.sub(r"[^a-z0-9_ -]+", " ", searchable)
        tokens = set(normalized.replace("_", " ").replace("-", " ").split())
        return bool(
            tokens
            & {
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
            }
        )

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
    ) -> dict[str, int] | None:
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
    db: Any | None = None,
    *,
    session_id: str | None = None,
    fallback_actor_id: str | None = None,
    event_bus_instance: Any = event_bus,
    source: str = "action_pipeline",
    social_roll_results: dict[str, Any] | None = None,
    provenance_context: dict[str, Any] | None = None,
) -> GMExecutionResult:
    """Fonction pratique gardant l'API explicite du lot 1.4."""
    executor = GMResponseExecutor(event_bus_instance, source=source)
    return await executor.execute_gm_response(
        response,
        active,
        db,
        session_id=session_id,
        fallback_actor_id=fallback_actor_id,
        social_roll_results=social_roll_results,
        provenance_context=provenance_context,
    )
