from __future__ import annotations

import json
import logging
from functools import lru_cache
from typing import Any, Optional

from app.agents.base_agent import BaseAgent
from app.agents.schemas import AgentContext, AgentResponse
from app.config import (
    get_forge_chapter_max_tokens,
    get_forge_indexes_max_tokens,
    get_forge_outline_max_tokens,
    get_forge_source_note_max_tokens,
)
from app.engine.srd_data import get_monsters
from app.llm.base_client import LLMClient
from app.llm.model_router import router

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def compact_srd_monster_index() -> list[dict[str, Any]]:
    """Compact list of legal SRD monster ids for Forge prompts."""
    return [
        {
            "id": str(monster.get("id") or ""),
            "name_fr": monster.get("name_fr") or monster.get("name") or "",
            "type": monster.get("type") or "",
            "cr": monster.get("cr"),
        }
        for monster in get_monsters()
        if monster.get("id")
    ]


class CampaignForgeAgent(BaseAgent):
    """LLM helper dedicated to campaign dossier generation and canon synthesis."""

    def __init__(self, client: Optional[LLMClient] = None) -> None:
        self._client: LLMClient = client or router.get_gm_client()
        self._srd_monster_index_json = json.dumps(
            compact_srd_monster_index(),
            ensure_ascii=False,
            separators=(",", ":"),
        )
        self._system_prompt = self._render_prompt(
            "campaign_forge_system.txt",
            {"srd_monster_index": self._srd_monster_index_json},
        )

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
                "srd_monster_index": self._srd_monster_index_json,
            },
        )
        return await self._call_json(prompt, max_tokens=4096)

    async def forge_outline(
        self,
        campaign: dict[str, Any],
        brief: dict[str, Any],
        options: dict[str, Any],
        source_notes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt = self._render_prompt(
            "campaign_forge_outline.txt",
            {
                "campaign": json.dumps(campaign, ensure_ascii=False, indent=2),
                "brief": json.dumps(brief, ensure_ascii=False, indent=2),
                "options": json.dumps(options, ensure_ascii=False, indent=2),
                "source_notes": json.dumps(source_notes, ensure_ascii=False, indent=2),
                "srd_monster_index": self._srd_monster_index_json,
            },
        )
        return await self._call_json(prompt, max_tokens=get_forge_outline_max_tokens())

    async def forge_chapter(
        self,
        campaign: dict[str, Any],
        player_contract: dict[str, Any],
        visible_chapter: dict[str, Any],
        chapter_index: int,
        chapter_total: int,
        source_notes: list[dict[str, Any]],
        options: dict[str, Any],
    ) -> dict[str, Any]:
        prompt = self._render_prompt(
            "campaign_forge_chapter.txt",
            {
                "campaign": json.dumps(campaign, ensure_ascii=False, indent=2),
                "player_contract": json.dumps(player_contract, ensure_ascii=False, indent=2),
                "visible_chapter": json.dumps(visible_chapter, ensure_ascii=False, indent=2),
                "chapter_index": chapter_index,
                "chapter_total": chapter_total,
                "source_notes": json.dumps(source_notes, ensure_ascii=False, indent=2),
                "options": json.dumps(options, ensure_ascii=False, indent=2),
                "srd_monster_index": self._srd_monster_index_json,
            },
        )
        return await self._call_json(prompt, max_tokens=get_forge_chapter_max_tokens())

    async def forge_global_indexes(
        self,
        campaign: dict[str, Any],
        brief: dict[str, Any],
        options: dict[str, Any],
        player_contract: dict[str, Any],
        chapters: list[dict[str, Any]],
        source_notes: list[dict[str, Any]],
    ) -> dict[str, Any]:
        prompt = self._render_prompt(
            "campaign_forge_indexes.txt",
            {
                "campaign": json.dumps(campaign, ensure_ascii=False, indent=2),
                "brief": json.dumps(brief, ensure_ascii=False, indent=2),
                "options": json.dumps(options, ensure_ascii=False, indent=2),
                "player_contract": json.dumps(player_contract, ensure_ascii=False, indent=2),
                "chapters": json.dumps(chapters, ensure_ascii=False, indent=2),
                "source_notes": json.dumps(source_notes, ensure_ascii=False, indent=2),
                "srd_monster_index": self._srd_monster_index_json,
            },
        )
        return await self._call_json(prompt, max_tokens=get_forge_indexes_max_tokens())

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
        return await self._call_json(prompt, max_tokens=get_forge_source_note_max_tokens())

    async def compress_canon_entries(
        self,
        field_name: str,
        old_entries: list[Any],
        existing_summary: str = "",
        max_len: int = 4000,
    ) -> str:
        """Condense des entrées de canon obsolètes en un paragraphe de résumé narratif.

        Utilisé par la fenêtre glissante dans ``campaign_dossier_service`` pour
        éviter la troncature brutale des listes longues.
        Retourne ``existing_summary`` inchangé en cas d'erreur LLM (fallback silencieux).
        """
        prompt = self._render_prompt(
            "gm_compress_canon.txt",
            {"field_name": field_name, "old_entries": old_entries},
        )
        try:
            raw = await self._client.chat(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=600,
            )
            compressed = (raw or "").strip()
            if not compressed:
                return existing_summary
            separator = "\n\n" if existing_summary else ""
            combined = existing_summary + separator + compressed
            return combined[:max_len]
        except Exception as exc:
            logger.warning(
                "compress_canon_entries(%s): compression échouée, résumé existant conservé — %s",
                field_name,
                exc,
            )
            return existing_summary

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
