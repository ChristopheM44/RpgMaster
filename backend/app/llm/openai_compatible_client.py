from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Optional

from openai import AsyncOpenAI, APIConnectionError, APIStatusError, APITimeoutError

from app.config import get_openai_api_key, get_openai_base_url

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0
_LLM_TIMEOUT = 120.0


class OpenAICompatibleError(Exception):
    """Le provider OpenAI-compatible est injoignable ou a retourné une erreur."""


class OpenAICompatibleClient:
    """Client async pour tout endpoint OpenAI-compatible.

    Compatible : Mistral AI, Groq, OpenRouter, Together AI, DeepSeek,
    Ollama remote avec auth, etc.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self._explicit_base_url = base_url
        self._explicit_api_key = api_key
        self._model = model or "mistral-large-latest"
        self._cached_base_url: Optional[str] = None
        self._cached_api_key: Optional[str] = None
        self._client: Optional[AsyncOpenAI] = None

    @property
    def _base_url(self) -> str:
        return self._explicit_base_url or get_openai_base_url()

    @property
    def _api_key(self) -> str:
        return self._explicit_api_key or get_openai_api_key()

    def _get_client(self) -> AsyncOpenAI:
        current_url = self._base_url
        current_key = self._api_key
        if (
            self._client is None
            or self._cached_base_url != current_url
            or self._cached_api_key != current_key
        ):
            self._client = AsyncOpenAI(
                base_url=current_url,
                api_key=current_key or "no-key",
                timeout=_LLM_TIMEOUT,
            )
            self._cached_base_url = current_url
            self._cached_api_key = current_key
        return self._client

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        async def _call() -> str:
            response = await self._get_client().chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                max_tokens=max_tokens,
            )
            return response.choices[0].message.content or ""

        return await self._with_retry(_call)

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return await self.chat(messages=messages, temperature=temperature, max_tokens=max_tokens)

    async def stream_chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        try:
            stream = await self._get_client().chat.completions.create(
                model=self._model,
                messages=messages,  # type: ignore[arg-type]
                temperature=temperature,
                stream=True,
            )
            async for chunk in stream:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield delta
        except (APIConnectionError, APITimeoutError) as exc:
            raise OpenAICompatibleError(f"Streaming interrompu : {exc}") from exc
        except APIStatusError as exc:
            raise OpenAICompatibleError(
                f"Erreur API {exc.status_code} pendant le streaming : {exc.message}"
            ) from exc

    async def is_available(self) -> bool:
        try:
            await self._get_client().models.list()
            return True
        except APIStatusError:
            # Certains providers ne supportent pas /models mais sont bien disponibles
            return True
        except Exception:
            return False

    async def _with_retry(self, coro_fn) -> str:  # type: ignore[type-arg]
        delay = _BASE_DELAY
        last_exc: Optional[Exception] = None
        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return await coro_fn()
            except (APIConnectionError, APITimeoutError) as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    break
                logger.warning(
                    "OpenAI-compat tentative %d/%d : %s — retry dans %.1fs",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                delay *= 2
            except APIStatusError as exc:
                raise OpenAICompatibleError(
                    f"Erreur API {exc.status_code} : {exc.message}"
                ) from exc
        raise OpenAICompatibleError(
            f"Provider injoignable après {_MAX_RETRIES} tentatives : {last_exc}"
        ) from last_exc
