from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import ollama
import pytest

from app.llm.ollama_client import OllamaClient, OllamaError


@pytest.fixture
def client() -> OllamaClient:
    return OllamaClient(base_url="http://localhost:11434", model="test-model")


# ---------------------------------------------------------------------------
# chat()
# ---------------------------------------------------------------------------


async def test_chat_returns_content(client: OllamaClient) -> None:
    """chat() retourne le contenu texte de la réponse Ollama."""
    mock_response = MagicMock()
    mock_response.message.content = "Bienvenue dans la taverne."

    with patch.object(client._client, "chat", new=AsyncMock(return_value=mock_response)):
        result = await client.chat([{"role": "user", "content": "Bonjour"}])

    assert result == "Bienvenue dans la taverne."


async def test_chat_passes_options(client: OllamaClient) -> None:
    """chat() transmet temperature et num_predict à Ollama."""
    mock_response = MagicMock()
    mock_response.message.content = "ok"
    mock_chat = AsyncMock(return_value=mock_response)

    with patch.object(client._client, "chat", new=mock_chat):
        await client.chat(
            messages=[{"role": "user", "content": "test"}],
            temperature=0.3,
            max_tokens=512,
        )

    call_kwargs = mock_chat.call_args.kwargs
    assert call_kwargs["options"]["temperature"] == 0.3
    assert call_kwargs["options"]["num_predict"] == 512


async def test_chat_uses_custom_model(client: OllamaClient) -> None:
    """chat() utilise le modèle passé en paramètre si fourni."""
    mock_response = MagicMock()
    mock_response.message.content = "ok"
    mock_chat = AsyncMock(return_value=mock_response)

    with patch.object(client._client, "chat", new=mock_chat):
        await client.chat(
            messages=[{"role": "user", "content": "test"}],
            model="llama3:8b",
        )

    assert mock_chat.call_args.kwargs["model"] == "llama3:8b"


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


async def test_chat_retries_on_connect_error(client: OllamaClient) -> None:
    """chat() réessaie jusqu'à MAX_RETRIES fois sur ConnectError."""
    mock_response = MagicMock()
    mock_response.message.content = "ok après retry"

    call_count = 0

    async def flaky_chat(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            raise httpx.ConnectError("Connection refused")
        return mock_response

    with patch.object(client._client, "chat", new=flaky_chat):
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await client.chat([{"role": "user", "content": "test"}])

    assert result == "ok après retry"
    assert call_count == 3


async def test_chat_raises_ollama_error_after_max_retries(client: OllamaClient) -> None:
    """chat() lève OllamaError après avoir épuisé toutes les tentatives."""
    with patch.object(
        client._client,
        "chat",
        new=AsyncMock(side_effect=httpx.ConnectError("Connection refused")),
    ):
        with patch("asyncio.sleep", new=AsyncMock()):
            with pytest.raises(OllamaError, match="injoignable"):
                await client.chat([{"role": "user", "content": "test"}])


async def test_chat_retries_on_response_error(client: OllamaClient) -> None:
    """chat() réessaie sur ollama.ResponseError."""
    mock_response = MagicMock()
    mock_response.message.content = "récupéré"

    call_count = 0

    async def flaky(**kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise ollama.ResponseError("model not found")
        return mock_response

    with patch.object(client._client, "chat", new=flaky):
        with patch("asyncio.sleep", new=AsyncMock()):
            result = await client.chat([{"role": "user", "content": "test"}])

    assert result == "récupéré"


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


async def test_generate_returns_response(client: OllamaClient) -> None:
    """generate() retourne le champ 'response' de la réponse Ollama."""
    mock_response = MagicMock()
    mock_response.response = "Une forêt dense s'étend devant vous."

    with patch.object(client._client, "generate", new=AsyncMock(return_value=mock_response)):
        result = await client.generate(prompt="Décris une forêt.")

    assert result == "Une forêt dense s'étend devant vous."


async def test_generate_passes_system_prompt(client: OllamaClient) -> None:
    """generate() transmet le system prompt à Ollama."""
    mock_response = MagicMock()
    mock_response.response = "ok"
    mock_gen = AsyncMock(return_value=mock_response)

    with patch.object(client._client, "generate", new=mock_gen):
        await client.generate(prompt="test", system="Tu es un MJ.")

    assert mock_gen.call_args.kwargs["system"] == "Tu es un MJ."


# ---------------------------------------------------------------------------
# is_available()
# ---------------------------------------------------------------------------


async def test_is_available_true(client: OllamaClient) -> None:
    with patch.object(client._client, "list", new=AsyncMock(return_value=[])):
        assert await client.is_available() is True


async def test_is_available_false(client: OllamaClient) -> None:
    with patch.object(
        client._client,
        "list",
        new=AsyncMock(side_effect=httpx.ConnectError("refused")),
    ):
        assert await client.is_available() is False
