"""Async client for image generation via OpenAI-compatible API (DALL-E, etc.)."""
from __future__ import annotations

import logging

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.config import (
    get_image_api_key,
    get_image_base_url,
    get_image_model,
    get_image_size,
)
from app.llm.retry import with_llm_retry

logger = logging.getLogger(__name__)

_MAX_RETRIES = 2
_BASE_DELAY = 2.0
_IMAGE_TIMEOUT = 180.0


class ImageClientError(Exception):
    """The image generation provider is unreachable or returned an error."""


def _image_retry_error(
    exc: BaseException | None, max_retries: int
) -> ImageClientError:
    return ImageClientError(
        f"Image provider injoignable après {max_retries} tentatives : {exc}"
    )


class ImageClient:
    """Client async pour la génération d'images via API OpenAI-compatible.

    Compatible : OpenAI DALL-E, Stable Diffusion WebUI, ComfyUI, etc.
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        size: str | None = None,
    ):
        self._explicit_base_url = base_url
        self._explicit_api_key = api_key
        self._explicit_model = model
        self._explicit_size = size
        self._cached_base_url: str | None = None
        self._cached_api_key: str | None = None
        self._client: AsyncOpenAI | None = None

    @property
    def _base_url(self) -> str:
        return self._explicit_base_url or get_image_base_url()

    @property
    def _api_key(self) -> str:
        return self._explicit_api_key or get_image_api_key()

    @property
    def _model(self) -> str:
        return self._explicit_model or get_image_model()

    @property
    def _size(self) -> str:
        return self._explicit_size or get_image_size()

    def _get_client(self) -> AsyncOpenAI:
        current_url = self._base_url
        current_key = self._api_key
        if (
            self._client is None
            or self._cached_base_url != current_url
            or self._cached_api_key != current_key
        ):
            self._client = AsyncOpenAI(
                base_url=current_url or None,
                api_key=current_key or "no-key",
                timeout=_IMAGE_TIMEOUT,
            )
            self._cached_base_url = current_url
            self._cached_api_key = current_key
        return self._client

    @with_llm_retry(
        retry_exceptions=(APIConnectionError, APITimeoutError),
        error_factory=_image_retry_error,
        provider_name="Image",
        max_retries=_MAX_RETRIES,
        base_delay=_BASE_DELAY,
        log=logger,
    )
    async def _generate_with_retry(self, prompt: str, size: str, model: str) -> str:
        response = await self._get_client().images.generate(
            model=model,
            prompt=prompt,
            size=size,
            n=1,
            response_format="url",
        )
        url = response.data[0].url
        if not url:
            raise ImageClientError("L'API n'a pas retourné d'URL d'image")
        return url

    async def generate(self, prompt: str) -> str:
        """Generate an image from a prompt and return the image URL."""
        try:
            return await self._generate_with_retry(
                prompt, self._size, self._model
            )
        except APIStatusError as exc:
            # Detect non-API responses (e.g. Ollama HTML homepage on 404)
            body = getattr(exc, "response", None)
            content_type = ""
            if body is not None:
                ct = getattr(body, "headers", {})
                content_type = ct.get("content-type", "") if isinstance(ct, dict) else ""
            if exc.status_code == 404 or "text/html" in content_type:
                raise ImageClientError(
                    "Le serveur ne supporte pas la génération d'images. "
                    "Vérifiez que l'URL pointe vers un service compatible OpenAI "
                    "(DALL-E, Stable Diffusion WebUI, etc.), pas un serveur LLM texte."
                ) from exc
            raise ImageClientError(
                f"Erreur API image {exc.status_code} : {exc.message}"
            ) from exc

    async def is_available(self) -> bool:
        try:
            await self._get_client().models.list()
            return True
        except APIStatusError:
            return True
        except Exception:
            return False