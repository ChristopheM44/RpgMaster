"""AI player manager — triggers PlayerAgent actions during AI combatant turns.

Integrates with TurnManager: when the current turn belongs to an AI-controlled
player character, this module calls PlayerAgent.decide_action() (or .roleplay()),
validates the result, and dispatches it through ActionResolver. Monster turns
are handled by the combat WebSocket loop, not by PlayerAgent.

Usage::

    from app.game.ai_player_manager import AIPlayerManager

    ai_manager = AIPlayerManager()

    # After a human action resolves, trigger any consecutive AI turns:
    triggered = await ai_manager.process_ai_turns(session_id, active, action_resolver)
"""

from __future__ import annotations

import logging
import re
import unicodedata
import uuid
from inspect import isawaitable
from typing import TYPE_CHECKING, Any

from app.agents.schemas import PlayerActionChoice
from app.game.action_mechanics import _load_spells
from app.game.companion_visibility import (
    companion_visible_game_state,
    sanitize_companion_visible_text,
)
from app.game.constants import INACTIVE_STATUSES
from app.game.event_bus import EventType, event_bus
from app.game.visible_events import publish_visible_entry
from app.llm.budget import (
    is_sober_mode,
)
from app.logging_utils import log_degraded

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.game.action_resolver import ActionResolver
    from app.game.session_manager import ActiveSession

logger = logging.getLogger(__name__)

_WAIT_ACTION = PlayerActionChoice(
    action_type="wait",
    action_description="Le personnage attend son tour.",
    roleplay_text="(attend, sur la défensive)",
    inner_reasoning="Fallback : aucune action valide disponible.",
)

_COMBAT_STARTING_ACTIONS = {"attack", "shove"}
_COMPANION_SPOTLIGHT_KEY = "_companion_spotlight_recent"

# Actions d'exploration qui nécessitent un arbitrage MJ (résolution moteur + narration).
# talk/wait sont purement narratifs et ne déclenchent PAS le pipeline MJ.
_EXPLORATION_ARBITRAGE_ACTIONS = {"examine", "move", "use_item", "help", "cast_spell"}
_MECHANICAL_ACTION_TYPES = (
    _COMBAT_STARTING_ACTIONS
    | _EXPLORATION_ARBITRAGE_ACTIONS
    | {"dash", "disengage", "dodge", "hide", "stabilize", "death_save", "wait"}
)


# Mots-clés de scène → classes/traits affinitaires
# Format : {keyword_normalized: {class_slug, ...}}
_SPECIALTY_AFFINITY: dict[str, set[str]] = {
    # Arcane / magie
    "magique": {"wizard", "mage", "sorcerer", "magicien", "ensorceleur", "bard", "barde"},
    "rune": {"wizard", "mage", "magicien", "ensorceleur"},
    "arcane": {"wizard", "mage", "magicien", "ensorceleur", "sorcerer"},
    "sort": {"wizard", "mage", "sorcerer", "magicien", "ensorceleur", "bard", "barde"},
    "incantation": {"wizard", "mage", "sorcerer", "magicien"},
    "cristal": {"wizard", "mage", "sorcerer", "magicien"},
    "enchantement": {"wizard", "mage", "sorcerer", "bard", "barde"},
    # Divine / soin
    "sacre": {"cleric", "clerc", "paladin"},
    "divin": {"cleric", "clerc", "paladin"},
    "temple": {"cleric", "clerc", "paladin"},
    "sanctuaire": {"cleric", "clerc", "paladin"},
    "beni": {"cleric", "clerc", "paladin"},
    "maledi": {"cleric", "clerc", "paladin"},
    # Nature / plantes
    "plante": {"ranger", "rodeur", "druid", "druide"},
    "herbe": {"ranger", "rodeur", "druid", "druide"},
    "foret": {"ranger", "rodeur", "druid", "druide"},
    "bete": {"ranger", "rodeur", "druid", "druide"},
    "animal": {"ranger", "rodeur", "druid", "druide"},
    # Discrétion / pièges / serrures
    "serrure": {"rogue", "roublard", "ranger", "rodeur"},
    "piege": {"rogue", "roublard", "ranger", "rodeur"},
    "secret": {"rogue", "roublard"},
    "cache": {"rogue", "roublard"},
    "passage": {"rogue", "roublard", "ranger", "rodeur"},
    "mecanisme": {"rogue", "roublard"},
}


def _companion_specialty_score(char_id: str, state_data: dict[str, Any], action_text: str) -> int:
    """Retourne un score de pertinence pour un compagnon face au contexte d'action.

    Score 0 = pas de correspondance. Score positif = affinité détectée.
    """
    normalized_text = unicodedata.normalize("NFKD", action_text.lower())
    normalized_text = "".join(ch for ch in normalized_text if not unicodedata.combining(ch))

    cdata = (state_data.get("characters") or {}).get(char_id, {})
    cls_raw = str(cdata.get("class", cdata.get("cls", ""))).lower()
    cls_norm = unicodedata.normalize("NFKD", cls_raw)
    cls_norm = "".join(ch for ch in cls_norm if not unicodedata.combining(ch))

    traits = cdata.get("personality", cdata.get("traits", [])) or []
    traits_norm = {
        "".join(
            ch
            for ch in unicodedata.normalize("NFKD", str(t).lower())
            if not unicodedata.combining(ch)
        )
        for t in traits
        if t
    }

    score = 0
    for keyword, affine_classes in _SPECIALTY_AFFINITY.items():
        if keyword not in normalized_text:
            continue
        if cls_norm in affine_classes or traits_norm & affine_classes:
            score += 1

    return score


def order_companion_spotlight(
    active: ActiveSession,
    candidate_ids: list[str],
    *,
    trigger_character_id: str | None = None,
    max_count: int | None = None,
    action_text: str | None = None,
) -> list[str]:
    """Prefer companions who have not had the recent spotlight.

    This keeps table chatter varied without forcing every companion to speak.
    The list stored in state_data is ordered oldest → newest.

    Si ``action_text`` est fourni, les compagnons dont la classe ou les traits
    correspondent aux mots-clés de la scène sont prioritaires (biais spécialité).
    """
    seen: set[str] = set()
    available: list[str] = []
    for char_id in candidate_ids:
        if char_id == trigger_character_id or char_id in seen:
            continue
        if char_id not in active.ai_players:
            continue
        seen.add(char_id)
        available.append(char_id)
    if len(available) <= 1:
        return available[:max_count] if max_count is not None else available

    raw_recent = active.state_data.get(_COMPANION_SPOTLIGHT_KEY, [])
    recent = [str(char_id) for char_id in raw_recent if str(char_id) in available]
    recent_rank = {char_id: index for index, char_id in enumerate(recent)}
    original_rank = {char_id: index for index, char_id in enumerate(available)}

    # Calcul du score spécialité si un contexte d'action est fourni
    specialty_scores: dict[str, int] = {}
    if action_text:
        specialty_scores = {
            char_id: _companion_specialty_score(char_id, active.state_data, action_text)
            for char_id in available
        }
    max_specialty = max(specialty_scores.values(), default=0)

    ordered = sorted(
        available,
        key=lambda char_id: (
            # 1. Spécialité : compagnons affinitaires en premier (si détectée)
            -(specialty_scores.get(char_id, 0) if max_specialty > 0 else 0),
            # 2. Pas de surexposition récente
            char_id in recent_rank,
            recent_rank.get(char_id, -1),
            # 3. Ordre original (stabilité)
            original_rank[char_id],
        ),
    )
    return ordered[:max_count] if max_count is not None else ordered


def record_companion_spotlight(active: ActiveSession, character_id: str) -> None:
    """Remember that a companion just spoke or visibly acted."""
    char_id = str(character_id)
    ai_ids = set(active.ai_players.keys())
    if char_id not in ai_ids:
        return
    raw_recent = active.state_data.get(_COMPANION_SPOTLIGHT_KEY, [])
    recent = [
        str(existing)
        for existing in raw_recent
        if str(existing) in ai_ids and str(existing) != char_id
    ]
    recent.append(char_id)
    active.state_data[_COMPANION_SPOTLIGHT_KEY] = recent[-max(1, len(ai_ids)) :]
    active.mark_dirty()


def _detect_reaction_mode(recent_messages: list) -> str:
    """Détecte si on est en ouverture de scène (open_scene) ou après une action joueur (follow_up).

    Remonte l'historique en ignorant les messages des compagnons IA.
    - Dernier message non-IA de rôle 'player' → follow_up (joueur humain a agi).
    - Dernier message non-IA de rôle 'gm' en premier → open_scene (aucune action humaine depuis).
    """
    for msg in reversed(recent_messages):
        role = getattr(msg, "role", None)
        role_val = role.value if hasattr(role, "value") else str(role)
        metadata = getattr(msg, "metadata", None) or {}
        if isinstance(metadata, dict) and metadata.get("is_ai_player"):
            continue  # Ignorer les répliques des compagnons IA
        if role_val == "player":
            return "follow_up"
        if role_val == "gm":
            return "open_scene"
    return "open_scene"


def _build_scene_context(messages: list) -> str:
    """Construit un résumé de scène à partir des derniers messages persistés.

    Extrait le dernier message du MJ et le dernier message joueur pour que le
    compagnon IA sache ce qui vient de se passer sans ingérer l'historique entier.
    """
    last_gm: str | None = None
    last_player: str | None = None
    for msg in reversed(messages):
        role = getattr(msg, "role", None)
        role_val = role.value if hasattr(role, "value") else str(role)
        if last_gm is None and role_val == "gm":
            last_gm = f"[Narration MJ] {msg.content}"
        if last_player is None and role_val == "player":
            speaker = getattr(msg, "speaker", "Joueur")
            last_player = f"[{speaker}] {msg.content}"
        if last_gm and last_player:
            break
    return "\n".join(p for p in [last_gm, last_player] if p)


def register_ai_player(active: ActiveSession, char_id: str, cdata: dict[str, Any]) -> None:
    """Instancie et enregistre un PlayerAgent pour un compagnon IA donné.

    Idempotent : ne recrée pas l'agent s'il est déjà présent dans
    ``active.ai_players``. Ignore les entrées non-IA.

    Priorité de chargement de la personnalité :
    1. ``cdata['persona']`` (CompanionPersona dump — nouveau format)
    2. ``cdata['personality']`` (PlayerPersonality / list traits / string — legacy)
    """
    from app.agents.persona import CompanionPersona
    from app.agents.player_agent import PlayerAgent, PlayerPersonality

    if not cdata.get("is_ai", False):
        return
    if char_id in active.ai_players:
        return

    character_name = cdata.get("name", char_id)
    persona: PlayerPersonality | CompanionPersona

    raw_persona = cdata.get("persona")
    if isinstance(raw_persona, dict) and raw_persona.get("persona_type") == "companion":
        try:
            persona = CompanionPersona.model_validate(raw_persona)
        except Exception as exc:
            logger.warning(
                "register_ai_player: CompanionPersona invalide pour %s : %s — fallback legacy.",
                char_id,
                exc,
            )
            persona = _legacy_personality(cdata)
    else:
        persona = _legacy_personality(cdata)

    active.ai_players[char_id] = PlayerAgent(
        character_id=char_id,
        character_name=character_name,
        personality=persona,
    )
    logger.info(
        "register_ai_player: PlayerAgent enregistré pour '%s' (%s).",
        character_name,
        char_id,
    )


def _legacy_personality(cdata: dict[str, Any]) -> Any:
    """Construit un PlayerPersonality à partir de l'ancien champ ``personality``."""
    from app.agents.player_agent import PlayerPersonality

    raw = cdata.get("personality") or ["brave"]
    if isinstance(raw, str):
        traits: list[str] = [raw]
    elif isinstance(raw, dict):
        traits = list(raw.get("traits") or ["brave"])
    else:
        traits = list(raw)
    return PlayerPersonality(traits=traits)


def unregister_ai_player(active: ActiveSession, char_id: str) -> None:
    """Retire le PlayerAgent d'un personnage (passage sous contrôle humain)."""
    if active.ai_players.pop(char_id, None) is not None:
        logger.info("unregister_ai_player: PlayerAgent retiré pour %s.", char_id)


def rebuild_ai_players(active: ActiveSession) -> int:
    """Reconstruit le registre ``ai_players`` à partir de ``state_data['characters']``.

    Appelé à l'ouverture d'une session pour restaurer les agents après un
    redémarrage backend, un ``load_save`` ou une fermeture/réouverture.

    Retourne le nombre d'agents (re)créés.
    """
    characters = active.state_data.get("characters") or {}
    before = len(active.ai_players)
    for char_id, cdata in characters.items():
        register_ai_player(active, char_id, cdata)
    created = len(active.ai_players) - before
    if created:
        logger.info(
            "rebuild_ai_players: %d agent(s) reconstruit(s) pour la session %s.",
            created,
            active.session_id,
        )
    return created


class AIPlayerManager:
    """Orchestrates AI companion turns within a game session.

    After each human player action, call :meth:`process_ai_turns` to let all
    consecutive AI-controlled player characters act before the next human or
    monster turn.

    The method stops as soon as a non-player, non-AI, or missing turn is reached
    (or the order is exhausted), so it is safe to call unconditionally.
    """

    async def process_ai_turns(
        self,
        session_id: str,
        active: ActiveSession,
        action_resolver: ActionResolver,
        db: AsyncSession | None = None,
        max_turns: int | None = None,
    ) -> int:
        """Trigger all consecutive AI-controlled PC turns from the current entry.

        Args:
            session_id: Active session identifier (for event publishing).
            active: In-memory session state (provides turn_manager and ai_players).
            action_resolver: Pipeline that resolves actions through engine + GM agent.
            max_turns: Optional cap on processed AI PC turns. ``None`` keeps the
                legacy batch behavior.

        Returns:
            The number of AI actions triggered this call.
        """
        triggered = 0

        while True:
            current = active.turn_manager.current_turn
            if current is None or not current.is_ai_controlled:
                break
            if not current.is_player:
                break

            agent = active.ai_players.get(current.combatant_id)
            if agent is None:
                logger.warning(
                    "AIPlayerManager: no PlayerAgent registered for AI combatant '%s' — skipping.",
                    current.combatant_id,
                )
                active.turn_manager.next_turn()
                continue

            available_actions = self._available_combat_actions(
                current.combatant_id,
                active.state_data,
            )
            if active.phase.value == "combat" and is_sober_mode():
                action = self._build_deterministic_combat_action(
                    current.combatant_id,
                    current.name,
                    active.state_data,
                    available_actions,
                )
            else:
                # Ask the agent for an action
                await self._publish_thinking(
                    session_id,
                    True,
                    character_id=current.combatant_id,
                    character_name=current.name,
                )
                try:
                    action = await self._get_action(agent, active, available_actions)
                finally:
                    await self._publish_thinking(
                        session_id,
                        False,
                        character_id=current.combatant_id,
                        character_name=current.name,
                    )

            if action.llm_error:
                await event_bus.publish_to_session(
                    session_id,
                    EventType.ERROR,
                    {
                        "source": "player_agent",
                        "character": current.name,
                        "message": (
                            f"Le compagnon IA {current.name} est temporairement indisponible."
                        ),
                    },
                    source="ai_player_manager",
                )
                active.turn_manager.next_turn()
                active.mark_dirty()
                triggered += 1
                continue

            spell_id: str | None = None
            slot_level: int | None = None
            if active.phase.value == "combat":
                action, spell_id, slot_level = self._normalize_combat_action(
                    action,
                    current.combatant_id,
                    active,
                    available_actions,
                )

            # Pre-validate before dispatching to the engine
            is_valid, reason = agent.validate_action(action, active.state_data)
            if not is_valid:
                logger.warning(
                    "AIPlayerManager: action '%s' invalid for '%s': %s — using fallback.",
                    action.action_type,
                    current.name,
                    reason,
                )
                if active.phase.value == "combat":
                    if self._character_can_act(current.combatant_id, active.state_data):
                        action = self._build_fallback_combat_action(
                            current.combatant_id,
                            current.name,
                            active.state_data,
                            available_actions,
                        )
                    else:
                        action = _WAIT_ACTION
                    spell_id = None
                    slot_level = None
                else:
                    action = _WAIT_ACTION

            visible_text = self._visible_action_text(action, current.name)
            scene_id = str(uuid.uuid4())
            entry_kind = "dialogue" if action.action_type == "talk" else "action"

            # Broadcast the AI player's visible intention first
            await publish_visible_entry(
                event_bus,
                session_id,
                {
                    "text": visible_text,
                    "speaker": current.name,
                    "speaker_id": current.combatant_id,
                    "speaker_kind": "companion",
                    "entry_kind": entry_kind,
                    "action_type": action.action_type,
                    "is_ai_player": True,
                    "scene_id": scene_id,
                },
                source="ai_player_manager",
            )

            if db is not None and action.action_type in {"talk", "wait"}:
                from app.models.message import MessageRole, MessageType
                from app.services.message_service import persist_narration

                await persist_narration(
                    session_id,
                    visible_text,
                    current.name,
                    db,
                    role=MessageRole.PLAYER,
                    message_type=(
                        MessageType.DIALOGUE if entry_kind == "dialogue" else MessageType.ACTION
                    ),
                    metadata={
                        "is_ai_player": True,
                        "speaker_id": current.combatant_id,
                        "speaker_kind": "companion",
                        "entry_kind": entry_kind,
                        "character_id": current.combatant_id,
                        "action_type": action.action_type,
                        "target": action.target,
                        "scene_id": scene_id,
                    },
                )

            # Full engine + GM pipeline for mechanical/arbitrated actions.
            if action.action_type not in {"talk", "wait"}:
                await action_resolver.resolve(
                    session_id=session_id,
                    action_type=action.action_type,
                    content=self._companion_action_content(action, current.name),
                    character_id=current.combatant_id,
                    target_id=action.target,
                    active=active,
                    db=db,
                    spell_id=spell_id,
                    slot_level=slot_level,
                    actor_kind="companion",
                    actor_name=current.name,
                    display_text=visible_text,
                )

            active.turn_number += 1
            active.mark_dirty()
            triggered += 1

            # Advance to the next combatant for the next iteration
            active.turn_manager.next_turn()
            if max_turns is not None and triggered >= max_turns:
                break

        return triggered

    async def run_exploration_reactions(
        self,
        session_id: str,
        active: ActiveSession,
        action_resolver: ActionResolver,
        trigger_character_id: str | None = None,
        db: AsyncSession | None = None,
        max_reactors: int | None = None,
        action_text: str | None = None,
    ) -> tuple[int, list[dict[str, str]]]:
        """Fait réagir une fois chaque compagnon IA en exploration.

        Contrairement à :meth:`process_ai_turns` (pensé pour le combat), cette
        méthode **ne modifie pas l'index** du turn manager : l'exploration reste
        en flux libre. Pour chaque entrée ``is_ai_controlled=True`` de l'ordre,
        on appelle ``agent.roleplay()`` avec l'historique récent puis, selon le
        type d'action :
          - talk / wait : publication + persistance, pas de pipeline MJ.
          - examine / move / use_item / help : pipeline MJ complet.
          - attack / shove : transition COMBAT si pending_encounter,
            sinon remplacement par une hésitation prudente.
          - cast_spell : arbitrage MJ en exploration quand le sort cible un
            obstacle, danger, POI ou effet environnemental.

        Le contexte (recent_messages, scene_context) est **rechargé après chaque
        réaction** pour que chaque compagnon voit ce que le précédent vient de dire.

        En mode ``open_scene`` (dernière narration = MJ, aucune action joueur
        humain depuis), un seul compagnon prend spontanément la parole — comme à
        une vraie table. En mode ``follow_up`` (action joueur présente), le cap
        est à 2 réactions maximum pour éviter la convergence.

        Args:
            session_id: session active.
            active: état mémoire.
            action_resolver: pour faire réagir le MJ après le roleplay IA.
            trigger_character_id: si défini, on saute ce personnage.
            db: session DB async pour charger l'historique et persister les actions.
            max_reactors: cap explicite sur le nombre de compagnons qui réagissent.
                Si None, le mode (open_scene / follow_up) fixe le cap automatiquement.

        Returns:
            Tuple (nombre de compagnons ayant réagi,
                   liste de dicts {"speaker": nom, "text": roleplay_text}).
        """
        if not active.ai_players:
            return 0, []

        # Chargement initial du contexte + détection du mode
        recent_messages: list = []
        scene_context = ""
        if db is not None:
            from app.services.message_service import load_recent_messages

            recent_messages = await load_recent_messages(session_id, db)
            scene_context = _build_scene_context(recent_messages)

        # Déterminer le cap effectif selon le contexte si non fourni explicitement
        if max_reactors is None:
            mode = _detect_reaction_mode(recent_messages)
            max_reactors = 1 if mode == "open_scene" else 2

        # visible_game_state ne dépend pas des messages — calculé une fois.
        visible_game_state = companion_visible_game_state(active.state_data)
        order = list(active.turn_manager._order)
        reacted = 0
        companion_responses: list[dict[str, str]] = []
        seen: set[str] = set()
        iterable = [e.combatant_id for e in order if e.is_ai_controlled]
        if not iterable:
            iterable = list(active.ai_players.keys())
        iterable = order_companion_spotlight(
            active,
            iterable,
            trigger_character_id=trigger_character_id,
            action_text=action_text,
        )

        for char_id in iterable:
            if reacted >= max_reactors:
                break
            if char_id == trigger_character_id or char_id in seen:
                continue
            seen.add(char_id)
            agent = active.ai_players.get(char_id)
            if agent is None:
                continue

            char_name = getattr(agent, "character_name", char_id)
            await self._publish_thinking(
                session_id,
                True,
                character_id=char_id,
                character_name=char_name,
            )
            try:
                action = await agent.roleplay(
                    game_state=visible_game_state,
                    scene_context=scene_context,
                    messages=recent_messages,
                )
            except Exception as exc:
                logger.error(
                    "run_exploration_reactions: agent '%s' raised exception: %s",
                    char_name,
                    exc,
                )
                action = PlayerActionChoice(
                    action_type="wait",
                    action_description=_WAIT_ACTION.action_description,
                    roleplay_text=_WAIT_ACTION.roleplay_text,
                    llm_error=f"{type(exc).__name__}: {exc}",
                )
            finally:
                await self._publish_thinking(
                    session_id,
                    False,
                    character_id=char_id,
                    character_name=char_name,
                )

            if action.llm_error:
                await event_bus.publish_to_session(
                    session_id,
                    EventType.ERROR,
                    {
                        "source": "player_agent",
                        "character": char_name,
                        "message": (
                            f"Le compagnon IA {char_name} est temporairement indisponible."
                        ),
                    },
                    source="ai_player_manager",
                )
                continue

            # Combat guard BEFORE publishing: only allow combat transition if
            # an encounter is already pending (GM-established), otherwise the
            # companion cannot unilaterally introduce a new threat.
            if (
                active.phase.value == "exploration"
                and action.action_type in _COMBAT_STARTING_ACTIONS
            ):
                if active.state_data.get("pending_encounter"):
                    # Legitimate: publish the aggressive action, flag transition, stop
                    visible_text = self._visible_action_text(action, char_name)
                    scene_id = str(uuid.uuid4())
                    await self._publish_companion_visible(
                        session_id,
                        visible_text,
                        char_name=char_name,
                        char_id=char_id,
                        action_type=action.action_type,
                        entry_kind="action",
                        scene_id=scene_id,
                    )
                    active.state_data["pending_phase_transition"] = "COMBAT"
                    active.mark_dirty()
                    record_companion_spotlight(active, char_id)
                    reacted += 1
                    break
                else:
                    # No confirmed threat: replace with cautious hesitation
                    action = PlayerActionChoice(
                        action_type="wait",
                        action_description="Le personnage hésite prudemment.",
                        roleplay_text=(
                            "(jette un regard méfiant, la main sur l'arme, mais sans dégainer)"
                        ),
                        inner_reasoning="Pas de menace confirmée par le MJ — attente.",
                    )

            # Publish post-guard roleplay
            visible_text = self._visible_action_text(action, char_name)
            scene_id = str(uuid.uuid4())
            entry_kind = "action" if action.action_type in _MECHANICAL_ACTION_TYPES else "dialogue"
            await self._publish_companion_visible(
                session_id,
                visible_text,
                char_name=char_name,
                char_id=char_id,
                action_type=action.action_type,
                entry_kind=entry_kind,
                scene_id=scene_id,
            )

            # Collecter la réponse pour la conclusion sociale éventuelle
            companion_responses.append({"speaker": char_name, "text": visible_text})
            record_companion_spotlight(active, char_id)

            # Persist locally only for non-pipeline social/passive reactions.
            if db is not None and action.action_type not in _EXPLORATION_ARBITRAGE_ACTIONS:
                from app.models.message import MessageRole, MessageType
                from app.services.message_service import persist_narration

                msg_type = (
                    MessageType.ACTION
                    if action.action_type in _EXPLORATION_ARBITRAGE_ACTIONS
                    else MessageType.DIALOGUE
                )
                await persist_narration(
                    session_id,
                    visible_text,
                    char_name,
                    db,
                    role=MessageRole.PLAYER,
                    message_type=msg_type,
                    metadata={
                        "is_ai_player": True,
                        "speaker_id": char_id,
                        "speaker_kind": "companion",
                        "entry_kind": entry_kind,
                        "character_id": char_id,
                        "action_type": action.action_type,
                        "scene_id": scene_id,
                    },
                )

            relayed_to_npc = False
            if action.action_type == "talk":
                relayed_to_npc = await self._relay_companion_talk_to_npc(
                    session_id=session_id,
                    active=active,
                    action_resolver=action_resolver,
                    action=action,
                    visible_text=visible_text,
                    char_id=char_id,
                    db=db,
                )

            # GM pipeline only for actions requiring world arbitration
            if action.action_type in _EXPLORATION_ARBITRAGE_ACTIONS:
                spell_id = self._choice_spell_id(action)
                slot_level = self._choice_slot_level(action)
                if action.action_type == "cast_spell":
                    spell_choice = self._resolve_spell_choice(action, char_id, active.state_data)
                    if spell_choice is not None:
                        spell_id, spell_name, slot_level = spell_choice
                        action.params["spell_id"] = spell_id
                        action.params["spell_name"] = spell_name
                try:
                    await action_resolver.resolve(
                        session_id=session_id,
                        action_type=action.action_type,
                        content=self._companion_action_prompt(action, char_name),
                        character_id=char_id,
                        target_id=action.target,
                        active=active,
                        db=db,
                        spell_id=spell_id,
                        slot_level=slot_level,
                        actor_kind="companion",
                        actor_name=char_name,
                        display_text=visible_text,
                    )
                except Exception as exc:
                    logger.error(
                        "run_exploration_reactions: action_resolver a échoué pour %s : %s",
                        char_name,
                        exc,
                    )

            reacted += 1

            if active.state_data.get("pending_phase_transition") == "COMBAT":
                break
            if relayed_to_npc:
                break

            # Recharger le contexte pour que le prochain compagnon voie ce qui
            # vient d'être dit (séquentialité : N+1 voit la réplique de N).
            if db is not None and reacted < max_reactors:
                from app.services.message_service import load_recent_messages

                recent_messages = await load_recent_messages(session_id, db)
                scene_context = _build_scene_context(recent_messages)

        return reacted, companion_responses

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    async def _publish_companion_visible(
        session_id: str,
        text: str,
        *,
        char_name: str,
        char_id: str,
        action_type: str,
        entry_kind: str,
        scene_id: str,
    ) -> None:
        await publish_visible_entry(
            event_bus,
            session_id,
            {
                "text": text,
                "speaker": char_name,
                "speaker_id": char_id,
                "speaker_kind": "companion",
                "entry_kind": entry_kind,
                "action_type": action_type,
                "is_ai_player": True,
                "scene_id": scene_id,
            },
            source="ai_player_manager",
        )

    @classmethod
    async def _relay_companion_talk_to_npc(
        cls,
        *,
        session_id: str,
        active: ActiveSession,
        action_resolver: ActionResolver,
        action: PlayerActionChoice,
        visible_text: str,
        char_id: str,
        db: AsyncSession | None,
    ) -> bool:
        relay = getattr(action_resolver, "resolve_npc_dialogue", None)
        if relay is None or not callable(relay):
            return False

        npc_id = cls._companion_npc_dialogue_target(action, visible_text, active.state_data)
        if not npc_id:
            return False

        try:
            result = relay(
                session_id=session_id,
                content=visible_text,
                character_id=char_id,
                target_id=npc_id,
                active=active,
                db=db,
            )
            if not isawaitable(result):
                return bool(result)
            return bool(await result)
        except Exception as exc:
            logger.error(
                "run_exploration_reactions: relais dialogue PNJ échoué pour %s : %s",
                char_id,
                exc,
            )
            return False

    @classmethod
    def _companion_npc_dialogue_target(
        cls,
        action: PlayerActionChoice,
        visible_text: str,
        state_data: dict[str, Any],
    ) -> str | None:
        raw_target = str(action.target or "").strip()
        explicit_target_id = (
            cls._resolve_present_npc_target(raw_target, state_data) if raw_target else None
        )
        text_target_id = cls._resolve_present_npc_target(visible_text, state_data)
        npc_id = explicit_target_id or text_target_id
        if not npc_id:
            return None

        npc_name = cls._present_npc_name(npc_id, state_data)
        if not cls._looks_like_direct_npc_address(
            visible_text,
            npc_name=npc_name,
            has_explicit_target=explicit_target_id is not None,
        ):
            return None
        return npc_id

    @classmethod
    def _resolve_present_npc_target(
        cls,
        text: str,
        state_data: dict[str, Any],
    ) -> str | None:
        if not text:
            return None
        present_ids = cls._present_npc_ids(state_data)
        if text in present_ids:
            return text
        try:
            from app.game.social_resolution import resolve_npc_target_id

            target_id = resolve_npc_target_id(text, state_data)
        except Exception as exc:
            log_degraded(logger, "résolution cible PNJ", exc, text=text)
            target_id = None
        if target_id and target_id in present_ids:
            return target_id
        return None

    @staticmethod
    def _present_npc_ids(state_data: dict[str, Any]) -> set[str]:
        scene = state_data.get("current_scene", {})
        scene_id = str(scene.get("scene_id") or "") if isinstance(scene, dict) else ""
        present: set[str] = set()
        if isinstance(scene, dict):
            for poi in scene.get("pois", []) or []:
                if not isinstance(poi, dict):
                    continue
                kind = str(poi.get("kind") or poi.get("icon") or "").casefold()
                if kind == "npc":
                    poi_id = str(poi.get("id") or "").strip()
                    if poi_id:
                        present.add(poi_id)

        npc_states = state_data.get("npc_states", {})
        if isinstance(npc_states, dict) and scene_id:
            for npc_id, npc in npc_states.items():
                if isinstance(npc, dict) and str(npc.get("last_location") or "") == scene_id:
                    present.add(str(npc_id))
        return present

    @staticmethod
    def _present_npc_name(npc_id: str, state_data: dict[str, Any]) -> str:
        npc_states = state_data.get("npc_states", {})
        if isinstance(npc_states, dict):
            npc = npc_states.get(npc_id)
            if isinstance(npc, dict) and npc.get("name"):
                return str(npc["name"])
        scene = state_data.get("current_scene", {})
        if isinstance(scene, dict):
            for poi in scene.get("pois", []) or []:
                if isinstance(poi, dict) and str(poi.get("id") or "") == npc_id:
                    return str(poi.get("name") or npc_id)
        return npc_id

    @classmethod
    def _looks_like_direct_npc_address(
        cls,
        text: str,
        *,
        npc_name: str,
        has_explicit_target: bool,
    ) -> bool:
        normalized = cls._normalize_text(text)
        if not normalized:
            return False

        has_question_or_request = "?" in text or any(
            marker in normalized
            for marker in (
                "vous",
                "votre",
                "vos",
                "tu",
                "toi",
                "ton",
                "ta",
                "tes",
                "dites",
                "expliquez",
                "repondez",
                "parlez",
                "pouvez",
                "avez vous",
                "savez vous",
            )
        )
        if has_explicit_target:
            return has_question_or_request

        aliases = [npc_name]
        first_name = str(npc_name).split(" ", 1)[0]
        if first_name and first_name != npc_name:
            aliases.append(first_name)
        alias_patterns = [re.escape(cls._normalize_text(alias)) for alias in aliases if alias]
        if not alias_patterns:
            return False
        alias_pattern = "|".join(alias_patterns)
        raw_text = unicodedata.normalize("NFKD", str(text).casefold())
        raw_text = "".join(ch for ch in raw_text if not unicodedata.combining(ch))
        raw_aliases = [
            re.escape(
                "".join(
                    ch
                    for ch in unicodedata.normalize("NFKD", str(alias).casefold())
                    if not unicodedata.combining(ch)
                )
            )
            for alias in aliases
            if str(alias).strip()
        ]
        raw_alias_pattern = "|".join(raw_aliases)
        has_vocative_name = bool(
            raw_alias_pattern
            and re.search(rf"(^|[«\"“”\s])@?(?:{raw_alias_pattern})\s*[:,]", raw_text)
        )
        speaks_to_name = bool(
            re.search(
                rf"(demande|interroge|parle|adresse|dit|questionne)\s+(a\s+)?(?:{alias_pattern})",
                normalized,
            )
        )
        has_direct_name_address = bool(has_vocative_name or speaks_to_name)
        return has_direct_name_address and has_question_or_request

    @staticmethod
    async def _publish_thinking(
        session_id: str,
        thinking: bool,
        *,
        character_id: str | None = None,
        character_name: str | None = None,
    ) -> None:
        await event_bus.publish_to_session(
            session_id,
            EventType.AI_THINKING,
            {
                "agent_kind": "player_ai",
                "thinking": thinking,
                "character_id": character_id,
                "character_name": character_name,
            },
            source="ai_player_manager",
        )

    @staticmethod
    async def _get_action(
        agent: Any,
        active: ActiveSession,
        available_actions: list[str] | None = None,
    ) -> PlayerActionChoice:
        """Ask the agent for an action based on the current game phase."""
        from app.models.session import SessionStatus

        try:
            if active.phase == SessionStatus.COMBAT:
                return await agent.decide_action(
                    game_state=active.state_data,
                    available_actions=available_actions,
                )
            else:
                return await agent.roleplay(
                    game_state=companion_visible_game_state(active.state_data)
                )
        except Exception as exc:
            logger.error(
                "AIPlayerManager: agent '%s' raised exception: %s",
                getattr(agent, "character_name", "?"),
                exc,
            )
            return PlayerActionChoice(
                action_type="wait",
                action_description=_WAIT_ACTION.action_description,
                roleplay_text=_WAIT_ACTION.roleplay_text,
                inner_reasoning=_WAIT_ACTION.inner_reasoning,
                llm_error=f"{type(exc).__name__}: {exc}",
            )

    @classmethod
    def _available_combat_actions(
        cls,
        character_id: str,
        state_data: dict[str, Any],
    ) -> list[str]:
        actions = ["attack", "move", "dash"]
        if cls._find_unstable_ally(character_id, state_data) is not None:
            actions.append("stabilize")
        if cls._has_castable_spell(character_id, state_data):
            actions.append("cast_spell")
        actions.extend(["disengage", "dodge", "wait"])
        return actions

    @classmethod
    def _has_castable_spell(cls, character_id: str, state_data: dict[str, Any]) -> bool:
        cdata = cls._character_data(character_id, state_data)
        known_spells = cdata.get("known_spells", [])
        if not isinstance(known_spells, list) or not known_spells:
            return False
        try:
            spells = _load_spells()
        except Exception as exc:
            logger.warning("AIPlayerManager: chargement des sorts impossible: %s", exc)
            return False
        for spell_id in known_spells:
            spell = spells.get(str(spell_id))
            if not spell:
                continue
            if int(spell.get("level", 0)) == 0:
                return True
            if cls._slot_level_available(cdata.get("spell_slots", {}), int(spell["level"])):
                return True
        return False

    @classmethod
    def _normalize_combat_action(
        cls,
        action: PlayerActionChoice,
        character_id: str,
        active: ActiveSession,
        available_actions: list[str],
    ) -> tuple[PlayerActionChoice, str | None, int | None]:
        state_data = active.state_data
        if action.action_type not in set(available_actions):
            return (
                cls._build_fallback_combat_action(
                    character_id,
                    cls._character_data(character_id, state_data).get("name", character_id),
                    state_data,
                    available_actions,
                ),
                None,
                None,
            )

        if action.action_type in {"move", "dash", "disengage"}:
            movement_action = cls._resolve_movement_intent(action, character_id, active)
            if movement_action is None:
                return (
                    cls._build_fallback_combat_action(
                        character_id,
                        cls._character_data(character_id, state_data).get("name", character_id),
                        state_data,
                        available_actions,
                    ),
                    None,
                    None,
                )
            return movement_action, None, None

        if action.action_type != "cast_spell":
            return action, None, None

        spell_choice = cls._resolve_spell_choice(action, character_id, state_data)
        if spell_choice is None:
            return (
                cls._build_fallback_combat_action(
                    character_id,
                    cls._character_data(character_id, state_data).get("name", character_id),
                    state_data,
                    available_actions,
                ),
                None,
                None,
            )

        spell_id, spell_name, slot_level = spell_choice
        action.params["spell_id"] = spell_id
        action.params["spell_name"] = spell_name
        if action.target is None:
            action.target = cls._select_default_enemy_target(character_id, state_data)
        return action, spell_id, slot_level

    @classmethod
    def _resolve_movement_intent(
        cls,
        action: PlayerActionChoice,
        character_id: str,
        active: ActiveSession,
    ) -> PlayerActionChoice | None:
        intent = str(action.params.get("intent") or "").strip().lower()
        if intent not in {"approach", "retreat", "flank"}:
            return None

        state_data = active.state_data
        target_id = cls._resolve_combatant_reference(
            action.params.get("target_id") or action.target,
            state_data,
        )
        if target_id is None:
            target_id = cls._select_default_enemy_target(character_id, state_data)
        if target_id is None:
            return None

        combatants = state_data.get("combatants", {})
        cdata = combatants.get(character_id, {}) if isinstance(combatants, dict) else {}
        speed_m = float(cdata.get("speed_m", 9.0) if isinstance(cdata, dict) else 9.0)
        current = active.turn_manager.current_turn
        economy = (
            current.action_economy
            if current is not None and current.combatant_id == character_id
            else None
        )
        movement_m = float(economy.movement if economy is not None else speed_m)
        if action.action_type == "dash":
            movement_m += float(economy.movement_max if economy is not None else speed_m)

        from app.game.tactical_combat import resolve_ai_move_destination  # noqa: PLC0415

        destination = resolve_ai_move_destination(
            state_data,
            character_id,
            intent,
            target_id,
            movement_m,
        )
        if destination is None:
            return None

        action.target = target_id
        action.params["intent"] = intent
        action.params["target_id"] = target_id
        action.params["destination"] = f"{destination.col},{destination.row}"
        return action

    @classmethod
    def _resolve_spell_choice(
        cls,
        action: PlayerActionChoice,
        character_id: str,
        state_data: dict[str, Any],
    ) -> tuple[str, str, int] | None:
        cdata = cls._character_data(character_id, state_data)
        known_spells = cdata.get("known_spells", [])
        if not isinstance(known_spells, list) or not known_spells:
            return None

        raw_spell = (
            action.params.get("spell_id")
            or action.params.get("spell_name")
            or action.action_description
        )
        if not raw_spell:
            return None

        try:
            spells = _load_spells()
        except Exception as exc:
            logger.warning("AIPlayerManager: chargement des sorts impossible: %s", exc)
            return None

        wanted = cls._normalize_text(raw_spell)
        known_ids = {str(s) for s in known_spells}
        for spell_id in known_ids:
            spell = spells.get(spell_id)
            if not spell:
                continue
            aliases = [
                spell_id,
                spell.get("name", ""),
                spell.get("name_fr", ""),
            ]
            if not any(
                cls._normalize_text(alias) in wanted or wanted in cls._normalize_text(alias)
                for alias in aliases
                if alias
            ):
                continue

            spell_level = int(spell.get("level", 0))
            if spell_level == 0:
                spell_name = str(spell.get("name_fr") or spell.get("name") or spell_id)
                return spell_id, spell_name, 0

            slot_level = cls._choose_slot_level(
                cdata.get("spell_slots", {}),
                spell_level,
                requested=action.params.get("slot_level") or action.params.get("level"),
            )
            if slot_level is None:
                return None
            spell_name = str(spell.get("name_fr") or spell.get("name") or spell_id)
            return spell_id, spell_name, slot_level

        return None

    @classmethod
    def _build_fallback_combat_action(
        cls,
        character_id: str,
        character_name: str,
        state_data: dict[str, Any],
        available_actions: list[str],
    ) -> PlayerActionChoice:
        target = cls._select_default_enemy_target(character_id, state_data)
        target_name = cls._combatant_name(state_data, target)
        if target and "attack" in available_actions:
            return PlayerActionChoice(
                action_type="attack",
                action_description=f"Attaque {target_name}",
                target=target,
                params={},
                roleplay_text=f"{character_name} reprend l'initiative et attaque {target_name}.",
                inner_reasoning="Fallback combat : attaque fiable sur une cible hostile active.",
            )
        if "dodge" in available_actions:
            return PlayerActionChoice(
                action_type="dodge",
                action_description="Se met en défense",
                roleplay_text=f"{character_name} se remet en garde.",
                inner_reasoning="Fallback combat : aucune cible hostile active.",
            )
        return PlayerActionChoice(
            action_type="wait",
            action_description=_WAIT_ACTION.action_description,
            roleplay_text=_WAIT_ACTION.roleplay_text,
            inner_reasoning=_WAIT_ACTION.inner_reasoning,
        )

    @classmethod
    def _build_deterministic_combat_action(
        cls,
        character_id: str,
        character_name: str,
        state_data: dict[str, Any],
        available_actions: list[str],
    ) -> PlayerActionChoice:
        unstable_ally = cls._find_unstable_ally(character_id, state_data)
        if unstable_ally and "stabilize" in available_actions:
            ally_name = cls._combatant_name(state_data, unstable_ally)
            return PlayerActionChoice(
                action_type="stabilize",
                action_description=f"Stabilise {ally_name}",
                target=unstable_ally,
                params={},
                roleplay_text=f"{character_name} se penche vers {ally_name} pour le stabiliser.",
                inner_reasoning="Mode sobre : priorite a la survie d'un allie a 0 PV.",
            )

        return cls._build_fallback_combat_action(
            character_id,
            character_name,
            state_data,
            available_actions,
        )

    @classmethod
    def _find_unstable_ally(
        cls,
        character_id: str,
        state_data: dict[str, Any],
    ) -> str | None:
        combatants = state_data.get("combatants", {})
        if not isinstance(combatants, dict):
            return None

        for cid, cdata in combatants.items():
            if cid == character_id or not isinstance(cdata, dict):
                continue
            if cdata.get("is_player") is not True:
                continue
            if str(cdata.get("status", "active")).lower() in INACTIVE_STATUSES:
                continue
            try:
                hp = int(cdata.get("hp", cdata.get("current_hp", 1)))
            except (TypeError, ValueError):
                hp = 1
            death_saves = cdata.get("death_saves", {})
            if hp == 0 and not death_saves.get("stable") and not cdata.get("dead"):
                return str(cid)
        return None

    @staticmethod
    def _character_data(character_id: str, state_data: dict[str, Any]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        characters = state_data.get("characters", {})
        if isinstance(characters, dict):
            cdata = characters.get(character_id)
            if isinstance(cdata, dict):
                result.update(cdata)
        combatants = state_data.get("combatants", {})
        if isinstance(combatants, dict):
            cdata = combatants.get(character_id)
            if isinstance(cdata, dict):
                result.setdefault("name", cdata.get("name", character_id))
                result["current_hp"] = cdata.get(
                    "hp",
                    result.get("current_hp", result.get("hp", 1)),
                )
                result.setdefault("hp", result["current_hp"])
                result.setdefault("hp_max", cdata.get("hp_max"))
                result.setdefault("conditions", cdata.get("conditions", []))
                result.setdefault("status", cdata.get("status", "active"))
        return result

    @classmethod
    def _character_can_act(cls, character_id: str, state_data: dict[str, Any]) -> bool:
        cdata = cls._character_data(character_id, state_data)
        if str(cdata.get("status", "active")).lower() in INACTIVE_STATUSES:
            return False
        try:
            hp = int(cdata.get("current_hp", cdata.get("hp", 1)))
        except (TypeError, ValueError):
            hp = 1
        return hp > 0

    @classmethod
    def _visible_action_text(cls, action: PlayerActionChoice, character_name: str) -> str:
        roleplay = str(action.roleplay_text or "").strip()
        if roleplay:
            return sanitize_companion_visible_text(roleplay, character_name=character_name)
        if action.action_type not in _MECHANICAL_ACTION_TYPES:
            return sanitize_companion_visible_text(
                roleplay,
                character_name=character_name,
            )

        description = str(action.action_description or "").strip()
        if not description:
            return sanitize_companion_visible_text(roleplay, character_name=character_name)

        if description.casefold().startswith(character_name.casefold()):
            text = description
        else:
            text = f"{character_name} {cls._lowercase_initial(description)}"
        if text[-1] not in ".!?…":
            text += "."
        return sanitize_companion_visible_text(text, character_name=character_name)

    @staticmethod
    def _choice_spell_id(action: PlayerActionChoice) -> str | None:
        spell_id = str(
            action.params.get("spell_id")
            or action.params.get("spell_name")
            or ""
        ).strip()
        return spell_id or None

    @staticmethod
    def _choice_slot_level(action: PlayerActionChoice) -> int | None:
        raw_level = action.params.get("slot_level")
        if raw_level is None:
            raw_level = action.params.get("level")
        if raw_level is None or raw_level == "":
            return None
        try:
            return int(raw_level)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _companion_action_prompt(
        cls,
        action: PlayerActionChoice,
        character_name: str,
    ) -> str:
        description = str(action.action_description or "").strip()
        if not description:
            description = str(action.roleplay_text or action.action_type).strip()
        if not description:
            return f"{character_name} agit."
        if description.casefold().startswith(character_name.casefold()):
            text = description
        else:
            text = f"{character_name} {cls._lowercase_initial(description)}"
        return text if text[-1] in ".!?…" else f"{text}."

    @classmethod
    def _companion_action_content(
        cls,
        action: PlayerActionChoice,
        character_name: str,
    ) -> str:
        destination = action.params.get("destination")
        if action.action_type in {"move", "dash", "disengage"} and destination:
            return str(destination)
        return cls._companion_action_prompt(action, character_name)

    @staticmethod
    def _lowercase_initial(text: str) -> str:
        if not text:
            return text
        return text[0].lower() + text[1:]

    @staticmethod
    def _normalize_text(value: Any) -> str:
        normalized = unicodedata.normalize("NFKD", str(value).lower())
        without_accents = "".join(ch for ch in normalized if not unicodedata.combining(ch))
        return re.sub(r"[^a-z0-9_]+", " ", without_accents).strip()

    @classmethod
    def _resolve_combatant_reference(
        cls,
        raw_target: Any,
        state_data: dict[str, Any],
    ) -> str | None:
        if raw_target is None:
            return None
        raw = str(raw_target).strip()
        if not raw:
            return None
        combatants = state_data.get("combatants", {})
        if not isinstance(combatants, dict):
            return raw
        if raw in combatants:
            return raw
        wanted = cls._normalize_text(raw).replace("_", " ")
        for cid, cdata in combatants.items():
            aliases = [str(cid), str(cid).replace("_", " ")]
            if isinstance(cdata, dict) and cdata.get("name"):
                aliases.append(str(cdata["name"]))
            for alias in aliases:
                if wanted == cls._normalize_text(alias).replace("_", " "):
                    return str(cid)
        return raw

    @classmethod
    def _choose_slot_level(
        cls,
        spell_slots: Any,
        minimum_level: int,
        requested: Any = None,
    ) -> int | None:
        if requested is not None:
            try:
                requested_level = max(minimum_level, int(requested))
            except (TypeError, ValueError):
                requested_level = minimum_level
            if cls._slot_level_available(spell_slots, requested_level):
                return requested_level

        for level in range(minimum_level, 10):
            if cls._slot_level_available(spell_slots, level):
                return level
        return None

    @staticmethod
    def _slot_level_available(spell_slots: Any, level: int) -> bool:
        if not isinstance(spell_slots, dict):
            return False
        slot = spell_slots.get(str(level), spell_slots.get(level))
        if isinstance(slot, dict):
            try:
                return int(slot.get("total", 0)) - int(slot.get("used", 0)) > 0
            except (TypeError, ValueError):
                return False
        try:
            return int(slot) > 0
        except (TypeError, ValueError):
            return False

    @classmethod
    def _select_default_enemy_target(
        cls,
        character_id: str,
        state_data: dict[str, Any],
    ) -> str | None:
        combatants = state_data.get("combatants", {})
        if not isinstance(combatants, dict):
            return None
        characters = state_data.get("characters", {})
        character_ids = set(characters) if isinstance(characters, dict) else set()
        candidates: list[tuple[int, str]] = []
        for cid, cdata in combatants.items():
            if cid == character_id or not isinstance(cdata, dict):
                continue
            is_enemy = cdata.get("is_player") is False or (
                cdata.get("is_player") is not True and cid not in character_ids
            )
            if not is_enemy:
                continue
            if str(cdata.get("status", "active")).lower() in INACTIVE_STATUSES:
                continue
            try:
                hp = int(cdata.get("hp", 0))
            except (TypeError, ValueError):
                hp = 0
            if hp <= 0:
                continue
            candidates.append((hp, str(cid)))
        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][1]

    @staticmethod
    def _combatant_name(state_data: dict[str, Any], target: str | None) -> str:
        if target is None:
            return "la cible"
        combatants = state_data.get("combatants", {})
        if isinstance(combatants, dict):
            cdata = combatants.get(target, {})
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])
        return target
