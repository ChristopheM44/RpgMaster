from __future__ import annotations

from app.config import (
    get_gm_model,
    get_llm_provider,
    get_openai_api_key,
    get_openai_base_url,
    get_player_model,
)
from app.llm.base_client import LLMClient


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

            return OpenAICompatibleClient(
                base_url=get_openai_base_url(),
                api_key=get_openai_api_key(),
                model=model,
            )
        from app.llm.ollama_client import OllamaClient

        return OllamaClient(model=model)


# Singleton module-level — réutilisé par les agents
router = ModelRouter()
