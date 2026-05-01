from __future__ import annotations

import logging

from app.config import (
    get_gm_model,
    get_llm_provider,
    get_ollama_url,
    get_openai_api_key,
    get_openai_base_url,
    get_player_model,
)
from app.llm.base_client import LLMClient

logger = logging.getLogger(__name__)


class ModelRouter:
    """Fabrique les clients LLM appropriés selon le provider actif.

    Point d'extension : ajouter un nouveau provider dans _make_client()
    sans toucher aux agents.
    """

    def get_gm_client(self) -> LLMClient:
        return self._make_client(model=get_gm_model())

    def get_player_client(self) -> LLMClient:
        return self._make_client(model=get_player_model())

    def _make_client(self, model: str) -> LLMClient:
        provider = get_llm_provider()
        if provider == "openai_compatible":
            from app.llm.openai_compatible_client import OpenAICompatibleClient

            base_url = get_openai_base_url()
            logger.info(
                "LLM client: provider=openai_compatible model=%s base_url=%s api_key_set=%s",
                model,
                base_url or "(empty!)",
                bool(get_openai_api_key()),
            )
            return OpenAICompatibleClient(
                base_url=base_url,
                api_key=get_openai_api_key(),
                model=model,
            )
        from app.llm.ollama_client import OllamaClient

        logger.info(
            "LLM client: provider=ollama model=%s base_url=%s",
            model,
            get_ollama_url(),
        )
        return OllamaClient(model=model)


# Singleton module-level — réutilisé par les agents
router = ModelRouter()
