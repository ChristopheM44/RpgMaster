from __future__ import annotations

from collections import deque
from typing import Any, Optional

from app.agents.schemas import ContextMessage
from app.config import settings


class ContextManager:
    """Gère la fenêtre glissante de contexte pour les agents LLM.

    Conserve les N derniers messages. Quand la fenêtre est pleine, les messages
    les plus anciens sont automatiquement évincés (``deque(maxlen=…)``).
    """

    def __init__(self, max_messages: Optional[int] = None):
        self._max = max_messages or settings.max_context_messages
        self._window: deque[ContextMessage] = deque(maxlen=self._max)

    # -------------------------------------------------------------------------
    # Ajout de messages
    # -------------------------------------------------------------------------

    def add_message(
        self,
        role: str,
        speaker: str,
        content: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> None:
        """Ajoute un message à la fenêtre de contexte."""
        self._window.append(
            ContextMessage(
                role=role,
                speaker=speaker,
                content=content,
                metadata=metadata or {},
            )
        )

    # -------------------------------------------------------------------------
    # Lecture du contexte
    # -------------------------------------------------------------------------

    def get_messages(self, last_n: Optional[int] = None) -> list[ContextMessage]:
        """Retourne les messages de la fenêtre (tous, ou seulement les N derniers)."""
        messages = list(self._window)
        if last_n is not None:
            return messages[-last_n:]
        return messages

    def to_ollama_messages(
        self,
        system_prompt: str,
        last_n: Optional[int] = None,
    ) -> list[dict[str, str]]:
        """Formate le contexte en liste de messages pour l'API Ollama chat.

        Le rôle ``"player"`` devient ``"user"`` ; tous les autres rôles
        (``"gm"``, ``"system"``) deviennent ``"assistant"``.
        """
        result: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        for msg in self.get_messages(last_n):
            ollama_role = "user" if msg.role == "player" else "assistant"
            result.append(
                {"role": ollama_role, "content": f"[{msg.speaker}] {msg.content}"}
            )
        return result

    # -------------------------------------------------------------------------
    # Gestion
    # -------------------------------------------------------------------------

    def clear(self) -> None:
        """Vide la fenêtre de contexte."""
        self._window.clear()

    @property
    def size(self) -> int:
        """Nombre de messages actuellement dans la fenêtre."""
        return len(self._window)

    @property
    def is_full(self) -> bool:
        """True si la fenêtre a atteint sa capacité maximale."""
        return len(self._window) == self._max
