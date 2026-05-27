"""Pipeline unifie de resolution et publication d'action.

Le pipeline centralise le contrat visible :
action acteur -> resolution mecanique -> ROLL_RESULT -> narration MJ.
Il ne choisit pas les actions et ne fait pas avancer les tours.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from app.agents.schemas import AgentContext, AgentResponse, GMAction, GMResponse
from app.engine.ability_checks import SKILL_ABILITY, Ability, Proficiency, skill_check
from app.engine.tactical_grid import GridPosition
from app.game.action_orchestrator import ActionOrchestrator
from app.game.combat_triggers import prime_combat_from_hostile_narration
from app.game.constants import INACTIVE_STATUSES
from app.game.event_bus import EventType, event_bus
from app.game.gm_response_executor import GMResponseExecutor
from app.game.session_manager import ActiveSession
from app.game.tactical_combat import (
    apply_tactical_move,
    calculate_reachable_cells,
    choose_attack_target,
    combatant_speed_m,
    prepare_attack,
    prepare_cast_spell,
)
from app.llm.budget import (
    begin_llm_call_scope,
    end_llm_call_scope,
    is_pure_companion_social_prompt,
    is_sober_mode,
    should_use_gm_for_action,
)
from app.llm.voxtral_client import tts_router
from app.services import campaign_dossier_service
from app.services.spellcasting_service import SpellcastingService, SpellcastingServiceError

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Narrations variées pour les blocages tactiques (portée / chemin absent)
# ---------------------------------------------------------------------------
_ATTACK_BLOCK_TEMPLATES = [
    "{name} cherche un angle d'attaque, mais n'est pas à portée.",
    "{name} marque une pause — aucune cible accessible depuis cette position.",
    "{name} pivote, guettant une ouverture qui ne vient pas.",
    "{name} retient son élan : les combattants sont trop éloignés pour frapper.",
    "{name} observe les lignes de mêlée, mais l'angle est fermé.",
    "{name} se repositionne lentement, sans prise immédiate.",
]
_SPELL_BLOCK_TEMPLATES = [
    "{name} amorce un geste runique, mais sa cible est hors de portée.",
    "{name} suspend son incantation — aucune cible dans le rayon d'action.",
    "{name} retient son sort : l'angle magique est trop précaire.",
    "{name} concentre son énergie, cherchant une ligne de vue qui n'existe pas.",
    "{name} murmure les mots du sort, puis les laisse s'éteindre, faute d'ouverture.",
]


# ---------------------------------------------------------------------------
# Garde-fou hors-combat : actions improvisées risquées sans roll_request GM
# ---------------------------------------------------------------------------
# Verbes qui signalent une action physiquement risquée ou à efficacité incertaine.
# Le pattern est volontairement conservateur pour éviter les faux positifs.
_RISKY_ACTION_PATTERN = re.compile(
    r"""
    (?:
        (?:trancher|couper|taillader|frapper|poignarder)\s+(?:avec|la|le|son|l'|les)
        |
        (?:enflammer|enflammer|mettre\s+le\s+feu|faire\s+prendre\s+feu|allumer)
        |
        (?:enfoncer|plonger|insérer|glisser)\s+(?:mon|ma|mes|son|sa|l'|la|le)
        |
        (?:escalader|grimper|traverser\s+en\s+courant)
        |
        (?:sauter|bondir|me\s+lancer)\s+(?:par[\s-]dessus|dans|sur)
        |
        (?:crocheter|forcer|fracturer|défoncer)\s+(?:la|le|les)
        |
        (?:toucher|saisir|attraper|empoigner)\s+(?:la|le|les|l')\s+\w*(?:électr|ardent|brûl|corros|poison)
    )
    """,
    re.IGNORECASE | re.VERBOSE,
)

# Skills par défaut selon le type de risque détecté (conservateur)
_RISKY_SKILL_DEFAULTS = {
    "trancher": ("Athletics", "str", 13),
    "enflammer": ("Arcana", "int", 12),
    "enfoncer": ("Acrobatics", "dex", 13),
    "escalader": ("Athletics", "str", 12),
    "grimper": ("Athletics", "str", 12),
    "sauter": ("Athletics", "str", 12),
    "bondir": ("Athletics", "str", 12),
    "crocheter": ("SleightOfHand", "dex", 15),
    "forcer": ("Athletics", "str", 14),
    "fracturer": ("Athletics", "str", 14),
}


def _infer_risky_roll_request(content: str) -> Optional[dict[str, Any]]:
    """Si l'action free_text contient un verbe risqué, retourne un roll_request minimal.

    Conservateur : ne tire pas sur les verbes ambigus ni les descriptions passives.
    Retourne None si aucun pattern ne correspond.
    """
    if not content or len(content) < 10:
        return None
    normalized = content.lower()
    # Cherche le premier verbe déclencheur pour adapter le skill
    for keyword, (skill, ability, dc) in _RISKY_SKILL_DEFAULTS.items():
        if keyword in normalized:
            if _RISKY_ACTION_PATTERN.search(content):
                return {
                    "type": "roll_request",
                    "target": None,
                    "params": {
                        "skill": skill,
                        "ability": ability,
                        "dc": dc,
                        "reason": "action_risquee_libre",
                    },
                }
    return None


def _tactical_block_narration(actor_name: str, action_type: str) -> str:
    """Retourne une phrase variée non-technique décrivant un blocage tactique.

    Le choix est déterministe par (actor_name, action_type) pour éviter les
    changements aléatoires entre appels, tout en variant selon les acteurs.
    """
    templates = _SPELL_BLOCK_TEMPLATES if action_type == "cast_spell" else _ATTACK_BLOCK_TEMPLATES
    seed = int(hashlib.md5(f"{actor_name}:{action_type}".encode()).hexdigest()[:8], 16)
    template = templates[seed % len(templates)]
    return template.format(name=actor_name)

_FALLBACK_NARRATION = (
    "Le Maître du Jeu hésite… (Le LLM n'a pas répondu correctement — "
    "veuillez répéter votre action ou rafraîchir la page.)"
)

spellcasting_service = SpellcastingService()

# Social detection helpers — canonical home is social_resolution.py
from app.game.social_resolution import (  # noqa: E402
    _ability_short_key,
    _calculate_social_dc,
    _detect_social_skill,
    _is_combat_social_text,
    _is_social_exploration_text,
    _normalized_skill_proficiencies,
    resolve_npc_target_id,
)


class ActionRequest(BaseModel):
    """Action normalisee envoyee au pipeline."""

    session_id: str
    actor_id: Optional[str] = None
    actor_name: Optional[str] = None
    actor_kind: Literal["player", "companion", "monster"] = "player"
    action_type: str
    content: Optional[str] = None
    target_id: Optional[str] = None
    spell_id: Optional[str] = None
    slot_level: Optional[int] = None
    display_text: Optional[str] = None
    persist_actor_action: bool = True
    suppress_gm_narration: bool = False


class ResolvedAction(BaseModel):
    """Resultat structure d'une action resolue et publiee."""

    actor_id: Optional[str] = None
    actor_name: str = ""
    actor_kind: Literal["player", "companion", "monster"]
    action_type: str
    target_id: Optional[str] = None
    mechanics: dict[str, Any] = Field(default_factory=dict)
    roll_events: list[dict[str, Any]] = Field(default_factory=list)
    narration: str = ""
    gm_actions: list[dict[str, Any]] = Field(default_factory=list)
    canon_dirty: bool = False


class ActionPipeline:
    """Resolve une action et publie les evenements canoniques."""

    def __init__(
        self,
        gm_agent: Any,
        event_bus_instance: Any = event_bus,
        db: Optional[Any] = None,
        *,
        mechanics: Optional[Any] = None,
        combat_gm_agent: Optional[Any] = None,
        source: str = "action_pipeline",
    ) -> None:
        self._gm = gm_agent
        self._combat_gm = combat_gm_agent or gm_agent
        self._event_bus = event_bus_instance
        self._db = db
        self._mechanics = mechanics
        self._source = source
        self._executor = GMResponseExecutor(event_bus_instance, source=source)
        self._orchestrator = ActionOrchestrator(
            event_bus_instance,
            source=source,
            tts_router=tts_router,
        )

    async def resolve_and_publish(
        self,
        request: ActionRequest,
        active: ActiveSession,
        db: Optional[Any] = None,
    ) -> ResolvedAction:
        """Execute le flux complet pour une action deja choisie."""
        token, scope = begin_llm_call_scope(
            request.session_id,
            f"{request.actor_kind}:{request.action_type}",
        )
        try:
            return await self._resolve_and_publish_impl(request, active, db)
        finally:
            end_llm_call_scope(token, scope)

    async def _resolve_and_publish_impl(
        self,
        request: ActionRequest,
        active: ActiveSession,
        db: Optional[Any] = None,
    ) -> ResolvedAction:
        """Execute le flux complet pour une action deja choisie."""
        actual_db = db if db is not None else self._db
        actor_name = request.actor_name or self._actor_name(
            request.actor_id,
            request.actor_kind,
            active.state_data,
        )
        target_id = request.target_id or self._default_target_id(request, active.state_data)
        target_name = self._combatant_name(active.state_data, target_id)
        display_text = self._display_text(request, actor_name, target_name)
        phase_value = self._phase_value(active).upper()

        roll_results: Optional[dict[str, Any]] = None
        roll_events: list[dict[str, Any]] = []
        executed_actions: list[dict[str, Any]] = []
        canon_dirty = False
        tactical: Any = None

        # 1. Resolution mecanique pure.
        mechanics = self._get_mechanics()
        if request.action_type == "attack":
            if phase_value == "COMBAT":
                tactical = await prepare_attack(
                    session_id=request.session_id,
                    active=active,
                    actor_id=request.actor_id,
                    target_id=target_id,
                    actor_kind=request.actor_kind,
                    event_bus=self._event_bus,
                    source=self._source,
                )
                target_id = tactical.target_id
                target_name = self._combatant_name(active.state_data, target_id)
                if tactical.moved is not None:
                    await self._publish_tactical_move_result(
                        request.session_id,
                        request.actor_id,
                        tactical.moved,
                        active,
                    )
                if not tactical.allowed:
                    message = tactical.reason or "Action tactique impossible."
                    if request.actor_kind in {"monster", "companion"}:
                        narration = _tactical_block_narration(actor_name, "attack")
                        await self._publish_gm_narration(request.session_id, narration, actual_db)
                    else:
                        await self._event_bus.publish_to_session(
                            request.session_id,
                            EventType.ERROR,
                            {"message": message},
                            source=self._source,
                        )
                        narration = ""
                    return ResolvedAction(
                        actor_id=request.actor_id,
                        actor_name=actor_name,
                        actor_kind=request.actor_kind,
                        action_type=request.action_type,
                        target_id=target_id,
                        mechanics={"error": True, "summary": message},
                        roll_events=[],
                        narration=narration,
                        gm_actions=[],
                        canon_dirty=False,
                    )
            roll_results = mechanics._resolve_attack(
                request.actor_id,
                target_id,
                active.state_data,
            )
            if tactical is not None:
                roll_results["tactical"] = {
                    "target_id": target_id,
                    "moved": bool(tactical.moved),
                    "movement_used_m": (tactical.moved.movement_used_m if tactical.moved else 0),
                    "path": (
                        [step.to_dict() for step in tactical.moved.path] if tactical.moved else []
                    ),
                    "opportunity_attacks": [
                        attack.__dict__ for attack in tactical.moved.opportunity_attacks
                    ]
                    if tactical.moved
                    else [],
                }
            if roll_results and roll_results.get("hit") and target_id:
                damage_amount = int(roll_results.get("damage", {}).get("total", 0))
                if damage_amount > 0:
                    await self._executor.execute_action(
                        request.session_id,
                        "damage_apply",
                        {"target": target_id, "amount": damage_amount},
                        active,
                    )
                    executed_actions.append(
                        {
                            "type": "damage_apply",
                            "target": target_id,
                            "params": {"amount": damage_amount},
                            "origin": "engine",
                        }
                    )
        elif request.action_type == "death_save":
            roll_results = mechanics._resolve_death_save(request.actor_id, active.state_data)
            await mechanics._apply_death_save_outcome(
                request.session_id,
                request.actor_id,
                roll_results,
                active,
            )
        elif request.action_type == "stabilize":
            roll_results = mechanics._resolve_stabilize(
                request.actor_id,
                target_id,
                active.state_data,
            )
            await self._apply_stabilize_success(
                request.session_id,
                target_id,
                roll_results,
                active,
            )
        elif request.action_type == "move" and phase_value == "COMBAT":
            ok, message, _move_result = await self._execute_tactical_move_request(
                request,
                active,
            )
            if not ok:
                await self._event_bus.publish_to_session(
                    request.session_id,
                    EventType.ERROR,
                    {"message": message},
                    source=self._source,
                )
                return ResolvedAction(
                    actor_id=request.actor_id,
                    actor_name=actor_name,
                    actor_kind=request.actor_kind,
                    action_type=request.action_type,
                    target_id=target_id,
                    mechanics={"error": True, "summary": message},
                    roll_events=[],
                    narration="",
                    gm_actions=[],
                    canon_dirty=False,
                )
        elif request.action_type == "dash" and phase_value == "COMBAT":
            current = active.turn_manager.current_turn
            economy = (
                current.action_economy
                if current is not None and current.combatant_id == request.actor_id
                else None
            )
            if economy is None or not economy.use_action():
                message = "Action déjà utilisée ce tour."
                await self._event_bus.publish_to_session(
                    request.session_id,
                    EventType.ERROR,
                    {"message": message},
                    source=self._source,
                )
                return ResolvedAction(
                    actor_id=request.actor_id,
                    actor_name=actor_name,
                    actor_kind=request.actor_kind,
                    action_type=request.action_type,
                    target_id=target_id,
                    mechanics={"error": True, "summary": message},
                    roll_events=[],
                    narration="",
                    gm_actions=[],
                    canon_dirty=False,
                )
            economy.movement += economy.movement_max
            economy.has_dashed = True
            active.mark_dirty()
            if self._parse_move_destination(request.content) is not None:
                ok, message, _move_result = await self._execute_tactical_move_request(
                    request,
                    active,
                )
                if not ok:
                    await self._event_bus.publish_to_session(
                        request.session_id,
                        EventType.ERROR,
                        {"message": message},
                        source=self._source,
                    )
                    return ResolvedAction(
                        actor_id=request.actor_id,
                        actor_name=actor_name,
                        actor_kind=request.actor_kind,
                        action_type=request.action_type,
                        target_id=target_id,
                        mechanics={"error": True, "summary": message},
                        roll_events=[],
                        narration="",
                        gm_actions=[],
                        canon_dirty=False,
                    )
            else:
                await self._publish_action_economy_result(active, request.actor_id)
        elif request.action_type == "disengage" and phase_value == "COMBAT":
            current = active.turn_manager.current_turn
            economy = (
                current.action_economy
                if current is not None and current.combatant_id == request.actor_id
                else None
            )
            if economy is None or not economy.use_action():
                message = "Action déjà utilisée ce tour."
                await self._event_bus.publish_to_session(
                    request.session_id,
                    EventType.ERROR,
                    {"message": message},
                    source=self._source,
                )
                return ResolvedAction(
                    actor_id=request.actor_id,
                    actor_name=actor_name,
                    actor_kind=request.actor_kind,
                    action_type=request.action_type,
                    target_id=target_id,
                    mechanics={"error": True, "summary": message},
                    roll_events=[],
                    narration="",
                    gm_actions=[],
                    canon_dirty=False,
                )
            economy.has_disengaged = True
            active.mark_dirty()
            if self._parse_move_destination(request.content) is not None:
                ok, message, _move_result = await self._execute_tactical_move_request(
                    request,
                    active,
                )
                if not ok:
                    await self._event_bus.publish_to_session(
                        request.session_id,
                        EventType.ERROR,
                        {"message": message},
                        source=self._source,
                    )
                    return ResolvedAction(
                        actor_id=request.actor_id,
                        actor_name=actor_name,
                        actor_kind=request.actor_kind,
                        action_type=request.action_type,
                        target_id=target_id,
                        mechanics={"error": True, "summary": message},
                        roll_events=[],
                        narration="",
                        gm_actions=[],
                        canon_dirty=False,
                    )
            else:
                await self._publish_action_economy_result(active, request.actor_id)
        elif request.action_type == "cast_spell":
            if request.spell_id is not None:
                if phase_value == "COMBAT":
                    tactical = await prepare_cast_spell(
                        session_id=request.session_id,
                        active=active,
                        actor_id=request.actor_id,
                        target_id=target_id,
                        spell_id=request.spell_id,
                        actor_kind=request.actor_kind,
                        event_bus=self._event_bus,
                        source=self._source,
                    )
                    target_id = tactical.target_id
                    target_name = self._combatant_name(active.state_data, target_id)
                    if tactical.moved is not None:
                        await self._publish_tactical_move_result(
                            request.session_id,
                            request.actor_id,
                            tactical.moved,
                            active,
                        )
                    if not tactical.allowed:
                        message = tactical.reason or "Sort tactique impossible."
                        if request.actor_kind in {"monster", "companion"}:
                            narration = _tactical_block_narration(actor_name, "cast_spell")
                            await self._publish_gm_narration(
                                request.session_id,
                                narration,
                                actual_db,
                            )
                        else:
                            await self._event_bus.publish_to_session(
                                request.session_id,
                                EventType.ERROR,
                                {"message": message},
                                source=self._source,
                            )
                            narration = ""
                        return ResolvedAction(
                            actor_id=request.actor_id,
                            actor_name=actor_name,
                            actor_kind=request.actor_kind,
                            action_type=request.action_type,
                            target_id=target_id,
                            mechanics={"error": True, "summary": message},
                            roll_events=[],
                            narration=narration,
                            gm_actions=[],
                            canon_dirty=False,
                        )
                caster_snapshot: Optional[dict[str, Any]] = None
                if actual_db is not None:
                    try:
                        prepared = await spellcasting_service.prepare_cast(
                            session_id=request.session_id,
                            character_id=request.actor_id,
                            spell_id=request.spell_id,
                            slot_level=request.slot_level,
                            active=active,
                            db=actual_db,
                            event_bus_instance=self._event_bus,
                        )
                        caster_snapshot = prepared.caster if prepared is not None else None
                    except SpellcastingServiceError as exc:
                        roll_results = {
                            "type": "cast_spell",
                            "summary": str(exc),
                            "error": True,
                        }
                if caster_snapshot is None and request.actor_id:
                    snapshot = (active.state_data.get("characters") or {}).get(request.actor_id)
                    if isinstance(snapshot, dict):
                        caster_snapshot = snapshot
                if roll_results is None:
                    roll_results = await mechanics._resolve_cast_spell(
                        request.session_id,
                        request.actor_id,
                        request.spell_id,
                        request.slot_level,
                        target_id,
                        active,
                        caster_snapshot,
                    )
                if tactical is not None and roll_results is not None:
                    roll_results["tactical"] = {
                        "target_id": target_id,
                        "moved": bool(tactical.moved),
                        "movement_used_m": (
                            tactical.moved.movement_used_m if tactical.moved else 0
                        ),
                        "path": (
                            [step.to_dict() for step in tactical.moved.path]
                            if tactical.moved
                            else []
                        ),
                        "opportunity_attacks": [
                            attack.__dict__ for attack in tactical.moved.opportunity_attacks
                        ]
                        if tactical.moved
                        else [],
                    }
                if roll_results and not roll_results.get("error") and target_id:
                    attack = roll_results.get("attack", {})
                    damage = roll_results.get("damage", {})
                    if damage:
                        hit = attack.get("hit", True) if attack else True
                        if hit:
                            damage_amount = int(damage.get("total", 0))
                            if damage_amount > 0:
                                await self._executor.execute_action(
                                    request.session_id,
                                    "damage_apply",
                                    {"target": target_id, "amount": damage_amount},
                                    active,
                                )
                                executed_actions.append(
                                    {
                                        "type": "damage_apply",
                                        "target": target_id,
                                        "params": {"amount": damage_amount},
                                        "origin": "engine",
                                    }
                                )
            else:
                roll_results = mechanics._resolve_generic_roll(request.content)
        elif request.action_type == "free_text" and _is_social_exploration_text(request.content):
            roll_results = self._resolve_social_check(request, active)

        # 2. Persistance visible puis contexte GM avec resume mecanique.
        if request.persist_actor_action:
            await self._persist_actor_action(
                request.session_id,
                display_text,
                actor_name,
                request,
                target_id,
                actual_db,
            )

        prompt_action_text = self._prompt_action_text(
            request,
            actor_name,
            target_name,
            roll_results,
        )
        use_gm = should_use_gm_for_action(
            phase=phase_value,
            action_type=request.action_type,
            actor_kind=request.actor_kind,
            content=request.content,
            roll_results=roll_results,
        )
        if request.suppress_gm_narration:
            use_gm = False
        if (
            is_sober_mode()
            and phase_value != "COMBAT"
            and is_pure_companion_social_prompt(request.action_type, request.content)
            and not request.suppress_gm_narration
            and not active.ai_players
        ):
            use_gm = True
        context: Optional[AgentContext] = None

        gm_response: Optional[AgentResponse] = None
        if use_gm:
            recent_messages: list[Any] = []
            if actual_db is not None:
                from app.services.message_service import load_recent_messages

                recent_messages = await load_recent_messages(request.session_id, actual_db)

            game_state_for_gm = await self._game_state_for_gm(
                request.session_id,
                active,
                actual_db,
            )
            context = AgentContext(
                session_id=request.session_id,
                game_phase=phase_value,
                game_state=game_state_for_gm,
                player_action=prompt_action_text,
                roll_results=roll_results or {},
                messages=recent_messages,
            )

            try:
                await self._publish_ai_thinking(request.session_id, True)
                gm_agent = self._gm_for_phase(phase_value)
                gm_candidate = await gm_agent.think(context)
                gm_response = self._as_agent_response(gm_candidate)
            except Exception as exc:
                logger.error("ActionPipeline : GMAgent echoue : %s", exc)
            finally:
                await self._publish_ai_thinking(request.session_id, False)

        if gm_response and phase_value == "COMBAT":
            gm_response = self._with_social_roll_fallback(
                gm_response,
                request,
                target_id,
                active.state_data,
            )
        if gm_response and roll_results and roll_results.get("type") == "skill_check":
            gm_response = self._without_redundant_social_roll_requests(
                gm_response,
                roll_results,
            )

        if gm_response:
            active.last_gm_intent = gm_response.action_intent
        elif (
            is_sober_mode()
            and phase_value != "COMBAT"
            and is_pure_companion_social_prompt(request.action_type, request.content)
        ):
            active.last_gm_intent = "social"
        else:
            active.last_gm_intent = None

        has_gm_roll_request = bool(
            gm_response
            and any(gm_action.type == "roll_request" for gm_action in gm_response.actions)
        )

        # Garde-fou hors-combat : si le MJ n'a pas émis de roll_request pour une
        # action libre contenant un verbe risqué (et qu'aucun résultat mécanique
        # n'existe déjà), on injecte un roll_request minimal de sauvegarde.
        # Conservateur : ne s'applique qu'en exploration, sur free_text humain.
        if (
            not has_gm_roll_request
            and not roll_results
            and phase_value == "EXPLORATION"
            and request.action_type == "free_text"
            and request.actor_kind == "player"
        ):
            fallback_roll = _infer_risky_roll_request(request.content or "")
            if fallback_roll and gm_response is not None:
                gm_response.actions.append(
                    GMAction(
                        type=fallback_roll["type"],
                        target=fallback_roll.get("target"),
                        params=fallback_roll.get("params", {}),
                    )
                )
                has_gm_roll_request = True
                logger.debug(
                    "ActionPipeline : roll_request fallback injecte pour action risquee : %r",
                    request.content,
                )

        if gm_response and phase_value == "COMBAT":
            gm_response = self._without_combat_damage_actions(gm_response)

        if gm_response and not has_gm_roll_request:
            prime_combat_from_hostile_narration(
                active,
                gm_response.content,
                source="gm_narration",
            )

        # 3. Evenement canonique de jet mecanique initial.
        if roll_results:
            roll_evt = mechanics._normalize_roll_event(roll_results)
            roll_evt = self._enrich_roll_event(roll_evt, request, actor_name, target_id)
            roll_events.append(roll_evt)
            await self._event_bus.publish_to_session(
                request.session_id,
                EventType.ROLL_RESULT,
                roll_evt,
                source=self._source,
            )

        if request.suppress_gm_narration:
            narration_text = ""
        elif gm_response:
            narration_text = gm_response.content
        elif use_gm:
            narration_text = _FALLBACK_NARRATION
        else:
            narration_text = self._deterministic_narration(
                request,
                actor_name,
                target_name,
                roll_results,
            )
        final_narration = narration_text
        if not has_gm_roll_request and narration_text:
            await self._publish_gm_narration(request.session_id, narration_text, actual_db)

        # 4. Actions GM initiales. Si roll_request, l'outcome narrera le resultat.
        pending_rolls: list[dict[str, Any]] = []
        if gm_response:
            exec_result = await self._executor.execute_gm_response(
                gm_response,
                active,
                actual_db,
                session_id=request.session_id,
                fallback_actor_id=request.actor_id,
                social_roll_results=roll_results,
            )
            pending_rolls.extend(exec_result.pending_rolls)
            roll_events.extend(exec_result.pending_rolls)
            executed_actions.extend(exec_result.executed_actions)
            canon_dirty = canon_dirty or exec_result.canon_dirty

        if has_gm_roll_request and not pending_rolls:
            prime_combat_from_hostile_narration(
                active,
                narration_text,
                source="gm_narration",
            )
            if narration_text:
                await self._publish_gm_narration(request.session_id, narration_text, actual_db)

        # 5. Narration finale des jets demandes par le GM.
        if pending_rolls:
            if context is None:
                logger.warning("ActionPipeline : jets GM en attente sans contexte de narration.")
                context = AgentContext(
                    session_id=request.session_id,
                    game_phase=phase_value,
                    game_state=await self._game_state_for_gm(
                        request.session_id,
                        active,
                        actual_db,
                    ),
                    player_action=prompt_action_text,
                    roll_results=roll_results or {},
                    messages=[],
                )
            outcome_response = await self._narrate_outcome(
                request.session_id,
                context,
                pending_rolls,
                gm_agent=self._gm_for_phase(phase_value),
            )
            if outcome_response and outcome_response.narration:
                final_narration = outcome_response.narration
                prime_combat_from_hostile_narration(
                    active,
                    final_narration,
                    source="gm_roll_outcome",
                )
                await self._publish_gm_narration(
                    request.session_id,
                    final_narration,
                    actual_db,
                )
                outcome_exec = await self._executor.execute_gm_response(
                    outcome_response,
                    active,
                    actual_db,
                    session_id=request.session_id,
                    fallback_actor_id=request.actor_id,
                    social_roll_results=(
                        pending_rolls[0]
                        if pending_rolls
                        and (
                            pending_rolls[0].get("type") == "skill_check"
                            or pending_rolls[0].get("social_target_id")
                        )
                        else None
                    ),
                )
                roll_events.extend(outcome_exec.pending_rolls)
                executed_actions.extend(outcome_exec.executed_actions)
                canon_dirty = canon_dirty or outcome_exec.canon_dirty
            elif narration_text:
                await self._publish_gm_narration(
                    request.session_id,
                    narration_text,
                    actual_db,
                )

        if canon_dirty and actual_db is not None:
            try:
                from app.services import campaign_dossier_service

                await campaign_dossier_service.synthesize_canon_for_session(
                    request.session_id,
                    active.state_data,
                    [],
                    actual_db,
                )
            except Exception as exc:
                logger.warning("Synthese canon campagne ignoree : %s", exc)

        return ResolvedAction(
            actor_id=request.actor_id,
            actor_name=actor_name,
            actor_kind=request.actor_kind,
            action_type=request.action_type,
            target_id=target_id,
            mechanics=roll_results or {},
            roll_events=roll_events,
            narration=final_narration,
            gm_actions=executed_actions,
            canon_dirty=canon_dirty,
        )

    def _get_mechanics(self) -> Any:
        if self._mechanics is None:
            from app.game.action_resolver import ActionResolver

            self._mechanics = ActionResolver(gm_agent=self._gm)
        return self._mechanics

    def _gm_for_phase(self, phase_value: str) -> Any:
        return self._combat_gm if phase_value.upper() == "COMBAT" else self._gm

    async def _game_state_for_gm(
        self,
        session_id: str,
        active: ActiveSession,
        db: Optional[Any],
    ) -> dict[str, Any]:
        game_state = dict(active.state_data)
        if db is not None:
            try:
                game_state["world_maps"] = await campaign_dossier_service.map_context_for_session(
                    session_id,
                    db,
                    active.state_data,
                )
            except Exception as exc:
                logger.debug("ActionPipeline : contexte cartes indisponible : %s", exc)
        return game_state

    @staticmethod
    def _deterministic_narration(
        request: ActionRequest,
        actor_name: str,
        target_name: str,
        roll_results: Optional[dict[str, Any]],
    ) -> str:
        action = request.action_type.strip().lower()
        target_label = target_name or "la cible"

        if is_pure_companion_social_prompt(request.action_type, request.content):
            return ""

        if action == "attack" and roll_results:
            hit = bool(roll_results.get("hit"))
            critical = bool(roll_results.get("critical"))
            if hit:
                damage = int(roll_results.get("damage", {}).get("total", 0))
                crit_text = " d'un coup critique" if critical else ""
                return f"{actor_name} touche {target_label}{crit_text} et inflige {damage} degats."
            return f"{actor_name} attaque {target_label}, mais manque sa cible."

        if action == "cast_spell" and roll_results:
            summary = str(roll_results.get("summary") or "").strip()
            spell_name = str(roll_results.get("spell_name") or "un sort")
            if summary:
                return f"{actor_name} lance {spell_name}. {summary}."
            return f"{actor_name} lance {spell_name} vers {target_label}."

        if action == "death_save" and roll_results:
            return str(roll_results.get("summary") or f"{actor_name} lutte pour survivre.")

        if action == "stabilize" and roll_results:
            if roll_results.get("success"):
                return f"{actor_name} stabilise {target_label}."
            return f"{actor_name} tente de stabiliser {target_label}, sans y parvenir."

        if action == "dodge":
            return f"{actor_name} se met en defense."
        if action == "dash":
            return f"{actor_name} se deplace aussi vite que possible."
        if action == "disengage":
            return f"{actor_name} se degage prudemment de la melee."
        if action == "hide":
            return f"{actor_name} cherche un couvert et tente de se dissimuler."
        if action == "wait":
            return f"{actor_name} temporise et observe le combat."

        display = request.display_text or request.content
        if display:
            return str(display)
        return f"{actor_name} agit."

    async def _publish_ai_thinking(self, session_id: str, thinking: bool) -> None:
        await self._orchestrator.publish_ai_thinking(session_id, thinking)

    async def _publish_tactical_move_result(
        self,
        session_id: str,
        combatant_id: Optional[str],
        move_result: Any,
        active: ActiveSession,
    ) -> None:
        if not combatant_id or not move_result.valid or move_result.final_position is None:
            return
        await self._event_bus.publish_to_session(
            session_id,
            EventType.COMBATANT_MOVED,
            {
                "combatant_id": combatant_id,
                "position": move_result.final_position.to_dict(),
                "movement_used_m": move_result.movement_used_m,
                "path": [step.to_dict() for step in move_result.path],
                "interrupted": move_result.interrupted,
                "reason": move_result.reason,
            },
            source=self._source,
        )
        current = active.turn_manager.current_turn
        if current is not None and current.combatant_id == combatant_id:
            payload: dict[str, Any] = {
                "combatant_id": combatant_id,
                "action_economy": getattr(
                    current.action_economy,
                    "__dict__",
                    current.action_economy,
                ),
            }
            reachable = calculate_reachable_cells(active, combatant_id)
            if reachable is not None:
                payload["reachable_cells"] = reachable
            await self._event_bus.publish_to_session(
                session_id,
                EventType.ACTION_ECONOMY_CHANGED,
                payload,
                source=self._source,
            )

    async def _execute_tactical_move_request(
        self,
        request: ActionRequest,
        active: ActiveSession,
    ) -> tuple[bool, str, Any]:
        if not request.actor_id:
            return False, "Combattant introuvable.", None
        destination = self._parse_move_destination(request.content)
        if destination is None:
            return False, "Format de déplacement invalide. Attendu: 'col,row'", None

        combatants = active.state_data.get("combatants") or {}
        mover_data = combatants.get(request.actor_id, {})
        if not isinstance(mover_data, dict):
            mover_data = {}
        current = active.turn_manager.current_turn
        economy = (
            current.action_economy
            if current is not None and current.combatant_id == request.actor_id
            else None
        )
        movement_m = float(
            economy.movement if economy is not None else combatant_speed_m(mover_data)
        )
        move_result = await apply_tactical_move(
            session_id=request.session_id,
            active=active,
            mover_id=request.actor_id,
            destination=destination,
            event_bus=self._event_bus,
            movement_m=movement_m,
            source=self._source,
        )
        if not move_result.valid:
            return False, f"Déplacement invalide : {move_result.reason}", move_result
        if economy is not None and not economy.spend_movement(move_result.movement_used_m):
            return False, "Mouvement insuffisant pour ce déplacement.", move_result
        await self._publish_tactical_move_result(
            request.session_id,
            request.actor_id,
            move_result,
            active,
        )
        return True, "", move_result

    @staticmethod
    def _parse_move_destination(content: Optional[str]) -> Optional[GridPosition]:
        if not content or "," not in content:
            return None
        try:
            col_text, row_text = content.split(",", 1)
            return GridPosition(col=int(col_text.strip()), row=int(row_text.strip()))
        except (TypeError, ValueError):
            return None

    async def _publish_action_economy_result(
        self,
        active: ActiveSession,
        combatant_id: Optional[str],
    ) -> None:
        if not combatant_id:
            return
        current = active.turn_manager.current_turn
        if current is None or current.combatant_id != combatant_id:
            return
        payload: dict[str, Any] = {
            "combatant_id": combatant_id,
            "action_economy": getattr(
                current.action_economy,
                "__dict__",
                current.action_economy,
            ),
        }
        reachable = calculate_reachable_cells(active, combatant_id)
        if reachable is not None:
            payload["reachable_cells"] = reachable
        await self._event_bus.publish_to_session(
            active.session_id,
            EventType.ACTION_ECONOMY_CHANGED,
            payload,
            source=self._source,
        )

    async def _publish_gm_narration(
        self,
        session_id: str,
        narration_text: str,
        db: Optional[Any],
    ) -> None:
        await self._orchestrator.publish_gm_narration(session_id, narration_text, db)

    async def _narrate_outcome(
        self,
        session_id: str,
        context: AgentContext,
        pending_rolls: list[dict[str, Any]],
        *,
        gm_agent: Optional[Any] = None,
    ) -> Optional[GMResponse]:
        outcome_response: Optional[GMResponse] = None
        agent = gm_agent or self._gm_for_phase(context.game_phase)
        try:
            await self._publish_ai_thinking(session_id, True)
            try:
                outcome_candidate = await agent.narrate_outcome_response(
                    context,
                    pending_rolls,
                )
            except (AttributeError, TypeError):
                outcome_candidate = await agent.narrate_outcome(context, pending_rolls)

            if isinstance(outcome_candidate, GMResponse):
                outcome_response = outcome_candidate
            elif isinstance(outcome_candidate, AgentResponse):
                outcome_response = GMResponse(
                    narration=outcome_candidate.content,
                    actions=outcome_candidate.actions,
                    action_intent=outcome_candidate.action_intent,
                )
            elif outcome_candidate is not None:
                outcome_response = GMResponse(narration=str(outcome_candidate))
        except Exception as exc:
            logger.error("ActionPipeline : narrate_outcome echoue : %s", exc)
        finally:
            await self._publish_ai_thinking(session_id, False)
        return outcome_response

    async def _persist_actor_action(
        self,
        session_id: str,
        visible_text: str,
        actor_name: str,
        request: ActionRequest,
        target_id: Optional[str],
        db: Optional[Any],
    ) -> None:
        if db is None:
            return

        from app.models.message import MessageRole, MessageType
        from app.services.message_service import persist_narration

        metadata: dict[str, Any] = {
            "action_type": request.action_type,
            "character_id": request.actor_id,
            "actor_kind": request.actor_kind,
            "target": target_id,
        }
        if request.actor_kind == "companion":
            metadata["is_ai_player"] = True

        await persist_narration(
            session_id,
            visible_text,
            actor_name,
            db,
            role=MessageRole.PLAYER,
            message_type=MessageType.ACTION,
            metadata=metadata,
        )

    @staticmethod
    def _as_agent_response(candidate: Any) -> Optional[AgentResponse]:
        if isinstance(candidate, AgentResponse):
            return candidate
        if isinstance(candidate, GMResponse):
            return AgentResponse(
                content=candidate.narration,
                actions=candidate.actions,
                action_intent=candidate.action_intent,
            )
        if candidate is None:
            return None
        return AgentResponse(content=str(candidate), actions=[])

    @staticmethod
    def _with_social_roll_fallback(
        response: AgentResponse,
        request: ActionRequest,
        social_target_id: Optional[str],
        state_data: dict[str, Any],
    ) -> AgentResponse:
        if (
            request.actor_kind != "player"
            or request.action_type != "free_text"
            or not request.actor_id
            or not _is_combat_social_text(request.content)
        ):
            return response

        if any(
            gm_action.type in {"roll_request", "combatant_status"} for gm_action in response.actions
        ):
            return response

        dc = _calculate_social_dc(state_data, social_target_id, None)
        actions = [
            *response.actions,
            GMAction(
                type="roll_request",
                target=request.actor_id,
                params={
                    "ability": "cha",
                    "type": "check",
                    "dc": dc,
                    "reason": "social_combat",
                    "social_target": social_target_id,
                },
            ),
        ]
        return AgentResponse(
            content=response.content,
            actions=actions,
            action_intent=response.action_intent or "mixed",
        )

    @staticmethod
    def _resolve_social_check(
        request: ActionRequest,
        active: ActiveSession,
    ) -> Optional[dict[str, Any]]:
        """Resout un jet de competence social en exploration via le moteur.

        Retourne un dict roll_results injecte dans le contexte GM pour narration.
        Le LLM ne resout jamais le jet ; il recoit le resultat deterministe.
        """
        if not request.actor_id or not request.content:
            return None

        skill = _detect_social_skill(request.content)
        if not skill:
            return None

        social_target_id = resolve_npc_target_id(
            request.content,
            active.state_data,
            request.target_id,
        )
        dc = _calculate_social_dc(active.state_data, social_target_id, skill)

        characters = active.state_data.get("characters", {})
        char_data = characters.get(request.actor_id, {}) if isinstance(characters, dict) else {}
        if not isinstance(char_data, dict):
            return None

        ability = SKILL_ABILITY.get(skill, Ability.CHA)
        ab_key = _ability_short_key(ability)
        ability_scores = char_data.get("ability_scores", {})
        if not isinstance(ability_scores, dict):
            ability_scores = {}
        score = int(
            ability_scores.get(
                ab_key,
                ability_scores.get(ability.value if isinstance(ability, Ability) else "", 10),
            )
        )
        level = int(char_data.get("level", 1))
        skill_profs = _normalized_skill_proficiencies(char_data)
        prof = Proficiency.PROFICIENT if skill in skill_profs else Proficiency.NONE

        result = skill_check(score, skill, level, prof, dc)
        skill_label = skill.replace("_", " ").title()
        outcome = "succès" if result.success else "échec"
        summary = f"{result.label} : {result.breakdown} ({outcome})"
        roll_results: dict[str, Any] = {
            "type": "skill_check",
            "skill": skill,
            "dice_notation": "1d20",
            "rolls": result.all_rolls,
            "d20": result.d20_roll,
            "d20_roll": result.d20_roll,
            "modifier": result.modifier,
            "total": result.total,
            "dc": result.dc,
            "success": result.success,
            "label": result.label or skill_label,
            "breakdown": result.breakdown,
            "summary": summary,
            "target_id": social_target_id,
            "social_target_id": social_target_id,
            "actor_id": request.actor_id,
        }

        if social_target_id:
            npc_states = active.state_data.setdefault("npc_states", {})
            if not isinstance(npc_states, dict):
                npc_states = {}
                active.state_data["npc_states"] = npc_states
            npc = npc_states.setdefault(social_target_id, {})
            if isinstance(npc, dict):
                npc.setdefault("name", social_target_id)
                npc.setdefault("attitude", "indifferent")
                npc["last_interaction_turn"] = active.state_data.get("turn_number", 0)
        return roll_results

    @staticmethod
    def _without_redundant_social_roll_requests(
        response: AgentResponse,
        roll_results: dict[str, Any],
    ) -> AgentResponse:
        if roll_results.get("type") != "skill_check":
            return response
        actions = [gm_action for gm_action in response.actions if gm_action.type != "roll_request"]
        if len(actions) == len(response.actions):
            return response
        logger.warning(
            "ActionPipeline : roll_request GM ignore ; le skill_check social est deja resolu."
        )
        return AgentResponse(
            content=response.content,
            actions=actions,
            action_intent=response.action_intent,
        )

    @staticmethod
    def _without_combat_damage_actions(response: AgentResponse) -> AgentResponse:
        actions = [gm_action for gm_action in response.actions if gm_action.type != "damage_apply"]
        if len(actions) == len(response.actions):
            return response
        logger.warning(
            "ActionPipeline : damage_apply GM ignore en combat ; les degats viennent du moteur."
        )
        return AgentResponse(
            content=response.content,
            actions=actions,
            action_intent=response.action_intent,
        )

    @staticmethod
    def _enrich_roll_event(
        payload: dict[str, Any],
        request: ActionRequest,
        actor_name: str,
        target_id: Optional[str],
    ) -> dict[str, Any]:
        enriched = dict(payload)
        enriched.setdefault("character_id", request.actor_id)
        enriched["actor_id"] = request.actor_id
        enriched["actor_name"] = actor_name
        enriched["actor_kind"] = request.actor_kind
        enriched["action_type"] = request.action_type
        enriched["target_id"] = target_id
        return enriched

    @classmethod
    def _prompt_action_text(
        cls,
        request: ActionRequest,
        actor_name: str,
        target_name: str,
        roll_results: Optional[dict[str, Any]],
    ) -> str:
        if request.content:
            text = request.content
            if (
                request.action_type == "free_text"
                and target_name
                and _is_combat_social_text(request.content)
            ):
                target_id = request.target_id or "unknown"
                text = f"{text} [Cible sociale : {target_name} ({target_id})]"
        elif request.action_type == "attack" and target_name:
            if request.actor_kind == "monster":
                text = f"[Tour du monstre] {actor_name} attaque {target_name}."
            else:
                text = f"{actor_name} attaque {target_name}."
        else:
            text = request.action_type

        if roll_results:
            text = f"{text} [Résultat mécanique : {roll_results.get('summary', '')}]"
        return text

    @classmethod
    def _display_text(
        cls,
        request: ActionRequest,
        actor_name: str,
        target_name: str,
    ) -> str:
        if request.display_text:
            return request.display_text
        if request.content:
            return request.content
        if request.action_type == "attack" and target_name:
            return f"{actor_name} attaque {target_name}."
        return request.action_type

    @staticmethod
    def _default_target_id(request: ActionRequest, state_data: dict[str, Any]) -> Optional[str]:
        combatants = state_data.get("combatants", {})
        if not isinstance(combatants, dict):
            return None

        if request.action_type == "free_text" and _is_combat_social_text(request.content):
            active_npcs: list[str] = []
            for combatant_id, cdata in combatants.items():
                if not isinstance(cdata, dict) or cdata.get("is_player", True):
                    continue
                status = str(cdata.get("status", "active")).lower()
                try:
                    hp = int(cdata.get("hp", 0))
                except (TypeError, ValueError):
                    hp = 0
                if hp > 0 and status not in INACTIVE_STATUSES:
                    active_npcs.append(combatant_id)
            return active_npcs[0] if len(active_npcs) == 1 else None

        if request.actor_kind != "monster" or request.action_type != "attack":
            return None

        return choose_attack_target(
            state_data,
            request.actor_id,
            actor_is_player=False,
        )

    @staticmethod
    def _actor_name(
        actor_id: Optional[str],
        actor_kind: str,
        state_data: dict[str, Any],
    ) -> str:
        fallback = {
            "player": "Joueur",
            "companion": "Compagnon",
            "monster": "Monstre",
        }.get(actor_kind, "Joueur")
        if not actor_id:
            return fallback

        characters = state_data.get("characters", {})
        if isinstance(characters, dict):
            cdata = characters.get(actor_id)
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])

        combatants = state_data.get("combatants", {})
        if isinstance(combatants, dict):
            cdata = combatants.get(actor_id)
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])
        return fallback

    @staticmethod
    def _combatant_name(state_data: dict[str, Any], combatant_id: Optional[str]) -> str:
        if not combatant_id:
            return ""
        combatants = state_data.get("combatants", {})
        if isinstance(combatants, dict):
            cdata = combatants.get(combatant_id)
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])
        characters = state_data.get("characters", {})
        if isinstance(characters, dict):
            cdata = characters.get(combatant_id)
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])
        return str(combatant_id)

    @staticmethod
    def _phase_value(active: ActiveSession) -> str:
        phase = active.phase
        return phase.value if hasattr(phase, "value") else str(phase)

    async def _apply_stabilize_success(
        self,
        session_id: str,
        target_id: Optional[str],
        roll_results: dict[str, Any],
        active: ActiveSession,
    ) -> None:
        if not roll_results.get("success") or not target_id:
            return
        combatants: dict[str, Any] = active.state_data.setdefault("combatants", {})
        if target_id not in combatants:
            return

        death_saves = combatants[target_id].setdefault(
            "death_saves",
            {"successes": 0, "failures": 0, "stable": False},
        )
        death_saves["stable"] = True
        conditions = list(combatants[target_id].get("conditions", []))
        if "inconscient" in conditions:
            conditions.remove("inconscient")
            combatants[target_id]["conditions"] = conditions
            await self._event_bus.publish_to_session(
                session_id,
                EventType.CONDITION_CHANGED,
                {"combatant_id": target_id, "condition": "inconscient", "added": False},
                source=self._source,
            )
        await self._event_bus.publish_to_session(
            session_id,
            EventType.DEATH_SAVE_UPDATED,
            {"combatant_id": target_id, "death_saves": dict(death_saves)},
            source=self._source,
        )
        active.mark_dirty()
