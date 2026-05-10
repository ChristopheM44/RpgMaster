"""Action resolver — pipeline : action joueur → moteur → agent GM → événements.

Pipeline complet pour une action joueur :
1. Résolution mécanique via le moteur (engine/) selon le type d'action
2. Construction du contexte et appel du GMAgent pour la narration
3. Publication des événements sur le bus (roll_result, narration, hp_changed…)

Pure orchestration : ce module ne contient pas de logique de règles.
"""
from __future__ import annotations

import logging
import uuid
from typing import Any, Literal, Optional

from app.agents.combat_gm_agent import CombatGMAgent
from app.agents.gm_agent import GMAgent
from app.game.action_mechanics import ActionMechanics
from app.game.async_tasks import create_logged_task
from app.game.event_bus import EventType, event_bus
from app.game.session_manager import ActiveSession
from app.llm.voxtral_client import tts_router
from app.services import campaign_dossier_service

logger = logging.getLogger(__name__)


class ActionResolver:
    """Orchestre le traitement complet d'une action joueur.

    Injectez un *gm_agent* personnalisé pour les tests (mock).

    Usage::

        resolver = ActionResolver()
        await resolver.resolve(
            session_id="abc",
            action_type="attack",
            content="J'attaque le gobelin",
            character_id="hero-1",
            target_id="goblin-1",
            active=active_session,
        )
    """

    def __init__(
        self,
        gm_agent: Optional[GMAgent] = None,
        combat_gm_agent: Optional[GMAgent] = None,
        mechanics: Optional[ActionMechanics] = None,
    ) -> None:
        self._gm: GMAgent = gm_agent or GMAgent()
        self._combat_gm_explicit = combat_gm_agent is not None
        self._combat_gm: GMAgent = combat_gm_agent or (
            gm_agent if gm_agent is not None else CombatGMAgent()
        )
        self._mechanics = mechanics or ActionMechanics()
        self._pipeline: Optional[Any] = None

    def __getattr__(self, name: str) -> Any:
        """Backward-compatible facade for legacy mechanical helper names."""
        if (
            name.startswith("_resolve")
            or name.startswith("_apply")
            or name == "_normalize_roll_event"
        ):
            return getattr(self._mechanics, name)
        raise AttributeError(name)

    # ------------------------------------------------------------------
    # Point d'entrée principal
    # ------------------------------------------------------------------

    async def resolve(
        self,
        session_id: str,
        action_type: str,
        content: Optional[str],
        character_id: Optional[str],
        target_id: Optional[str],
        active: ActiveSession,
        db: Optional[Any] = None,
        spell_id: Optional[str] = None,
        slot_level: Optional[int] = None,
        actor_kind: Literal["player", "companion", "monster"] = "player",
        actor_name: Optional[str] = None,
        display_text: Optional[str] = None,
        persist_actor_action: bool = True,
    ) -> Any:
        """Exécute le pipeline complet pour une action.

        Args:
            session_id: Identifiant de la session active.
            action_type: Type d'action (free_text, attack, cast_spell, …).
            content: Texte libre décrivant l'action.
            character_id: ID du personnage qui agit.
            target_id: ID de la cible (optionnel).
            active: Session active en mémoire.
        """
        from app.game.action_pipeline import ActionRequest

        pipeline = self._pipeline_for_call(db)
        return await pipeline.resolve_and_publish(
            ActionRequest(
                session_id=session_id,
                actor_id=character_id,
                actor_name=actor_name,
                actor_kind=actor_kind,
                action_type=action_type,
                content=content,
                target_id=target_id,
                spell_id=spell_id,
                slot_level=slot_level,
                display_text=display_text,
                persist_actor_action=persist_actor_action,
            ),
            active,
            db,
        )

    def _pipeline_for_call(self, db: Optional[Any]) -> Any:
        """Return the reusable action pipeline for this resolver."""
        from app.game.action_pipeline import ActionPipeline

        if self._pipeline is None:
            self._pipeline = ActionPipeline(
                self._gm,
                event_bus,
                db,
                mechanics=self,
                combat_gm_agent=self._combat_gm_for_call(),
            )
        else:
            self._pipeline._db = db
            self._pipeline._combat_gm = self._combat_gm_for_call()
        return self._pipeline

    def _combat_gm_for_call(self) -> GMAgent:
        """Retourne le MJ combat effectif.

        Les tests et certains outils monkeypatchent historiquement ``_gm.think``
        sur le resolver global. Dans ce cas, on respecte ce patch pour éviter un
        appel réseau involontaire tout en gardant un agent combat dédié en usage
        normal.
        """
        think_type_module = type(getattr(self._gm, "think", None)).__module__
        if (
            not self._combat_gm_explicit
            and self._combat_gm is not self._gm
            and think_type_module.startswith("unittest.mock")
        ):
            return self._gm
        return self._combat_gm

    async def resolve_npc_dialogue(
        self,
        session_id: str,
        content: Optional[str],
        character_id: Optional[str],
        target_id: Optional[str],
        active: ActiveSession,
        db: Optional[Any] = None,
        roll_results: Optional[dict[str, Any]] = None,
    ) -> None:
        """Genere une replique de PNJ via run_npc_dialogue() et la publie.

        Cette methode est appelee APRES la resolution mecanique (jet de skill)
        pour incarner la voix du PNJ cible.
        """
        from app.game.action_pipeline import _poi_by_id, resolve_npc_target_id

        npc_id = resolve_npc_target_id(content, active.state_data, target_id)
        if not npc_id:
            logger.debug("resolve_npc_dialogue : aucune cible PNJ detectee")
            return

        npc_states = active.state_data.setdefault("npc_states", {})
        if not isinstance(npc_states, dict):
            npc_states = {}
            active.state_data["npc_states"] = npc_states
        npc = npc_states.get(npc_id, {}) if isinstance(npc_states, dict) else {}
        poi = _poi_by_id(active.state_data, npc_id)
        if not isinstance(npc, dict):
            npc = {}
        if isinstance(poi, dict) and not npc:
            npc = npc_states.setdefault(
                npc_id,
                {
                    "name": str(poi.get("name") or npc_id),
                    "attitude": "indifferent",
                    "personality_hint": str(
                        poi.get("description") or poi.get("action_hint") or "indifferent"
                    ),
                },
            )

        npc_name = str(npc.get("name", npc_id))
        npc_personality = str(npc.get("personality_hint", "indifferent"))
        recent_messages: list[Any] = []
        if db is not None:
            from app.services.message_service import load_recent_messages
            recent_messages = await load_recent_messages(session_id, db)

        try:
            gm_resp = await self._gm.run_npc_dialogue(
                npc_name=npc_name,
                npc_personality=npc_personality,
                player_message=content or "",
                messages=recent_messages,
                roll_results=roll_results,
            )
        except Exception as exc:
            logger.error("resolve_npc_dialogue : echec LLM : %s", exc)
            return

        dialogue_text = gm_resp.narration or ""
        if not dialogue_text:
            return

        await event_bus.publish_to_session(
            session_id,
            EventType.DIALOGUE,
            {
                "text": dialogue_text,
                "speaker": npc_name,
                "speaker_id": npc_id,
                "speaker_kind": "npc",
                "entry_kind": "dialogue",
                "scene_id": str(uuid.uuid4()),
            },
            source="action_resolver",
        )

        if db is not None:
            from app.models.message import MessageRole, MessageType
            from app.services.message_service import persist_narration
            await persist_narration(
                session_id,
                dialogue_text,
                npc_name,
                db,
                role=MessageRole.GM,
                message_type=MessageType.DIALOGUE,
                metadata={
                    "speaker_id": npc_id,
                    "speaker_kind": "npc",
                    "character_id": character_id,
                },
            )

        from app.game.gm_response_executor import execute_gm_response
        exec_result = await execute_gm_response(
            gm_resp,
            active,
            db,
            session_id=session_id,
            fallback_actor_id=character_id,
        )
        if exec_result.canon_dirty and db is not None:
            try:
                from app.services import campaign_dossier_service

                await campaign_dossier_service.synthesize_canon_for_session(
                    session_id,
                    active.state_data,
                    [],
                    db,
                )
            except Exception as exc:
                logger.warning("Synthese canon campagne ignoree apres dialogue PNJ : %s", exc)

    async def _publish_gm_narration(
        self,
        session_id: str,
        narration_text: str,
        db: Optional[Any],
    ) -> None:
        """Publie, persiste et lance le TTS pour une narration visible du MJ."""
        narration_id = str(uuid.uuid4())
        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {
                "text": narration_text,
                "speaker": "Maître du Jeu",
                "speaker_kind": "gm",
                "entry_kind": "narration",
                "narration_id": narration_id,
            },
            source="action_resolver",
        )

        if db is not None:
            from app.services.message_service import persist_narration

            await persist_narration(session_id, narration_text, "Maître du Jeu", db)

        create_logged_task(
            tts_router.synthesize_and_broadcast(narration_text, session_id, narration_id),
            "action_resolver.tts_narration",
        )

    # ------------------------------------------------------------------
    # Conclusion sociale (compagnons ont déjà parlé)
    # ------------------------------------------------------------------

    async def social_conclude(
        self,
        session_id: str,
        active: ActiveSession,
        player_action: str,
        companion_responses: list[dict[str, str]],
        db: Optional[Any] = None,
    ) -> None:
        """Appelle le MJ pour conclure une scène sociale après les réponses des compagnons.

        Publie et persiste la narration de conclusion, sans ré-exécuter
        la mécanique (les jets et transitions ont déjà été traités).
        """
        try:
            await event_bus.publish_to_session(
                session_id,
                EventType.AI_THINKING,
                {"agent_kind": "gm", "thinking": True},
                source="action_resolver",
            )
            game_state = dict(active.state_data)
            if db is not None:
                try:
                    game_state["world_maps"] = await campaign_dossier_service.map_context_for_session(
                        session_id,
                        db,
                        active.state_data,
                    )
                except Exception as map_exc:
                    logger.debug("ActionResolver.social_conclude : cartes indisponibles : %s", map_exc)
            gm_resp = await self._gm.narrate_social_conclude(
                game_state=game_state,
                player_action=player_action,
                companion_responses=companion_responses,
            )
        except Exception as exc:
            logger.error("ActionResolver.social_conclude : GMAgent échoué : %s", exc)
            gm_resp = None
        finally:
            await event_bus.publish_to_session(
                session_id,
                EventType.AI_THINKING,
                {"agent_kind": "gm", "thinking": False},
                source="action_resolver",
            )

        if gm_resp is None:
            return

        narration_id = str(uuid.uuid4())
        await event_bus.publish_to_session(
            session_id,
            EventType.NARRATION,
            {
                "text": gm_resp.narration,
                "speaker": "Maître du Jeu",
                "speaker_kind": "gm",
                "entry_kind": "narration",
                "narration_id": narration_id,
            },
            source="action_resolver",
        )
        if db is not None:
            from app.services.message_service import persist_narration
            await persist_narration(session_id, gm_resp.narration, "Maître du Jeu", db)
        create_logged_task(
            tts_router.synthesize_and_broadcast(gm_resp.narration, session_id, narration_id),
            "action_resolver.tts_social_conclude",
        )

    # ------------------------------------------------------------------

    async def _apply_gm_action(
        self,
        session_id: str,
        action_type: str,
        params: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        """Applique une action mécanique demandée par le GM.

        Les types supportés :
        - ``damage_apply`` : réduit les PV d'un combattant dans state_data.
        - ``condition_add`` / ``condition_remove`` : publie un événement de condition.
        - ``combatant_status`` : marque un PNJ comme actif, vaincu, rendu ou en fuite.
        - ``scene_layout`` : mémorise le schéma compact du lieu d'exploration.
        - ``state_transition`` : ignoré ici (géré par SessionManager).
        """
        if action_type == "damage_apply":
            target_id = params.get("target")
            amount = int(params.get("amount", 0))
            combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
            if target_id and target_id in combatants:
                old_hp = int(combatants[target_id].get("hp", 0))
                new_hp = max(0, old_hp - amount)
                combatants[target_id]["hp"] = new_hp
                active.mark_dirty()
                await event_bus.publish_to_session(
                    session_id,
                    EventType.HP_CHANGED,
                    {
                        "combatant_id": target_id,
                        "delta": -amount,
                        "hp": new_hp,
                    },
                    source="action_resolver",
                )
                # Si un joueur tombe à 0 PV : init jets de sauvegarde contre la mort
                if new_hp == 0 and combatants[target_id].get("is_player", False):
                    cdata = combatants[target_id]
                    if "death_saves" not in cdata:
                        cdata["death_saves"] = {"successes": 0, "failures": 0, "stable": False}
                    conds: list[str] = list(cdata.get("conditions", []))
                    if "inconscient" not in conds:
                        conds.append("inconscient")
                        cdata["conditions"] = conds
                        await event_bus.publish_to_session(
                            session_id,
                            EventType.CONDITION_CHANGED,
                            {"combatant_id": target_id, "condition": "inconscient", "added": True},
                            source="action_resolver",
                        )
            else:
                logger.debug(
                    "damage_apply : cible '%s' non trouvée dans state_data.", target_id
                )

        elif action_type in ("condition_add", "condition_remove"):
            target_id = params.get("target")
            condition = params.get("condition", "")
            combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
            if target_id and target_id in combatants and condition:
                conditions: list[str] = list(combatants[target_id].get("conditions", []))
                if action_type == "condition_add" and condition not in conditions:
                    conditions.append(condition)
                elif action_type == "condition_remove":
                    conditions = [c for c in conditions if c != condition]
                combatants[target_id]["conditions"] = conditions
                active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.CONDITION_CHANGED,
                {
                    "combatant_id": target_id,
                    "condition": condition,
                    "added": action_type == "condition_add",
                },
                source="action_resolver",
            )

        elif action_type == "combatant_status":
            target_id = params.get("target")
            status = str(params.get("status", "")).strip().lower()
            reason = str(params.get("reason", status or "resolved"))
            valid_statuses = {"active", "defeated", "surrendered", "fled"}
            if status not in valid_statuses:
                logger.warning(
                    "combatant_status ignoré : statut invalide '%s' — params=%s",
                    status,
                    params,
                )
                return

            combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
            if not target_id or target_id not in combatants:
                logger.warning(
                    "combatant_status ignoré : cible '%s' introuvable — params=%s",
                    target_id,
                    params,
                )
                return

            combatants[target_id]["status"] = status
            active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.COMBATANT_STATUS_CHANGED,
                {
                    "combatant_id": target_id,
                    "combatant_name": combatants[target_id].get("name", target_id),
                    "status": status,
                    "reason": reason,
                },
                source="action_resolver",
            )

        elif action_type == "encounter_setup":
            monster_ids = params.get("monster_ids", [])
            context = params.get("context", "")
            if monster_ids:
                active.state_data["pending_encounter"] = {
                    "monster_ids": monster_ids,
                    "context": context,
                }
                active.mark_dirty()
                logger.info(
                    "encounter_setup : pending_encounter défini avec %s",
                    monster_ids,
                )

        elif action_type == "state_transition":
            # Le MJ demande un changement de phase. On pose un drapeau que
            # ws_game._dispatch_action consommera après le retour de resolve()
            # pour déclencher effectivement la transition (le resolver n'a pas
            # accès à la session DB ni au WebSocket).
            target_phase = (
                params.get("to")
                or params.get("target")
                or params.get("phase")
                or ""
            )
            target_phase = str(target_phase).upper()

            if target_phase == "COMBAT":
                if active.state_data.get("pending_encounter"):
                    active.state_data["pending_phase_transition"] = "COMBAT"
                    active.mark_dirty()
                    logger.info(
                        "state_transition : passage en COMBAT programmé (pending_encounter=%s)",
                        active.state_data["pending_encounter"].get("monster_ids"),
                    )
                else:
                    logger.warning(
                        "state_transition COMBAT ignoré : aucun pending_encounter défini "
                        "(le MJ devrait émettre encounter_setup avant state_transition)."
                    )
            elif target_phase:
                logger.info(
                    "state_transition %s : non implémenté (scope actuel : COMBAT uniquement).",
                    target_phase,
                )
            else:
                logger.debug("state_transition reçue sans phase cible : %s", params)

        elif action_type == "scene_layout":
            from app.game.gm_response_executor import GMResponseExecutor

            layout = GMResponseExecutor._normalize_scene_layout(params)
            if not layout:
                logger.warning("scene_layout ignoré : params invalides — %s", params)
                return
            active.state_data["current_scene"] = layout
            active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.SCENE_LAYOUT_CHANGED,
                {"scene": layout},
                source="action_resolver",
            )

        elif action_type == "journal_update":
            journal: dict[str, Any] = active.state_data.setdefault("adventure_journal", {
                "location_region": None,
                "location_place": None,
                "time_of_day": "morning",
                "day_number": 1,
                "calendar_date": None,
                "weather": None,
            })
            for key in ("location_region", "location_place", "time_of_day",
                        "day_number", "calendar_date", "weather"):
                if key in params and params[key] is not None:
                    journal[key] = params[key]
            active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.JOURNAL_UPDATED,
                {"journal": dict(journal)},
                source="action_resolver",
            )

        elif action_type == "quest_add":
            quest_id = params.get("id")
            if not quest_id:
                logger.warning("quest_add ignoré : id manquant — params=%s", params)
                return
            quests: list[dict[str, Any]] = active.state_data.setdefault("quests", [])
            idx = next((i for i, q in enumerate(quests) if q.get("id") == quest_id), -1)
            quest_entry: dict[str, Any] = {
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
            await event_bus.publish_to_session(
                session_id,
                EventType.QUEST_UPDATED,
                {"quests": list(quests)},
                source="action_resolver",
            )

        elif action_type == "chronicle_add":
            chron_id = params.get("id")
            kind = params.get("kind")
            if not chron_id or kind not in ("npc", "location"):
                logger.warning(
                    "chronicle_add ignoré : id ou kind invalide — params=%s", params
                )
                return
            chronicle: list[dict[str, Any]] = active.state_data.setdefault("chronicle", [])
            idx = next((i for i, e in enumerate(chronicle) if e.get("id") == chron_id), -1)
            entry: dict[str, Any] = {
                "id": chron_id,
                "kind": kind,
                "name": params.get("name", chron_id),
                "note": params.get("note", ""),
            }
            if idx >= 0:
                chronicle[idx] = {**chronicle[idx], **entry}
            else:
                chronicle.append(entry)
            active.mark_dirty()
            await event_bus.publish_to_session(
                session_id,
                EventType.CHRONICLE_UPDATED,
                {"chronicle": list(chronicle)},
                source="action_resolver",
            )

        else:
            logger.warning("ActionResolver : type d'action GM inconnu '%s'.", action_type)
