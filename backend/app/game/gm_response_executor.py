"""Execution des actions mecaniques demandees par le MJ.

Ce module ne parle pas au LLM. Il applique les actions structurees deja
produites par le GM agent, publie les evenements mecaniques correspondants et
retourne les jets en attente pour une narration d'outcome.
"""
from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import BaseModel, Field

from app.agents.schemas import AgentResponse, GMResponse
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession

logger = logging.getLogger(__name__)

CANON_DIRTY_ACTIONS = {
    "journal_update",
    "quest_add",
    "chronicle_add",
    "state_transition",
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

        ``db`` est garde dans la signature publique pour les appels futurs et
        pour matcher le contrat du pipeline ; l'executor ne l'utilise pas.
        """
        del db
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

            await self.execute_action(actual_session_id, gm_action.type, params, active)
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
        from app.engine.ability_checks import (
            Ability,
            Proficiency,
            SKILL_ABILITY,
            ability_check,
            saving_throw,
            skill_check,
        )

        ability_long_map: dict[str, str] = {
            "strength": "str",
            "dexterity": "dex",
            "constitution": "con",
            "intelligence": "int",
            "wisdom": "wis",
            "charisma": "cha",
        }
        ability_enum_map = {a.value: a for a in Ability}

        skill_name = str(params.get("skill", "")).lower().replace(" ", "_").replace("-", "_")
        ability_str = str(params.get("ability", "")).lower()
        check_type = params.get("type", "check")
        dc = params.get("dc")
        target_id = params.get("target") or fallback_actor_id

        characters = active.state_data.get("characters", {})
        combatants = active.state_data.get("combatants", {})
        char_data = characters.get(target_id) or combatants.get(target_id)
        if char_data is None and characters:
            char_data = next(iter(characters.values()))
        if not char_data:
            logger.warning("roll_request: personnage '%s' introuvable dans state_data", target_id)
            return None

        ab_scores: dict[str, int] = char_data.get("ability_scores") or {
            "str": int(char_data.get("str", 10)),
            "dex": int(char_data.get("dex", 10)),
            "con": 10,
            "int": 10,
            "wis": 10,
            "cha": 10,
        }
        level = int(char_data.get("level", 1))
        skill_profs = list(char_data.get("skill_proficiencies", []))
        save_profs = list(char_data.get("save_proficiencies", []))

        ability_short: Optional[str] = (
            ability_long_map.get(ability_str, ability_str[:3] if ability_str else None)
            if ability_str
            else None
        )
        long_from_short = {v: k for k, v in ability_long_map.items()}

        try:
            if check_type == "save":
                long_ab = long_from_short.get(ability_short or "", ability_str or "wisdom")
                ability_enum = ability_enum_map.get(long_ab, Ability.WIS)
                score = ab_scores.get(ability_short or "wis", 10)
                result = saving_throw(score, ability_enum, level, long_ab in save_profs, dc)
            elif skill_name and skill_name in SKILL_ABILITY:
                gov = SKILL_ABILITY[skill_name]
                ab_key = gov.value[:3]
                score = ab_scores.get(ab_key, 10)
                prof = Proficiency.PROFICIENT if skill_name in skill_profs else Proficiency.NONE
                result = skill_check(score, skill_name, level, prof, dc)
            else:
                long_ab = long_from_short.get(ability_short or "", ability_str or "wisdom")
                ability_enum = ability_enum_map.get(long_ab, Ability.WIS)
                score = ab_scores.get(ability_short or "wis", 10)
                result = ability_check(score, dc, ability=ability_enum)
        except Exception as exc:
            logger.error("roll_request: calcul du jet echoue : %s", exc)
            return None

        return {
            "dice_notation": "1d20",
            "rolls": result.all_rolls,
            "d20": result.d20_roll,
            "modifier": result.modifier,
            "total": result.total,
            "dc": result.dc,
            "success": result.success,
            "label": result.label,
            "breakdown": result.breakdown,
            "character_id": target_id,
            "character_name": char_data.get("name", target_id or ""),
        }

    async def execute_action(
        self,
        session_id: str,
        action_type: str,
        params: dict[str, Any],
        active: ActiveSession,
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
        elif action_type == "social_outcome":
            logger.debug("social_outcome recu sans handler mecanique : %s", params)
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
