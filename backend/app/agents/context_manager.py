from __future__ import annotations

from collections import deque
from typing import Any

from app.agents.schemas import ContextMessage
from app.config import settings

_SUMMARY_LINE_MAX_CHARS = 160
_SUMMARY_MAX_LINES = 12


class ContextManager:
    """Gère la fenêtre glissante de contexte pour les agents LLM.

    Conserve les N derniers messages. Quand la fenêtre est pleine, le message
    le plus ancien est condensé dans un résumé court (``summarize_old_messages``)
    avant d'être évincé (``deque(maxlen=…)``), au lieu d'être simplement perdu.
    """

    def __init__(self, max_messages: int | None = None):
        self._max = max_messages or settings.max_context_messages
        self._window: deque[ContextMessage] = deque(maxlen=self._max)
        self._summary_lines: deque[str] = deque(maxlen=_SUMMARY_MAX_LINES)

    # -------------------------------------------------------------------------
    # Ajout de messages
    # -------------------------------------------------------------------------

    def add_message(
        self,
        role: str,
        speaker: str,
        content: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """Ajoute un message à la fenêtre de contexte.

        Si la fenêtre est pleine, le message le plus ancien est condensé dans
        le résumé (cf. ``summarize_old_messages``) avant d'être évincé.
        """
        if len(self._window) == self._max:
            self._summary_lines.append(self._condense(self._window[0]))
        self._window.append(
            ContextMessage(
                role=role,
                speaker=speaker,
                content=content,
                metadata=metadata or {},
            )
        )

    @staticmethod
    def _condense(message: ContextMessage) -> str:
        """Condense un message évincé en une ligne courte pour le résumé."""
        content = " ".join(message.content.split())
        if len(content) > _SUMMARY_LINE_MAX_CHARS:
            content = content[: _SUMMARY_LINE_MAX_CHARS - 1].rstrip() + "…"
        return f"[{message.speaker}] {content}"

    # -------------------------------------------------------------------------
    # Lecture du contexte
    # -------------------------------------------------------------------------

    def get_messages(self, last_n: int | None = None) -> list[ContextMessage]:
        """Retourne les messages de la fenêtre (tous, ou seulement les N derniers)."""
        messages = list(self._window)
        if last_n is not None:
            return messages[-last_n:]
        return messages

    def summarize_old_messages(self) -> str:
        """Retourne le résumé condensé des messages évincés de la fenêtre.

        Chaîne vide si aucun message n'a encore été évincé. Limité aux
        ``_SUMMARY_MAX_LINES`` évictions les plus récentes.
        """
        return "\n".join(self._summary_lines)

    def to_ollama_messages(
        self,
        system_prompt: str,
        last_n: int | None = None,
    ) -> list[dict[str, str]]:
        """Formate le contexte en liste de messages pour l'API Ollama chat.

        Le rôle ``"player"`` devient ``"user"`` ; tous les autres rôles
        (``"gm"``, ``"system"``) deviennent ``"assistant"``. Si des messages
        ont été évincés de la fenêtre, un résumé condensé est inséré juste
        après le system prompt.
        """
        result: list[dict[str, str]] = [{"role": "system", "content": system_prompt}]
        summary = self.summarize_old_messages()
        if summary:
            result.append(
                {
                    "role": "system",
                    "content": (
                        f"Résumé des échanges précédents (hors fenêtre récente) :\n{summary}"
                    ),
                }
            )
        for msg in self.get_messages(last_n):
            ollama_role = "user" if msg.role == "player" else "assistant"
            result.append({"role": ollama_role, "content": f"[{msg.speaker}] {msg.content}"})
        return result

    # -------------------------------------------------------------------------
    # Gestion
    # -------------------------------------------------------------------------

    def clear(self) -> None:
        """Vide la fenêtre de contexte et le résumé."""
        self._window.clear()
        self._summary_lines.clear()

    @property
    def size(self) -> int:
        """Nombre de messages actuellement dans la fenêtre."""
        return len(self._window)

    @property
    def is_full(self) -> bool:
        """True si la fenêtre a atteint sa capacité maximale."""
        return len(self._window) == self._max
