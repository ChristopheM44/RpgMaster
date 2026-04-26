from __future__ import annotations

import json
import logging
from typing import Any, Optional

from app.agents.base_agent import BaseAgent
from app.agents.schemas import AgentContext, AgentResponse
from app.llm.base_client import LLMClient
from app.llm.model_router import router

logger = logging.getLogger(__name__)


class CampaignForgeAgent(BaseAgent):
    """LLM helper dedicated to campaign dossier generation and canon synthesis."""

    def __init__(self, client: Optional[LLMClient] = None) -> None:
        self._client: LLMClient = client or router.get_gm_client()
        self._system_prompt = self._load_system_prompt("campaign_forge_system.txt")

    async def think(self, context: AgentContext) -> AgentResponse:
        data = await self.forge_dossier(
            campaign={"id": context.session_id, "name": "Campagne", "description": ""},
            brief=context.game_state,
            options={},
            import_sources=[],
        )
        return AgentResponse(content=json.dumps(data, ensure_ascii=False), actions=[])

    async def forge_dossier(
        self,
        campaign: dict[str, Any],
        brief: dict[str, Any],
        options: dict[str, Any],
        import_sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt = self._render_prompt(
            "campaign_forge_dossier.txt",
            {
                "campaign": json.dumps(campaign, ensure_ascii=False, indent=2),
                "brief": json.dumps(brief, ensure_ascii=False, indent=2),
                "options": json.dumps(options, ensure_ascii=False, indent=2),
                "import_sources": json.dumps(import_sources, ensure_ascii=False, indent=2),
            },
        )
        return await self._call_json(prompt, max_tokens=4096)

    async def synthesize_canon(
        self,
        player_contract: dict[str, Any],
        gm_dossier: dict[str, Any],
        played_canon: dict[str, Any],
        game_state: dict[str, Any],
        recent_messages: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt = self._render_prompt(
            "campaign_synthesize_canon.txt",
            {
                "player_contract": json.dumps(player_contract, ensure_ascii=False, indent=2),
                "gm_dossier": json.dumps(gm_dossier, ensure_ascii=False, indent=2),
                "played_canon": json.dumps(played_canon, ensure_ascii=False, indent=2),
                "game_state": json.dumps(game_state, ensure_ascii=False, indent=2),
                "recent_messages": json.dumps(recent_messages, ensure_ascii=False, indent=2),
            },
        )
        return await self._call_json(prompt, max_tokens=3072)

    async def normalize_import_source(self, source: dict[str, Any]) -> dict[str, Any]:
        prompt = self._render_prompt(
            "campaign_import_source.txt",
            {"source": json.dumps(source, ensure_ascii=False, indent=2)},
        )
        return await self._call_json(prompt, max_tokens=2048)

    async def _call_json(self, prompt: str, max_tokens: int) -> dict[str, Any]:
        raw = await self._client.chat(
            messages=[
                {"role": "system", "content": self._system_prompt},
                {"role": "user", "content": prompt},
            ],
            temperature=0.55,
            max_tokens=max_tokens,
        )
        data = self._extract_json(raw)
        if not isinstance(data, dict):
            raise ValueError("CampaignForgeAgent returned no JSON object")
        return data
