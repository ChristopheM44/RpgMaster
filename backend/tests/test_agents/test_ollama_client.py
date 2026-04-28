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


@pytest.fixture
def sdk_client(client: OllamaClient):
    """Client SDK Ollama mocké sans dépendre de l'initialisation paresseuse."""
    mock_sdk = MagicMock()
    with patch.object(client, "_get_client", return_value=mock_sdk):
        yield mock_sdk


# ---------------------------------------------------------------------------
# chat()
# ---------------------------------------------------------------------------


async def test_chat_returns_content(client: OllamaClient, sdk_client) -> None:
    """chat() retourne le contenu texte de la réponse Ollama."""
    mock_response = MagicMock()
    mock_response.message.content = "Bienvenue dans la taverne."
    sdk_client.chat = AsyncMock(return_value=mock_response)

    result = await client.chat([{"role": "user", "content": "Bonjour"}])

    assert result == "Bienvenue dans la taverne."


async def test_chat_passes_options(client: OllamaClient, sdk_client) -> None:
    """chat() transmet temperature et num_predict à Ollama."""
    mock_response = MagicMock()
    mock_response.message.content = "ok"
    mock_chat = AsyncMock(return_value=mock_response)
    sdk_client.chat = mock_chat

    await client.chat(
        messages=[{"role": "user", "content": "test"}],
        temperature=0.3,
        max_tokens=512,
    )

    call_kwargs = mock_chat.call_args.kwargs
    assert call_kwargs["options"]["temperature"] == 0.3
    assert call_kwargs["options"]["num_predict"] == 512


async def test_chat_uses_custom_model(client: OllamaClient, sdk_client) -> None:
    """chat() utilise le modèle passé en paramètre si fourni."""
    mock_response = MagicMock()
    mock_response.message.content = "ok"
    mock_chat = AsyncMock(return_value=mock_response)
    sdk_client.chat = mock_chat

    await client.chat(
        messages=[{"role": "user", "content": "test"}],
        model="llama3:8b",
    )

    assert mock_chat.call_args.kwargs["model"] == "llama3:8b"


async def test_chat_serializes_concurrent_requests(client: OllamaClient, sdk_client) -> None:
    """Le limiteur global évite deux requêtes Ollama simultanées par défaut."""
    active_calls = 0
    max_active_calls = 0

    async def slow_chat(**kwargs):
        nonlocal active_calls, max_active_calls
        active_calls += 1
        max_active_calls = max(max_active_calls, active_calls)
        await asyncio.sleep(0.01)
        active_calls -= 1
        mock_response = MagicMock()
        mock_response.message.content = "ok"
        return mock_response

    sdk_client.chat = slow_chat

    results = await asyncio.gather(
        client.chat([{"role": "user", "content": "a"}]),
        client.chat([{"role": "user", "content": "b"}]),
    )

    assert results == ["ok", "ok"]
    assert max_active_calls == 1


# ---------------------------------------------------------------------------
# Retry logic
# ---------------------------------------------------------------------------


async def test_chat_retries_on_connect_error(client: OllamaClient, sdk_client) -> None:
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

    sdk_client.chat = flaky_chat

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await client.chat([{"role": "user", "content": "test"}])

    assert result == "ok après retry"
    assert call_count == 3


async def test_chat_raises_ollama_error_after_max_retries(
    client: OllamaClient, sdk_client
) -> None:
    """chat() lève OllamaError après avoir épuisé toutes les tentatives."""
    sdk_client.chat = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))

    with patch("asyncio.sleep", new=AsyncMock()):
        with pytest.raises(OllamaError, match="injoignable"):
            await client.chat([{"role": "user", "content": "test"}])


async def test_chat_retries_on_response_error(client: OllamaClient, sdk_client) -> None:
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

    sdk_client.chat = flaky

    with patch("asyncio.sleep", new=AsyncMock()):
        result = await client.chat([{"role": "user", "content": "test"}])

    assert result == "récupéré"


# ---------------------------------------------------------------------------
# generate()
# ---------------------------------------------------------------------------


async def test_generate_returns_response(client: OllamaClient, sdk_client) -> None:
    """generate() retourne le champ 'response' de la réponse Ollama."""
    mock_response = MagicMock()
    mock_response.response = "Une forêt dense s'étend devant vous."
    sdk_client.generate = AsyncMock(return_value=mock_response)

    result = await client.generate(prompt="Décris une forêt.")

    assert result == "Une forêt dense s'étend devant vous."


async def test_generate_passes_system_prompt(client: OllamaClient, sdk_client) -> None:
    """generate() transmet le system prompt à Ollama."""
    mock_response = MagicMock()
    mock_response.response = "ok"
    mock_gen = AsyncMock(return_value=mock_response)
    sdk_client.generate = mock_gen

    await client.generate(prompt="test", system="Tu es un MJ.")

    assert mock_gen.call_args.kwargs["system"] == "Tu es un MJ."


# ---------------------------------------------------------------------------
# is_available()
# ---------------------------------------------------------------------------


async def test_is_available_true(client: OllamaClient, sdk_client) -> None:
    sdk_client.list = AsyncMock(return_value=[])

    assert await client.is_available() is True


async def test_is_available_false(client: OllamaClient, sdk_client) -> None:
    sdk_client.list = AsyncMock(side_effect=httpx.ConnectError("refused"))

    assert await client.is_available() is False
