from __future__ import annotations

from app.config import settings
from app.llm.ollama_client import OllamaClient


class ModelRouter:
    """Fabrique les clients LLM appropriés selon le rôle (MJ, joueur, etc.).

    Point d'extension pour ajouter d'autres backends (vLLM, OpenAI-compat…)
    sans toucher aux agents.
    """

    def get_gm_client(self) -> OllamaClient:
        """Retourne un client Ollama configuré pour le modèle MJ."""
        return OllamaClient(model=settings.gm_model)

    def get_player_client(self) -> OllamaClient:
        """Retourne un client Ollama configuré pour les agents joueurs IA."""
        return OllamaClient(model=settings.player_model)


# Singleton module-level — réutilisé par les agents
router = ModelRouter()
