from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from app.agents.base_agent import BaseAgent
from app.agents.context_manager import ContextManager
from app.agents.schemas import AgentContext, AgentResponse, GMAction, GMResponse
from app.llm.base_client import LLMClient
from app.llm.model_router import router
from app.llm.ollama_client import OllamaError
from app.llm.openai_compatible_client import OpenAICompatibleError

logger = logging.getLogger(__name__)

_FALLBACK_NARRATION = (
    "Le Maître du Jeu réfléchit… "
    "(Le système LLM est temporairement indisponible. Veuillez réessayer dans un instant.)"
)


class GMAgent(BaseAgent):
    """Agent Maître du Jeu : narration, gestion des scènes et des PNJ.

    Pipeline complet :
    contexte → template Jinja2 → LLM → extraction JSON → GMResponse Pydantic
    """

    def __init__(
        self,
        client: Optional[LLMClient] = None,
        model: Optional[str] = None,
    ):
        self._client: LLMClient = client or router.get_gm_client()
        self._system_prompt = self._load_system_prompt("gm_system.txt")

    # -------------------------------------------------------------------------
    # Interface BaseAgent
    # -------------------------------------------------------------------------

    async def think(self, context: AgentContext) -> AgentResponse:
        """Point d'entrée générique — délègue selon la phase de jeu."""
        if context.game_phase == "COMBAT":
            gm_resp = await self.run_combat_turn(
                game_state=context.game_state,
                context_manager=None,
                player_action=context.player_action,
                messages=context.messages,
                roll_results=context.roll_results or None,
            )
        else:
            gm_resp = await self.narrate(
                game_state=context.game_state,
                context_manager=None,
                player_action=context.player_action,
                messages=context.messages,
            )
        return AgentResponse(
            content=gm_resp.narration,
            actions=gm_resp.actions,
            action_intent=gm_resp.action_intent,
        )

    # -------------------------------------------------------------------------
    # Méthodes spécialisées
    # -------------------------------------------------------------------------

    async def narrate(
        self,
        game_state: dict[str, Any],
        context_manager: Optional[ContextManager] = None,
        player_action: Optional[str] = None,
        messages: Optional[list] = None,
    ) -> GMResponse:
        """Génère une narration d'exploration / générale."""
        user_prompt = self._render_prompt(
            "gm_narrate.txt",
            {
                "game_state": json.dumps(game_state, ensure_ascii=False, indent=2),
                "player_action": player_action or "",
                "recent_messages": self._format_messages(messages),
            },
        )
        return await self._call_and_parse(user_prompt, context_manager)

    async def run_combat_turn(
        self,
        game_state: dict[str, Any],
        context_manager: Optional[ContextManager] = None,
        player_action: Optional[str] = None,
        messages: Optional[list] = None,
        roll_results: Optional[dict[str, Any]] = None,
    ) -> GMResponse:
        """Narre un tour de combat après résolution mécanique par le moteur."""
        user_prompt = self._render_prompt(
            "gm_combat.txt",
            {
                "game_state": json.dumps(game_state, ensure_ascii=False, indent=2),
                "player_action": player_action or "",
                "roll_results": json.dumps(roll_results or {}, ensure_ascii=False),
                "recent_messages": self._format_messages(messages),
            },
        )
        return await self._call_and_parse(user_prompt, context_manager)

    async def run_npc_dialogue(
        self,
        npc_name: str,
        npc_personality: str,
        player_message: str,
        context_manager: Optional[ContextManager] = None,
        messages: Optional[list] = None,
    ) -> GMResponse:
        """Génère une réplique de PNJ avec sa personnalité."""
        user_prompt = self._render_prompt(
            "gm_npc_dialogue.txt",
            {
                "npc_name": npc_name,
                "npc_personality": npc_personality,
                "player_message": player_message,
                "recent_messages": self._format_messages(messages),
            },
        )
        return await self._call_and_parse(user_prompt, context_manager)

    async def narrate_social_conclude(
        self,
        game_state: dict[str, Any],
        player_action: str,
        companion_responses: list[dict[str, str]],
        context_manager: Optional[ContextManager] = None,
    ) -> GMResponse:
        """Narre la conclusion d'une scène sociale après les réponses des compagnons."""
        responses_text = "\n".join(
            f"[{r['speaker']}] {r['text']}" for r in companion_responses
        )
        user_prompt = self._render_prompt(
            "gm_social_conclude.txt",
            {
                "game_state": json.dumps(game_state, ensure_ascii=False, indent=2),
                "player_action": player_action,
                "companion_responses": responses_text,
            },
        )
        return await self._call_and_parse(user_prompt, context_manager)

    async def narrate_outcome(
        self,
        context: AgentContext,
        roll_results: list[dict[str, Any]],
    ) -> str:
        """Narre l'issue d'un ou plusieurs jets de dés après résolution par le moteur."""
        gm_resp = await self.narrate_outcome_response(context, roll_results)
        return gm_resp.narration

    async def narrate_outcome_response(
        self,
        context: AgentContext,
        roll_results: list[dict[str, Any]],
    ) -> GMResponse:
        """Narre l'issue de jets et conserve les actions mécaniques éventuelles."""
        rolls_text = "\n".join(
            "- {label}: {breakdown} → {outcome}".format(
                label=r.get("label", "Jet"),
                breakdown=r.get("breakdown", ""),
                outcome=(
                    "SUCCÈS" if r.get("success") is True
                    else "ÉCHEC" if r.get("success") is False
                    else str(r.get("total", "?"))
                ),
            )
            for r in roll_results
        )
        user_prompt = self._render_prompt(
            "gm_narrate_outcome.txt",
            {
                "game_state": json.dumps(context.game_state, ensure_ascii=False, indent=2),
                "recent_messages": self._format_messages(context.messages or []),
                "player_action": context.player_action or "",
                "roll_results": rolls_text,
            },
        )
        return await self._call_and_parse(user_prompt, None)

    # -------------------------------------------------------------------------
    # Helpers privés
    # -------------------------------------------------------------------------

    async def _call_and_parse(
        self,
        user_prompt: str,
        context_manager: Optional[ContextManager],
    ) -> GMResponse:
        """Appelle le LLM et parse la réponse JSON en GMResponse."""
        messages = self._build_messages(user_prompt, context_manager)

        try:
            raw = await self._client.chat(messages=messages, temperature=0.75, max_tokens=2048)
        except (OllamaError, OpenAICompatibleError) as exc:
            logger.error("GMAgent : appel LLM échoué : %s", exc)
            return GMResponse(narration=_FALLBACK_NARRATION)

        data = self._extract_json(raw)
        if data is None:
            logger.warning(
                "GMAgent : le LLM n'a pas retourné du JSON valide — extraction partielle"
            )
            # Tentative d'extraction du champ narration depuis un JSON tronqué
            match = re.search(r'"narration"\s*:\s*"((?:[^"\\]|\\.)*)', raw)
            narration_text = match.group(1) if match else raw.strip()
            return GMResponse(narration=narration_text)

        return self._parse_gm_response(data, raw)

    def _parse_gm_response(self, data: dict[str, Any], raw: str) -> GMResponse:
        """Convertit le dict JSON parsé en GMResponse Pydantic."""
        try:
            actions = [
                GMAction(
                    type=a.get("type", "unknown"),
                    target=a.get("target"),
                    params=a.get("params", {}),
                )
                for a in data.get("actions", [])
                if isinstance(a, dict)
            ]
            raw_intent = data.get("action_intent")
            action_intent = (
                str(raw_intent)
                if raw_intent in ("social", "environmental", "mixed")
                else None
            )
            return GMResponse(
                narration=str(data.get("narration", raw.strip())),
                actions=actions,
                mood=str(data.get("mood", "neutral")),
                inner_reasoning=data.get("inner_reasoning"),
                action_intent=action_intent,
            )
        except Exception as exc:
            logger.error("GMAgent : échec parsing GMResponse : %s — data=%s", exc, data)
            return GMResponse(narration=str(data.get("narration", raw.strip())))

