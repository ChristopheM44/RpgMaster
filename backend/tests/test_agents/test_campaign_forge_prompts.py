from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock

from app.agents.base_agent import _PROMPTS_DIR
from app.agents.campaign_forge_agent import CampaignForgeAgent, compact_srd_monster_index


def test_compact_srd_monster_index_exposes_all_monsters() -> None:
    index = compact_srd_monster_index()

    assert len(index) == 292
    ids = {item["id"] for item in index}
    assert "skeleton" in ids
    assert "dragon_rouge_venerable" in ids


def test_forge_prompts_do_not_use_old_ten_monster_whitelist() -> None:
    forbidden = (
        "goblin, hobgoblin, orc, skeleton, zombie, wolf, giant_spider, bandit, cultist, bugbear"
    )

    for path in Path(_PROMPTS_DIR).glob("campaign_forge*.txt"):
        assert forbidden not in path.read_text(encoding="utf-8")


def test_campaign_forge_system_prompt_renders_srd_index() -> None:
    agent = CampaignForgeAgent(client=object())

    assert "INDEX SRD MONSTRES COMPACT" in agent._system_prompt
    assert "dragon_rouge_venerable" in agent._system_prompt


async def test_call_json_passes_format_json() -> None:
    """_call_json force une sortie JSON contrainte via format="json" (Piste D.1)."""
    mock_client = AsyncMock()
    mock_client.chat = AsyncMock(return_value='{"ok": true}')
    agent = CampaignForgeAgent(client=mock_client)

    result = await agent._call_json("prompt", max_tokens=100)

    assert result == {"ok": True}
    assert mock_client.chat.call_args.kwargs["format"] == "json"
