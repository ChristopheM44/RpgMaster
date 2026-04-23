from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.agents.base_agent import BaseAgent
from app.agents.context_manager import ContextManager
from app.agents.schemas import (
    PLAYER_ACTION_TYPES,
    AgentContext,
    AgentResponse,
    PlayerActionChoice,
    PlayerPersonality,
)
from app.llm.base_client import LLMClient
from app.llm.model_router import router
from app.llm.ollama_client import OllamaError
from app.llm.openai_compatible_client import OpenAICompatibleError

logger = logging.getLogger(__name__)

_FALLBACK_ACTION = PlayerActionChoice(
    action_type="wait",
    action_description="Le personnage attend, incertain.",
    roleplay_text="(hésite, cherchant quoi faire)",
    inner_reasoning="Le système LLM est indisponible.",
)

_PERSONALITY_DESCRIPTIONS: dict[str, str] = {
    "brave": (
        "Tu fondes sur les ennemis les plus dangereux. "
        "Tu n'abandonnes jamais tes alliés et tu mènes l'assaut."
    ),
    "cautious": (
        "Tu conserves tes ressources précieuses. "
        "Tu préfères te soigner ou soutenir plutôt que d'attaquer à découvert."
    ),
    "greedy": (
        "Tu repères toujours les objets de valeur et les opportunités. "
        "Tu vises les cibles qui semblent porter des richesses."
    ),
    "noble": (
        "Tu protèges les plus faibles et tu t'interposes entre les ennemis et tes alliés blessés. "
        "L'honneur guide chaque décision."
    ),
    "vengeful": (
        "Tu te concentres sur l'ennemi qui a blessé l'un de tes alliés. "
        "La vengeance est ta priorité en combat."
    ),
    "arcane": (
        "Tu préfères systématiquement la magie aux armes physiques. "
        "Tu gères tes emplacements de sorts avec précision."
    ),
    "reckless": (
        "Tu attaques sans calculer les risques, avec fougue et imprévisibilité. "
        "La subtilité n'est pas ton fort."
    ),
    "protective": (
        "Tu restes aux côtés des alliés les plus vulnérables. "
        "Tu utilises Aide (Help) et Esquive (Dodge) autant qu'attaquer."
    ),
}


def _describe_personality(personality: PlayerPersonality) -> str:
    """Traduit un profil de personnalité en description textuelle pour le prompt."""
    lines: list[str] = []
    for trait in personality.traits:
        desc = _PERSONALITY_DESCRIPTIONS.get(trait)
        if desc:
            lines.append(f"- [{trait.upper()}] {desc}")
    if personality.backstory_hook:
        lines.append(f"- BACKGROUND : {personality.backstory_hook}")
    if personality.speech_style:
        lines.append(f"- STYLE DE DISCOURS : {personality.speech_style}")
    return "\n".join(lines) if lines else "- Personnalité équilibrée, sans traits marqués."


class PlayerAgent(BaseAgent):
    """Agent joueur IA : prend des décisions tactiques et narratives
    selon la personnalité du personnage et ses capacités disponibles.

    Pipeline :
    contexte + personnalité + capacités → template Jinja2 → LLM → PlayerActionChoice Pydantic
    """

    def __init__(
        self,
        character_id: str,
        character_name: str,
        personality: Optional[PlayerPersonality] = None,
        client: Optional[LLMClient] = None,
        model: Optional[str] = None,
    ):
        self._character_id = character_id
        self._character_name = character_name
        self._personality = personality or PlayerPersonality(traits=["brave"])
        self._client: LLMClient = client or router.get_player_client()
        self._system_prompt = self._build_system_prompt()

    # -------------------------------------------------------------------------
    # Interface BaseAgent
    # -------------------------------------------------------------------------

    async def think(self, context: AgentContext) -> AgentResponse:
        """Point d'entrée générique — délègue selon la phase de jeu."""
        if context.game_phase == "COMBAT":
            action = await self.decide_action(
                game_state=context.game_state,
                available_actions=context.game_state.get("available_actions", []),
                messages=context.messages,
            )
        else:
            action = await self.roleplay(
                game_state=context.game_state,
                scene_context=context.player_action or "",
                messages=context.messages,
            )
        return AgentResponse(
            content=action.roleplay_text,
            actions=[],
        )

    # -------------------------------------------------------------------------
    # Méthodes spécialisées
    # -------------------------------------------------------------------------

    async def decide_action(
        self,
        game_state: dict[str, Any],
        available_actions: Optional[list[str]] = None,
        context_manager: Optional[ContextManager] = None,
        messages: Optional[list] = None,
    ) -> PlayerActionChoice:
        """Choisit une action tactique valide parmi les capacités disponibles.

        Utilisé principalement en combat (COMBAT phase).
        """
        actions_list = available_actions or list(PLAYER_ACTION_TYPES)
        character_data = self._extract_character(game_state)

        user_prompt = self._render_prompt(
            "player_decide.txt",
            {
                "character_name": self._character_name,
                "character_data": json.dumps(character_data, ensure_ascii=False, indent=2),
                "personality_description": _describe_personality(self._personality),
                "game_state": json.dumps(game_state, ensure_ascii=False, indent=2),
                "available_actions": ", ".join(actions_list),
                "recent_messages": self._format_messages(messages),
            },
        )
        return await self._call_and_parse_action(user_prompt, context_manager)

    async def roleplay(
        self,
        game_state: dict[str, Any],
        scene_context: str = "",
        context_manager: Optional[ContextManager] = None,
        messages: Optional[list] = None,
    ) -> PlayerActionChoice:
        """Génère une réaction narrative / roleplay hors combat."""
        character_data = self._extract_character(game_state)

        user_prompt = self._render_prompt(
            "player_roleplay.txt",
            {
                "character_name": self._character_name,
                "character_data": json.dumps(character_data, ensure_ascii=False, indent=2),
                "personality_description": _describe_personality(self._personality),
                "game_state": json.dumps(game_state, ensure_ascii=False, indent=2),
                "scene_context": scene_context,
                "recent_messages": self._format_messages(messages),
            },
        )
        return await self._call_and_parse_action(user_prompt, context_manager)

    # -------------------------------------------------------------------------
    # Validation des actions
    # -------------------------------------------------------------------------

    def validate_action(
        self,
        action: PlayerActionChoice,
        game_state: dict[str, Any],
    ) -> tuple[bool, str]:
        """Vérifie que l'action choisie est légale selon les capacités du personnage.

        Retourne (is_valid, reason).
        Le moteur de jeu reste l'autorité finale ; cette validation est un garde-fou préliminaire.
        """
        character_data = self._extract_character(game_state)

        # Vérification de base : type d'action valide
        if action.action_type not in PLAYER_ACTION_TYPES:
            return False, f"Type d'action inconnu : {action.action_type}"

        # Vérification des sorts : l'emplacement doit être disponible
        if action.action_type == "cast_spell":
            spell_name = action.params.get("spell_name")
            if not spell_name:
                return False, "cast_spell sans spell_name dans params"
            spell_slots = character_data.get("spell_slots", {})
            if not any(v > 0 for v in spell_slots.values()):
                return False, f"{self._character_name} n'a plus d'emplacements de sorts"

        # Vérification de l'utilisation d'objet : l'objet doit être dans l'inventaire
        if action.action_type == "use_item":
            item_name = action.params.get("item_name")
            if not item_name:
                return False, "use_item sans item_name dans params"
            inventory = character_data.get("inventory", [])
            item_names = [
                (i.get("name") or i) if isinstance(i, (dict, str)) else ""
                for i in inventory
            ]
            if item_name not in item_names:
                return False, f"Objet '{item_name}' absent de l'inventaire"

        # Vérification que le personnage n'est pas inconscient
        hp = character_data.get("current_hp", 1)
        if hp <= 0 and action.action_type not in ("wait",):
            return False, f"{self._character_name} est inconscient (0 PV)"

        return True, "ok"

    # -------------------------------------------------------------------------
    # Helpers privés
    # -------------------------------------------------------------------------

    def _build_system_prompt(self) -> str:
        """Construit le system prompt de l'agent à partir de la personnalité."""
        personality_block = _describe_personality(self._personality)
        return (
            f"Tu incarnes {self._character_name}, un personnage joueur dans une campagne D&D 5e.\n"
            "Tu es contrôlé par l'IA et tu joues aux côtés de joueurs humains.\n\n"
            "RÈGLES ABSOLUES :\n"
            "1. Tu ne génères JAMAIS les résultats de jets de dés.\n"
            "2. Tu choisis UNIQUEMENT parmi les actions disponibles indiquées.\n"
            "3. Tu respectes TOUJOURS les ressources actuelles de ton personnage"
            " (PV, sorts, objets).\n"
            "4. Tu réponds TOUJOURS en JSON valide selon le schéma fourni dans le prompt.\n\n"
            f"TA PERSONNALITÉ :\n{personality_block}\n"
        )

    async def _call_and_parse_action(
        self,
        user_prompt: str,
        context_manager: Optional[ContextManager],
    ) -> PlayerActionChoice:
        """Appelle le LLM et parse la réponse en PlayerActionChoice."""
        messages = self._build_messages(user_prompt, context_manager)

        try:
            raw = await self._client.chat(messages=messages, temperature=0.8, max_tokens=512)
        except (OllamaError, OpenAICompatibleError) as exc:
            logger.error("PlayerAgent[%s] : appel LLM échoué : %s", self._character_name, exc)
            return _FALLBACK_ACTION

        data = self._extract_json(raw)
        if data is None:
            logger.warning(
                "PlayerAgent[%s] : pas de JSON dans la réponse LLM", self._character_name
            )
            return PlayerActionChoice(
                action_type="wait",
                action_description="Le personnage hésite.",
                roleplay_text=raw.strip()[:300],
            )

        return self._parse_player_action(data, raw)

    def _build_messages(
        self,
        user_prompt: str,
        context_manager: Optional[ContextManager],
    ) -> list[dict[str, str]]:
        if context_manager is not None:
            msgs = context_manager.to_ollama_messages(self._system_prompt)
        else:
            msgs = [{"role": "system", "content": self._system_prompt}]
        msgs.append({"role": "user", "content": user_prompt})
        return msgs

    def _parse_player_action(self, data: dict[str, Any], raw: str) -> PlayerActionChoice:
        """Convertit le dict JSON parsé en PlayerActionChoice Pydantic."""
        action_type = str(data.get("action_type", "wait"))
        if action_type not in PLAYER_ACTION_TYPES:
            logger.warning(
                "PlayerAgent[%s] : action_type '%s' invalide, fallback wait",
                self._character_name,
                action_type,
            )
            action_type = "wait"

        try:
            return PlayerActionChoice(
                action_type=action_type,
                action_description=str(data.get("action_description", "")),
                target=data.get("target"),
                params=data.get("params", {}),
                roleplay_text=str(data.get("roleplay_text", raw.strip()[:300])),
                inner_reasoning=data.get("inner_reasoning"),
            )
        except Exception as exc:
            logger.error(
                "PlayerAgent[%s] : échec parsing PlayerActionChoice : %s",
                self._character_name,
                exc,
            )
            return _FALLBACK_ACTION

    def _extract_character(self, game_state: dict[str, Any]) -> dict[str, Any]:
        """Extrait les données du personnage depuis le game_state."""
        characters = game_state.get("characters", {})
        return characters.get(self._character_id, {})

    @staticmethod
    def _format_messages(messages: Optional[list]) -> str:
        if not messages:
            return "(aucun message récent)"
        lines: list[str] = []
        for msg in messages[-10:]:
            speaker = getattr(msg, "speaker", "?")
            content = getattr(msg, "content", "")
            lines.append(f"[{speaker}] {content}")
        return "\n".join(lines)

    # -------------------------------------------------------------------------
    # Propriétés
    # -------------------------------------------------------------------------

    @property
    def character_id(self) -> str:
        return self._character_id

    @property
    def character_name(self) -> str:
        return self._character_name

    @property
    def personality(self) -> PlayerPersonality:
        return self._personality
