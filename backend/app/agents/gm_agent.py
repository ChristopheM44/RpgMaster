from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.agents.base_agent import BaseAgent
from app.agents.context_manager import ContextManager
from app.agents.schemas import AgentContext, AgentResponse, GMAction, GMResponse
from app.config import settings
from app.llm.ollama_client import OllamaClient, OllamaError

logger = logging.getLogger(__name__)

_FALLBACK_NARRATION = (
    "Le Maître du Jeu réfléchit… "
    "(Le système LLM est temporairement indisponible. Veuillez réessayer dans un instant.)"
)


class GMAgent(BaseAgent):
    """Agent Maître du Jeu : narration, gestion des scènes et des PNJ.

    Pipeline complet :
    contexte → template Jinja2 → LLM (Ollama) → extraction JSON → GMResponse Pydantic
    """

    def __init__(
        self,
        client: Optional[OllamaClient] = None,
        model: Optional[str] = None,
    ):
        self._client = client or OllamaClient(model=model or settings.gm_model)
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
            raw = await self._client.chat(messages=messages, temperature=0.75, max_tokens=1024)
        except OllamaError as exc:
            logger.error("GMAgent : appel LLM échoué : %s", exc)
            return GMResponse(narration=_FALLBACK_NARRATION)

        data = self._extract_json(raw)
        if data is None:
            logger.warning("GMAgent : le LLM n'a pas retourné du JSON — utilisation du texte brut")
            return GMResponse(narration=raw.strip())

        return self._parse_gm_response(data, raw)

    def _build_messages(
        self,
        user_prompt: str,
        context_manager: Optional[ContextManager],
    ) -> list[dict[str, str]]:
        """Construit la liste de messages pour l'API Ollama."""
        if context_manager is not None:
            msgs = context_manager.to_ollama_messages(self._system_prompt)
        else:
            msgs = [{"role": "system", "content": self._system_prompt}]
        msgs.append({"role": "user", "content": user_prompt})
        return msgs

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
            return GMResponse(
                narration=str(data.get("narration", raw.strip())),
                actions=actions,
                mood=str(data.get("mood", "neutral")),
                inner_reasoning=data.get("inner_reasoning"),
            )
        except Exception as exc:
            logger.error("GMAgent : échec parsing GMResponse : %s — data=%s", exc, data)
            return GMResponse(narration=str(data.get("narration", raw.strip())))

    @staticmethod
    def _format_messages(messages: Optional[list]) -> str:
        """Formate une liste de messages récents en texte pour les templates."""
        if not messages:
            return "(aucun message récent)"
        lines: list[str] = []
        for msg in messages[-10:]:
            speaker = getattr(msg, "speaker", "?")
            content = getattr(msg, "content", "")
            lines.append(f"[{speaker}] {content}")
        return "\n".join(lines)
