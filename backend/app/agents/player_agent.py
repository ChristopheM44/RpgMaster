from __future__ import annotations

import json
import logging
import re
import unicodedata
from collections.abc import Sequence
from typing import Any, Optional

from app.agents.base_agent import BaseAgent
from app.agents.context_manager import ContextManager
from app.agents.json_recovery import (
    build_default_combat_action,
    recover_partial_json_response,
    recover_prose_action_response,
    recover_structured_text_response,
)
from app.agents.schemas import (
    PLAYER_ACTION_TYPES,
    AgentContext,
    AgentResponse,
    PlayerActionChoice,
    PlayerPersonality,
)
from app.game.constants import INACTIVE_STATUSES
from app.llm.base_client import LLMClient
from app.llm.budget import record_llm_call
from app.llm.model_router import router
from app.llm.ollama_client import OllamaError
from app.llm.openai_compatible_client import OpenAICompatibleError

logger = logging.getLogger(__name__)

_NON_JSON_LLM_ERROR = "Réponse LLM non parsable (JSON manquant)."

_ELLIPSIS_ONLY_RESPONSES = {"...", "…"}

_ACTION_KEYWORDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "attack",
        (
            "attaque",
            "attaquer",
            "frappe",
            "frapper",
            "coup",
            "charge",
            "fonce",
            "tire",
            "tir",
            "decoche",
            "epee",
            "marteau",
            "hache",
            "lame",
        ),
    ),
    (
        "cast_spell",
        (
            "lance un sort",
            "incante",
            "sort",
            "magie",
            "projectile magique",
            "boule de feu",
            "soin",
            "guerison",
        ),
    ),
    ("dodge", ("esquive", "defensive", "defense", "se protege", "a couvert")),
    ("help", ("aide", "assiste", "soutient", "protege")),
    ("dash", ("sprinte", "court", "se precipite", "dash")),
    ("disengage", ("desengage", "se replie", "retrait prudent")),
    ("hide", ("se cache", "cache", "furtif")),
    ("move", ("avance", "recule", "se deplace", "rejoint", "va vers")),
    ("talk", ("dit", "crie", "previent", "previens", "avertit", "parle", "hurle")),
    ("wait", ("attend", "observe", "reste immobile")),
)


def _fallback_action(error: Optional[str] = None) -> PlayerActionChoice:
    """Action de repli quand le LLM ne répond pas ou renvoie un JSON invalide.

    ``error`` est propagé dans ``PlayerActionChoice.llm_error`` pour que la
    couche appelante puisse remonter l'incident à l'utilisateur au lieu de
    laisser le personnage « attendre » en silence.
    """
    return PlayerActionChoice(
        action_type="wait",
        action_description="Le personnage attend, incertain.",
        roleplay_text="(hésite, cherchant quoi faire)",
        inner_reasoning="Le système LLM est indisponible.",
        llm_error=error,
    )


_FALLBACK_ACTION = _fallback_action()

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


def _normalize_for_match(value: Any) -> str:
    """Normalise un texte pour des comparaisons simples et accent-insensibles."""
    normalized = unicodedata.normalize("NFKD", str(value).lower())
    without_accents = "".join(
        ch for ch in normalized if not unicodedata.combining(ch)
    )
    return re.sub(r"[^a-z0-9_]+", " ", without_accents).strip()


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
        prompt_game_state = self._compact_combat_state(game_state)

        user_prompt = self._render_prompt(
            "player_decide.txt",
            {
                "character_name": self._character_name,
                "character_data": json.dumps(character_data, ensure_ascii=False, indent=2),
                "personality_description": _describe_personality(self._personality),
                "game_state": json.dumps(prompt_game_state, ensure_ascii=False, indent=2),
                "available_actions": ", ".join(actions_list),
                "recent_messages": self._format_messages(messages),
            },
        )
        return await self._call_and_parse_action(
            user_prompt,
            context_manager,
            game_state=game_state,
            available_actions=actions_list,
            combat_mode=True,
        )

    async def roleplay(
        self,
        game_state: dict[str, Any],
        scene_context: str = "",
        context_manager: Optional[ContextManager] = None,
        messages: Optional[list] = None,
    ) -> PlayerActionChoice:
        """Génère une réaction narrative / roleplay hors combat."""
        character_data = self._extract_character(game_state)
        recent_messages = self._format_messages(messages)
        if recent_messages == "(aucun message récent)":
            recent_messages = self._summarize_recent_narrative(game_state)

        user_prompt = self._render_prompt(
            "player_roleplay.txt",
            {
                "character_name": self._character_name,
                "character_data": json.dumps(character_data, ensure_ascii=False, indent=2),
                "personality_description": _describe_personality(self._personality),
                "game_state": json.dumps(game_state, ensure_ascii=False, indent=2),
                "scene_context": scene_context,
                "recent_messages": recent_messages,
            },
        )
        return await self._call_and_parse_action(
            user_prompt,
            context_manager,
            game_state=game_state,
            available_actions=("talk", "move", "use_item", "wait", "examine"),
            combat_mode=False,
        )

    async def respond_to_player(
        self,
        game_state: dict[str, Any],
        player_message: str,
        context_manager: Optional[ContextManager] = None,
        messages: Optional[list] = None,
    ) -> PlayerActionChoice:
        """Répond à un joueur humain dans une scène de dialogue libre.

        Contrairement à :meth:`roleplay`, ce mode part explicitement de la
        parole d'un joueur adressée au compagnon. La réponse peut rester purement
        conversationnelle (``talk``) ou proposer une action que le MJ arbitrera.
        """
        character_data = self._extract_character(game_state)
        recent_messages = self._format_messages(messages)
        if recent_messages == "(aucun message récent)":
            recent_messages = self._summarize_recent_narrative(game_state)

        user_prompt = self._render_prompt(
            "player_dialogue.txt",
            {
                "character_name": self._character_name,
                "character_data": json.dumps(character_data, ensure_ascii=False, indent=2),
                "personality_description": _describe_personality(self._personality),
                "game_state": json.dumps(game_state, ensure_ascii=False, indent=2),
                "player_message": player_message,
                "recent_messages": recent_messages,
            },
        )
        return await self._call_and_parse_action(
            user_prompt,
            context_manager,
            game_state=game_state,
            available_actions=("talk", "move", "use_item", "wait", "examine", "help"),
            combat_mode=False,
        )

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
            if not self._has_available_spell_slot(spell_slots):
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

    @staticmethod
    def _has_available_spell_slot(spell_slots: Any) -> bool:
        if not isinstance(spell_slots, dict):
            return False
        for slot in spell_slots.values():
            if isinstance(slot, dict):
                try:
                    total = int(slot.get("total", 0))
                    used = int(slot.get("used", 0))
                except (TypeError, ValueError):
                    continue
                if total - used > 0:
                    return True
                continue
            try:
                if int(slot) > 0:
                    return True
            except (TypeError, ValueError):
                continue
        return False

    async def _call_and_parse_action(
        self,
        user_prompt: str,
        context_manager: Optional[ContextManager],
        *,
        game_state: Optional[dict[str, Any]] = None,
        available_actions: Optional[Sequence[str]] = None,
        combat_mode: bool = False,
    ) -> PlayerActionChoice:
        """Appelle le LLM et parse la réponse en PlayerActionChoice."""
        messages = self._build_messages(user_prompt, context_manager)

        try:
            record_llm_call("player")
            raw = await self._client.chat(messages=messages, temperature=0.6, max_tokens=1024)
        except (OllamaError, OpenAICompatibleError) as exc:
            logger.error("PlayerAgent[%s] : appel LLM échoué : %s", self._character_name, exc)
            return _fallback_action(error=f"{type(exc).__name__}: {exc}")

        data = self._extract_json(raw, log_failure=False)
        if data is None:
            data = await self._repair_json_response(raw)

        if data is None:
            data = self._recover_partial_json_response(raw, game_state=game_state or {})

        if data is None:
            data = self._recover_structured_text_response(raw)

        if data is None:
            data = self._recover_prose_action_response(
                raw,
                game_state=game_state or {},
                available_actions=available_actions,
                combat_mode=combat_mode,
            )

        if data is None and combat_mode:
            data = self._build_default_combat_action(
                raw,
                game_state=game_state or {},
                available_actions=available_actions,
            )

        if data is None:
            logger.warning(
                "PlayerAgent[%s] : pas de JSON dans la réponse LLM", self._character_name
            )
            return PlayerActionChoice(
                action_type="wait",
                action_description="Le personnage hésite.",
                roleplay_text=raw.strip()[:300],
                llm_error=_NON_JSON_LLM_ERROR,
            )

        return self._parse_player_action(data, raw, game_state=game_state or {})

    async def _repair_json_response(self, raw: str) -> Optional[dict[str, Any]]:
        """Second passage léger : demande au modèle de convertir sa prose en JSON.

        Certains petits modèles suivent le rôle mais oublient le format. On tente
        une conversion stricte à basse température avant de tomber en fallback.
        """
        stripped = raw.strip()
        if not stripped or stripped in _ELLIPSIS_ONLY_RESPONSES:
            return None

        repair_messages = [
            {
                "role": "system",
                "content": (
                    "Tu es un convertisseur de réponse. Retourne uniquement un objet JSON valide, "
                    "sans markdown ni commentaire."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Convertis cette réponse de joueur IA D&D en JSON selon ce schéma exact :\n"
                    "{\n"
                    '  "action_type": "attack|cast_spell|dash|dodge|help|use_item|move|talk|'
                    'wait|disengage|hide|shove|examine",\n'
                    '  "action_description": "description courte",\n'
                    '  "target": null,\n'
                    '  "params": {},\n'
                    '  "roleplay_text": "texte en français",\n'
                    '  "inner_reasoning": "raison brève"\n'
                    "}\n\n"
                    "Si l'action n'est pas claire, utilise action_type='wait'.\n\n"
                    f"Réponse brute :\n{stripped[:1200]}"
                ),
            },
        ]
        try:
            record_llm_call("player")
            repaired = await self._client.chat(
                messages=repair_messages,
                temperature=0.0,
                max_tokens=600,
            )
        except (OllamaError, OpenAICompatibleError) as exc:
            logger.warning(
                "PlayerAgent[%s] : réparation JSON impossible : %s",
                self._character_name,
                exc,
            )
            return None
        return self._extract_json(repaired, log_failure=False)

    def _recover_partial_json_response(
        self,
        raw: str,
        *,
        game_state: Optional[dict[str, Any]] = None,
    ) -> Optional[dict[str, Any]]:
        """Recover useful fields from a truncated JSON-like response.

        Local models sometimes stop mid-string after producing valid-looking
        keys. This keeps the turn moving without surfacing a false provider
        error or forcing a silent wait.
        """
        return recover_partial_json_response(
            raw,
            character_name=self._character_name,
            game_state=game_state,
            safe_recovered_roleplay=self._safe_recovered_roleplay,
        )

    def _recover_structured_text_response(self, raw: str) -> Optional[dict[str, Any]]:
        """Recover useful fields from loosely structured text answers."""
        return recover_structured_text_response(raw)

    def _recover_prose_action_response(
        self,
        raw: str,
        *,
        game_state: dict[str, Any],
        available_actions: Optional[Sequence[str]],
        combat_mode: bool,
    ) -> Optional[dict[str, Any]]:
        """Infer an action from plain prose when the model ignored JSON format."""
        return recover_prose_action_response(
            raw,
            game_state=game_state,
            available_actions=available_actions,
            combat_mode=combat_mode,
            available_action_set=self._available_action_set,
            infer_action_type_from_text=self._infer_action_type_from_text,
            find_referenced_combatant=self._find_referenced_combatant,
            select_default_enemy_target=self._select_default_enemy_target,
            infer_spell_name_from_text=self._infer_spell_name_from_text,
            combatant_name=self._combatant_name,
            describe_inferred_action=self._describe_inferred_action,
        )

    def _build_default_combat_action(
        self,
        raw: str,
        *,
        game_state: dict[str, Any],
        available_actions: Optional[Sequence[str]],
    ) -> Optional[dict[str, Any]]:
        """Create a deterministic combat action when the LLM output is unusable."""
        return build_default_combat_action(
            raw,
            character_name=self._character_name,
            game_state=game_state,
            available_actions=available_actions,
            available_action_set=self._available_action_set,
            select_default_enemy_target=self._select_default_enemy_target,
            combatant_name=self._combatant_name,
        )

    @staticmethod
    def _available_action_set(available_actions: Optional[Sequence[str]]) -> set[str]:
        if not available_actions:
            return set(PLAYER_ACTION_TYPES)
        return {str(action).strip() for action in available_actions if str(action).strip()}

    @staticmethod
    def _infer_action_type_from_text(raw: str, available_actions: set[str]) -> Optional[str]:
        haystack = f" {_normalize_for_match(raw)} "
        for action_type, keywords in _ACTION_KEYWORDS:
            if action_type not in available_actions:
                continue
            for keyword in keywords:
                needle = f" {_normalize_for_match(keyword)} "
                if needle in haystack:
                    return action_type
        return None

    def _find_referenced_combatant(
        self,
        raw: str,
        game_state: dict[str, Any],
    ) -> Optional[str]:
        combatants = game_state.get("combatants", {})
        if not isinstance(combatants, dict):
            return None

        haystack = f" {_normalize_for_match(raw).replace('_', ' ')} "
        for cid, cdata in combatants.items():
            if cid == self._character_id or not self._is_alive_combatant(cdata):
                continue
            aliases = [cid, str(cid).replace("_", " ")]
            if isinstance(cdata, dict) and cdata.get("name"):
                aliases.append(str(cdata["name"]))
            for alias in aliases:
                needle = f" {_normalize_for_match(alias).replace('_', ' ')} "
                if needle.strip() and needle in haystack:
                    return str(cid)
        return None

    def _select_default_enemy_target(self, game_state: dict[str, Any]) -> Optional[str]:
        combatants = game_state.get("combatants", {})
        if not isinstance(combatants, dict):
            return None

        characters = game_state.get("characters", {})
        character_ids = set(characters) if isinstance(characters, dict) else set()
        candidates: list[tuple[int, str]] = []
        for cid, cdata in combatants.items():
            if cid == self._character_id or not self._is_alive_combatant(cdata):
                continue
            if not self._looks_like_enemy_combatant(str(cid), cdata, character_ids):
                continue
            hp = self._combatant_hp(cdata)
            candidates.append((hp if hp is not None else 9999, str(cid)))

        if not candidates:
            return None
        candidates.sort(key=lambda item: (item[0], item[1]))
        return candidates[0][1]

    @staticmethod
    def _looks_like_enemy_combatant(
        combatant_id: str,
        cdata: Any,
        character_ids: set[str],
    ) -> bool:
        if isinstance(cdata, dict):
            if cdata.get("is_player") is True:
                return False
            if cdata.get("is_player") is False:
                return True
            if cdata.get("monster_id") or cdata.get("cr") is not None:
                return True
        return combatant_id not in character_ids

    @staticmethod
    def _combatant_hp(cdata: Any) -> Optional[int]:
        if not isinstance(cdata, dict):
            return None
        raw_hp = cdata.get("hp", cdata.get("current_hp"))
        if raw_hp is None:
            return None
        try:
            return int(raw_hp)
        except (TypeError, ValueError):
            return None

    @classmethod
    def _is_alive_combatant(cls, cdata: Any) -> bool:
        if isinstance(cdata, dict):
            status = str(cdata.get("status", "active")).lower()
            if status in INACTIVE_STATUSES:
                return False
        hp = cls._combatant_hp(cdata)
        return hp is None or hp > 0

    @staticmethod
    def _combatant_name(game_state: dict[str, Any], target: Optional[str]) -> str:
        if target is None:
            return "la cible"
        combatants = game_state.get("combatants", {})
        if isinstance(combatants, dict):
            cdata = combatants.get(target, {})
            if isinstance(cdata, dict) and cdata.get("name"):
                return str(cdata["name"])
        return target

    def _normalize_target_reference(
        self,
        raw_target: Any,
        game_state: dict[str, Any],
    ) -> Optional[str]:
        if raw_target is None:
            return None
        if not isinstance(raw_target, str):
            return str(raw_target)

        stripped = raw_target.strip()
        if not stripped or stripped.lower() in {"null", "none", "aucun"}:
            return None

        resolved = self._find_referenced_combatant(stripped, game_state)
        return resolved or stripped

    def _infer_spell_name_from_text(
        self,
        raw: str,
        game_state: dict[str, Any],
    ) -> Optional[str]:
        character = self._extract_character(game_state)
        known_spells = character.get("known_spells", [])
        if not isinstance(known_spells, list):
            return None
        haystack = f" {_normalize_for_match(raw).replace('_', ' ')} "
        for spell in known_spells:
            needle = f" {_normalize_for_match(spell).replace('_', ' ')} "
            if needle.strip() and needle in haystack:
                return str(spell)
        return None

    @staticmethod
    def _describe_inferred_action(
        action_type: str,
        target_name: str,
        raw: str,
    ) -> str:
        if action_type == "attack":
            return f"Attaque {target_name}"
        if action_type == "cast_spell":
            return f"Lance un sort sur {target_name}"
        if action_type in {"shove", "help"}:
            return f"{action_type} {target_name}"
        return raw.strip()[:160] or f"Action {action_type}"

    def _compact_combat_state(self, game_state: dict[str, Any]) -> dict[str, Any]:
        """Return a small combat prompt state while preserving full state for parsing."""
        combatants = game_state.get("combatants", {})
        if not isinstance(combatants, dict):
            return game_state

        characters = game_state.get("characters", {})
        character_ids = set(characters) if isinstance(characters, dict) else set()
        allies: list[dict[str, Any]] = []
        enemies: list[dict[str, Any]] = []

        for cid, cdata in combatants.items():
            if not isinstance(cdata, dict):
                continue
            status = str(cdata.get("status", "active")).lower()
            try:
                hp = int(cdata.get("hp", cdata.get("current_hp", 0)))
            except (TypeError, ValueError):
                hp = 0
            entry = {
                "id": cid,
                "name": cdata.get("name", cid),
                "hp": hp,
                "hp_max": cdata.get("hp_max"),
                "ac": cdata.get("ac"),
                "status": status,
                "conditions": cdata.get("conditions", []),
            }
            if cdata.get("is_player") is True or cid in character_ids:
                allies.append(entry)
            elif hp > 0 and status not in INACTIVE_STATUSES:
                enemies.append(entry)

        return {
            "phase": game_state.get("phase", "COMBAT"),
            "round": game_state.get("round_number"),
            "self_id": self._character_id,
            "allies": allies,
            "enemies": enemies,
        }

    def _safe_recovered_roleplay(
        self,
        action_type: Optional[str],
        action_description: Optional[str],
        target: Optional[str],
        game_state: dict[str, Any],
    ) -> str:
        target_name = self._combatant_name(game_state, target)
        clean_description = (action_description or "").strip().rstrip(".!?")
        if action_type == "attack" and target:
            return f"{self._character_name} reprend l'initiative et attaque {target_name}."
        if action_type == "cast_spell" and target:
            return f"{self._character_name} concentre sa magie vers {target_name}."
        if clean_description:
            return f"{self._character_name} agit avec prudence : {clean_description}."
        return f"{self._character_name} se remet en garde."

    def _parse_player_action(
        self,
        data: dict[str, Any],
        raw: str,
        *,
        game_state: Optional[dict[str, Any]] = None,
    ) -> PlayerActionChoice:
        """Convertit le dict JSON parsé en PlayerActionChoice Pydantic."""
        action_type = str(data.get("action_type", "wait")).strip().lower()
        if action_type not in PLAYER_ACTION_TYPES:
            logger.warning(
                "PlayerAgent[%s] : action_type '%s' invalide, fallback wait",
                self._character_name,
                action_type,
            )
            action_type = "wait"

        params = data.get("params", {})
        if not isinstance(params, dict):
            params = {}

        target = self._normalize_target_reference(data.get("target"), game_state or {})

        try:
            return PlayerActionChoice(
                action_type=action_type,
                action_description=str(data.get("action_description", "")),
                target=target,
                params=params,
                roleplay_text=str(data.get("roleplay_text", raw.strip()[:300])),
                inner_reasoning=data.get("inner_reasoning"),
            )
        except Exception as exc:
            logger.error(
                "PlayerAgent[%s] : échec parsing PlayerActionChoice : %s",
                self._character_name,
                exc,
            )
            return _fallback_action(error=f"ParseError: {exc}")

    def _extract_character(self, game_state: dict[str, Any]) -> dict[str, Any]:
        """Extrait les données du personnage depuis le game_state."""
        characters = game_state.get("characters", {})
        character = characters.get(self._character_id, {}) if isinstance(characters, dict) else {}
        result = dict(character) if isinstance(character, dict) else {}
        combatants = game_state.get("combatants", {})
        if isinstance(combatants, dict):
            cdata = combatants.get(self._character_id, {})
            if isinstance(cdata, dict):
                result.setdefault("name", cdata.get("name", self._character_name))
                result["current_hp"] = cdata.get(
                    "hp",
                    result.get("current_hp", result.get("hp", 1)),
                )
                result.setdefault("max_hp", cdata.get("hp_max"))
                result.setdefault("conditions", cdata.get("conditions", []))
        if "current_hp" not in result and "hp" in result:
            result["current_hp"] = result["hp"]
        return result

    @staticmethod
    def _summarize_recent_narrative(game_state: dict[str, Any]) -> str:
        phase = str(game_state.get("phase") or "").upper()
        if phase == "EXPLORATION":
            return (
                "[Système] La scène actuelle est hors combat. "
                "Si un combat vient de se terminer, les ennemis sont vaincus et le calme revient."
            )
        return "(aucun message récent)"

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
