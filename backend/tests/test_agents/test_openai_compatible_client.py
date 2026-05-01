from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from openai import APIConnectionError, APIStatusError

from app.llm.openai_compatible_client import (
    OpenAICompatibleClient,
    OpenAICompatibleError,
)


@pytest.fixture
def client() -> OpenAICompatibleClient:
    return OpenAICompatibleClient(
        base_url="http://provider.test/v1",
        api_key="test-key",
        model="test-model",
    )


@pytest.fixture
def sdk_client(client: OpenAICompatibleClient):
    mock_sdk = MagicMock()
    with patch.object(client, "_get_client", return_value=mock_sdk):
        yield mock_sdk


def _chat_response(content: str):
    response = MagicMock()
    choice = MagicMock()
    choice.message.content = content
    response.choices = [choice]
    return response


def _api_connection_error() -> APIConnectionError:
    request = httpx.Request("POST", "http://provider.test/v1/chat/completions")
    return APIConnectionError(request=request)


def _api_status_error(status_code: int = 500) -> APIStatusError:
    request = httpx.Request("POST", "http://provider.test/v1/chat/completions")
    response = httpx.Response(status_code=status_code, request=request)
    return APIStatusError("server error", response=response, body=None)


async def test_chat_returns_content_and_passes_options(
    client: OpenAICompatibleClient,
    sdk_client,
) -> None:
    mock_create = AsyncMock(return_value=_chat_response("Bienvenue."))
    sdk_client.chat.completions.create = mock_create

    result = await client.chat(
        messages=[{"role": "user", "content": "Bonjour"}],
        temperature=0.2,
        max_tokens=256,
    )

    assert result == "Bienvenue."
    call_kwargs = mock_create.call_args.kwargs
    assert call_kwargs["model"] == "test-model"
    assert call_kwargs["temperature"] == 0.2
    assert call_kwargs["max_tokens"] == 256
    assert call_kwargs["messages"] == [{"role": "user", "content": "Bonjour"}]


async def test_generate_builds_chat_messages(client: OpenAICompatibleClient) -> None:
    mock_chat = AsyncMock(return_value="ok")

    with patch.object(client, "chat", new=mock_chat):
        result = await client.generate(
            prompt="Decris la porte.",
            system="Tu es un MJ.",
            temperature=0.1,
            max_tokens=64,
        )

    assert result == "ok"
    mock_chat.assert_awaited_once_with(
        messages=[
            {"role": "system", "content": "Tu es un MJ."},
            {"role": "user", "content": "Decris la porte."},
        ],
        temperature=0.1,
        max_tokens=64,
    )


async def test_chat_retries_on_connection_error(
    client: OpenAICompatibleClient,
    sdk_client,
) -> None:
    mock_create = AsyncMock(
        side_effect=[
            _api_connection_error(),
            _api_connection_error(),
            _chat_response("ok apres retry"),
        ]
    )
    sdk_client.chat.completions.create = mock_create

    with patch("app.llm.retry.asyncio.sleep", new=AsyncMock()):
        result = await client.chat([{"role": "user", "content": "test"}])

    assert result == "ok apres retry"
    assert mock_create.await_count == 3


async def test_chat_raises_openai_error_after_max_retries(
    client: OpenAICompatibleClient,
    sdk_client,
) -> None:
    mock_create = AsyncMock(side_effect=_api_connection_error())
    sdk_client.chat.completions.create = mock_create

    with patch("app.llm.retry.asyncio.sleep", new=AsyncMock()):
        with pytest.raises(OpenAICompatibleError, match="Provider injoignable"):
            await client.chat([{"role": "user", "content": "test"}])

    assert mock_create.await_count == 3


async def test_chat_converts_status_error_without_retry(
    client: OpenAICompatibleClient,
    sdk_client,
) -> None:
    mock_create = AsyncMock(side_effect=_api_status_error(status_code=500))
    sdk_client.chat.completions.create = mock_create

    with patch("app.llm.retry.asyncio.sleep", new=AsyncMock()) as sleep:
        with pytest.raises(OpenAICompatibleError, match="Erreur API 500"):
            await client.chat([{"role": "user", "content": "test"}])

    assert mock_create.await_count == 1
    sleep.assert_not_awaited()
