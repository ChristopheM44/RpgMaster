from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from typing import Optional

import httpx
import ollama

from app.config import settings

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_BASE_DELAY = 1.0  # seconds, doubles on each retry


class OllamaError(Exception):
    """Ollama est injoignable ou a retourné une erreur."""


class OllamaClient:
    """Client async pour Ollama avec retry et gestion d'erreur.

    Encapsule le SDK officiel ollama-python (>=0.4.0).
    """

    def __init__(self, base_url: Optional[str] = None, model: Optional[str] = None):
        self.base_url = base_url or settings.ollama_base_url
        self.model = model or settings.gm_model
        self._client = ollama.AsyncClient(host=self.base_url)

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    async def chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Envoie une requête chat et retourne le contenu de la réponse."""

        async def _call() -> str:
            response = await self._client.chat(
                model=model or self.model,
                messages=messages,
                options={"temperature": temperature, "num_predict": max_tokens},
            )
            return response.message.content  # type: ignore[union-attr]

        return await self._with_retry(_call)

    async def generate(
        self,
        prompt: str,
        model: Optional[str] = None,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        """Envoie une requête generate et retourne le texte de la réponse."""

        async def _call() -> str:
            response = await self._client.generate(
                model=model or self.model,
                prompt=prompt,
                system=system or "",
                options={"temperature": temperature, "num_predict": max_tokens},
            )
            return response.response  # type: ignore[union-attr]

        return await self._with_retry(_call)

    async def stream_chat(
        self,
        messages: list[dict[str, str]],
        model: Optional[str] = None,
        temperature: float = 0.7,
    ) -> AsyncIterator[str]:
        """Stream une réponse chat, retourne les chunks de texte un par un."""
        try:
            stream = await self._client.chat(
                model=model or self.model,
                messages=messages,
                options={"temperature": temperature},
                stream=True,
            )
            async for chunk in stream:  # type: ignore[union-attr]
                if chunk.message and chunk.message.content:
                    yield chunk.message.content
        except (httpx.ConnectError, httpx.TimeoutException, ollama.ResponseError) as exc:
            raise OllamaError(f"Streaming interrompu : {exc}") from exc

    async def is_available(self) -> bool:
        """Vérifie qu'Ollama est joignable."""
        try:
            await self._client.list()
            return True
        except Exception:
            return False

    # -------------------------------------------------------------------------
    # Internal retry logic
    # -------------------------------------------------------------------------

    async def _with_retry(self, coro_fn) -> str:
        """Appelle ``coro_fn()`` avec backoff exponentiel sur erreurs transitoires."""
        delay = _BASE_DELAY
        last_exc: Optional[Exception] = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                return await coro_fn()
            except (httpx.ConnectError, httpx.TimeoutException, ollama.ResponseError) as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    break
                logger.warning(
                    "Ollama tentative %d/%d échouée : %s — retry dans %.1fs",
                    attempt,
                    _MAX_RETRIES,
                    exc,
                    delay,
                )
                await asyncio.sleep(delay)
                delay *= 2

        raise OllamaError(
            f"Ollama injoignable après {_MAX_RETRIES} tentatives : {last_exc}"
        ) from last_exc
