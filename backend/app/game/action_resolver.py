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
from app.game.action_orchestrator import ActionOrchestrator
from app.game.event_bus import event_bus
from app.game.session_manager import ActiveSession
from app.game.visible_events import publish_visible_entry
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
        self._orchestrator = ActionOrchestrator(
            event_bus,
            source="action_resolver",
            tts_router=tts_router,
        )

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
        suppress_gm_narration: bool = False,
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
                suppress_gm_narration=suppress_gm_narration,
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
    ) -> bool:
        """Genere une replique de PNJ via run_npc_dialogue() et la publie.

        Cette methode est appelee APRES la resolution mecanique (jet de skill)
        pour incarner la voix du PNJ cible.
        """
        from app.game.action_pipeline import _poi_by_id, resolve_npc_target_id

        npc_id = resolve_npc_target_id(content, active.state_data, target_id)
        if not npc_id:
            logger.debug("resolve_npc_dialogue : aucune cible PNJ detectee")
            return False

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
        # The party is actively engaging with this NPC → reveal identity to companions.
        if isinstance(npc, dict):
            npc["known_to_party"] = True
        if isinstance(poi, dict):
            poi["known_to_party"] = True

        if isinstance(roll_results, dict):
            roll_results = dict(roll_results)
            roll_results.setdefault("type", "skill_check")
            roll_results.setdefault("social_target_id", npc_id)

        npc_name = str(npc.get("name", npc_id))
        npc_personality = str(npc.get("personality_hint", "indifferent"))
        recent_messages: list[Any] = []
        if db is not None:
            from app.services.message_service import load_recent_messages
            recent_messages = await load_recent_messages(session_id, db)
        game_state = dict(active.state_data)
        if db is not None:
            try:
                game_state["world_maps"] = (
                    await campaign_dossier_service.map_context_for_session(
                        session_id,
                        db,
                        active.state_data,
                    )
                )
            except Exception as map_exc:
                logger.debug(
                    "resolve_npc_dialogue : contexte cartes indisponible : %s",
                    map_exc,
                )

        try:
            gm_resp = await self._gm.run_npc_dialogue(
                npc_name=npc_name,
                npc_personality=npc_personality,
                player_message=content or "",
                game_state=game_state,
                messages=recent_messages,
                roll_results=roll_results,
            )
        except Exception as exc:
            logger.error("resolve_npc_dialogue : echec LLM : %s", exc)
            return False

        has_roll_request = any(a.type == "roll_request" for a in gm_resp.actions)
        dialogue_text = gm_resp.narration or ""

        if not dialogue_text and not has_roll_request:
            return False

        published_visible = False
        if dialogue_text:
            await publish_visible_entry(
                event_bus,
                session_id,
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
            published_visible = True

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
            social_roll_results=roll_results,
        )
        canon_dirty = exec_result.canon_dirty

        # Si un jet de dés (roll_request) a été demandé par le PNJ/MJ, on passe à la deuxième étape
        if has_roll_request and exec_result.pending_rolls:
            first_roll = exec_result.pending_rolls[0]
            if isinstance(first_roll, dict):
                first_roll.setdefault("type", "skill_check")
                first_roll.setdefault("social_target_id", npc_id)
            game_state_2 = dict(active.state_data)
            if db is not None:
                try:
                    game_state_2["world_maps"] = (
                        await campaign_dossier_service.map_context_for_session(
                            session_id,
                            db,
                            active.state_data,
                        )
                    )
                except Exception as map_exc:
                    logger.debug(
                        "resolve_npc_dialogue (step 2) : contexte cartes indisponible : %s",
                        map_exc,
                    )

            try:
                gm_resp_2 = await self._gm.run_npc_dialogue(
                    npc_name=npc_name,
                    npc_personality=npc_personality,
                    player_message=content or "",
                    game_state=game_state_2,
                    messages=recent_messages,
                    roll_results=first_roll,
                )

                dialogue_text_2 = gm_resp_2.narration or ""
                if dialogue_text_2:
                    await publish_visible_entry(
                        event_bus,
                        session_id,
                        {
                            "text": dialogue_text_2,
                            "speaker": npc_name,
                            "speaker_id": npc_id,
                            "speaker_kind": "npc",
                            "entry_kind": "dialogue",
                            "scene_id": str(uuid.uuid4()),
                        },
                        source="action_resolver",
                    )
                    published_visible = True

                    if db is not None:
                        from app.models.message import MessageRole, MessageType
                        from app.services.message_service import persist_narration
                        await persist_narration(
                            session_id,
                            dialogue_text_2,
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

                exec_result_2 = await execute_gm_response(
                    gm_resp_2,
                    active,
                    db,
                    session_id=session_id,
                    fallback_actor_id=character_id,
                    social_roll_results=first_roll,
                )
                if exec_result_2.canon_dirty:
                    canon_dirty = True
            except Exception as exc:
                logger.error("resolve_npc_dialogue (step 2) : echec LLM : %s", exc)

        if canon_dirty and db is not None:
            try:
                await campaign_dossier_service.synthesize_canon_for_session(
                    session_id,
                    active.state_data,
                    [],
                    db,
                )
            except Exception as exc:
                logger.warning("Synthese canon campagne ignoree apres dialogue PNJ : %s", exc)
        return published_visible or bool(exec_result.pending_rolls)

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
            await self._orchestrator.publish_ai_thinking(session_id, True)
            game_state = dict(active.state_data)
            if db is not None:
                try:
                    game_state["world_maps"] = (
                        await campaign_dossier_service.map_context_for_session(
                            session_id,
                            db,
                            active.state_data,
                        )
                    )
                except Exception as map_exc:
                    logger.debug(
                        "ActionResolver.social_conclude : cartes indisponibles : %s",
                        map_exc,
                    )
            gm_resp = await self._gm.narrate_social_conclude(
                game_state=game_state,
                player_action=player_action,
                companion_responses=companion_responses,
            )
        except Exception as exc:
            logger.error("ActionResolver.social_conclude : GMAgent échoué : %s", exc)
            gm_resp = None
        finally:
            await self._orchestrator.publish_ai_thinking(session_id, False)

        if gm_resp is None:
            return

        await self._orchestrator.publish_gm_narration(session_id, gm_resp.narration, db)
