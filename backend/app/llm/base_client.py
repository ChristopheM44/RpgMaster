from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class LLMClient(Protocol):
    """Interface commune à tous les clients LLM (Ollama, OpenAI-compatible…).

    Toute classe implémentant ces quatre méthodes satisfait ce Protocol
    structurellement — aucun héritage explicite requis.
    """

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str: ...

    async def generate(
        self,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str: ...

    async def stream_chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
    ) -> AsyncIterator[str]: ...

    async def is_available(self) -> bool: ...
