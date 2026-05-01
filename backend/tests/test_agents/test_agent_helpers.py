"""Tests pour les helpers partagés de BaseAgent.

_extract_json, _format_messages, _build_messages sont les primitives
communes à GMAgent et PlayerAgent.  Les tester directement protège le
Lot 1.4 contre toute régression lors de la création du pipeline unifié.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.agents.base_agent import BaseAgent
from app.agents.schemas import AgentContext, AgentResponse

# ---------------------------------------------------------------------------
# Stub concret (BaseAgent est abstract)
# ---------------------------------------------------------------------------


class _StubAgent(BaseAgent):
    _system_prompt = "Système de test."

    async def think(self, context: AgentContext) -> AgentResponse:  # pragma: no cover
        return AgentResponse(content="", actions=[])


@pytest.fixture
def agent() -> _StubAgent:
    return _StubAgent()


# ---------------------------------------------------------------------------
# _extract_json
# ---------------------------------------------------------------------------


class TestExtractJson:
    def test_direct_valid_json(self, agent: _StubAgent) -> None:
        result = agent._extract_json('{"narration": "Bonjour"}')
        assert result == {"narration": "Bonjour"}

    def test_json_in_markdown_block(self, agent: _StubAgent) -> None:
        raw = '```json\n{"narration": "Combat"}\n```'
        result = agent._extract_json(raw)
        assert result is not None
        assert result["narration"] == "Combat"

    def test_json_embedded_in_prose(self, agent: _StubAgent) -> None:
        raw = 'Voici ma réponse : {"mood": "tense"} comme convenu.'
        result = agent._extract_json(raw)
        assert result is not None
        assert result["mood"] == "tense"

    def test_truncated_json_returns_none(self, agent: _StubAgent) -> None:
        result = agent._extract_json('{"narration": "coupé', log_failure=False)
        assert result is None

    def test_empty_string_returns_none(self, agent: _StubAgent) -> None:
        result = agent._extract_json("", log_failure=False)
        assert result is None

    def test_pure_prose_returns_none(self, agent: _StubAgent) -> None:
        result = agent._extract_json("Ceci est du texte sans JSON.", log_failure=False)
        assert result is None

    def test_first_balanced_block_only(self, agent: _StubAgent) -> None:
        """Quand le LLM produit deux blocs JSON, seul le premier est retourné."""
        raw = '{"first": 1} du texte {"second": 2}'
        result = agent._extract_json(raw)
        assert result == {"first": 1}

    def test_nested_json_extracted_correctly(self, agent: _StubAgent) -> None:
        raw = '{"actions": [{"type": "roll_request", "params": {"dc": 15}}]}'
        result = agent._extract_json(raw)
        assert result is not None
        assert result["actions"][0]["type"] == "roll_request"


# ---------------------------------------------------------------------------
# _format_messages
# ---------------------------------------------------------------------------


class TestFormatMessages:
    def test_empty_list_returns_placeholder(self, agent: _StubAgent) -> None:
        assert agent._format_messages([]) == "(aucun message récent)"

    def test_none_returns_placeholder(self, agent: _StubAgent) -> None:
        assert agent._format_messages(None) == "(aucun message récent)"

    def test_formats_speaker_and_content(self, agent: _StubAgent) -> None:
        msg = MagicMock(speaker="Thorvald", content="J'avance.")
        result = agent._format_messages([msg])
        assert "[Thorvald] J'avance." in result

    def test_multiple_messages_joined_with_newlines(self, agent: _StubAgent) -> None:
        msgs = [
            MagicMock(speaker="MJ", content="Une forêt sombre."),
            MagicMock(speaker="Aria", content="J'entre prudemment."),
        ]
        result = agent._format_messages(msgs)
        assert "[MJ] Une forêt sombre." in result
        assert "[Aria] J'entre prudemment." in result
        assert result.index("[MJ]") < result.index("[Aria]")

    def test_window_keeps_last_10_only(self, agent: _StubAgent) -> None:
        msgs = [MagicMock(speaker="P", content=f"msg{i:03d}") for i in range(15)]
        result = agent._format_messages(msgs)
        # Les 10 derniers (indices 5–14) sont inclus ; les 5 premiers non.
        for i in range(5, 15):
            assert f"msg{i:03d}" in result
        for i in range(0, 5):
            assert f"msg{i:03d}" not in result


# ---------------------------------------------------------------------------
# _build_messages
# ---------------------------------------------------------------------------


class TestBuildMessages:
    def test_without_context_manager_returns_system_and_user(
        self, agent: _StubAgent
    ) -> None:
        msgs = agent._build_messages("Bonjour", None)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "system"
        assert msgs[0]["content"] == "Système de test."
        assert msgs[1]["role"] == "user"
        assert msgs[1]["content"] == "Bonjour"

    def test_with_context_manager_appends_user_last(self, agent: _StubAgent) -> None:
        cm = MagicMock()
        cm.to_ollama_messages.return_value = [
            {"role": "system", "content": "Système de test."},
            {"role": "user", "content": "Action 1"},
            {"role": "assistant", "content": "Narration 1"},
        ]
        msgs = agent._build_messages("Action 2", cm)
        assert len(msgs) == 4
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "Action 2"

    def test_with_context_manager_calls_to_ollama_messages(
        self, agent: _StubAgent
    ) -> None:
        cm = MagicMock()
        cm.to_ollama_messages.return_value = [
            {"role": "system", "content": "Système de test."}
        ]
        agent._build_messages("prompt", cm)
        cm.to_ollama_messages.assert_called_once_with("Système de test.")
