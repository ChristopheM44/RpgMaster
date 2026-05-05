"""Helpers for fire-and-forget asyncio tasks."""
from __future__ import annotations

import asyncio
import logging
from collections.abc import Coroutine
from typing import Any

logger = logging.getLogger(__name__)


def create_logged_task(coro: Coroutine[Any, Any, Any], name: str) -> asyncio.Task[Any]:
    """Create a background task and log any unhandled exception."""
    task = asyncio.create_task(coro, name=name)

    def _log_result(done: asyncio.Task[Any]) -> None:
        if done.cancelled():
            return
        try:
            done.result()
        except Exception:
            logger.exception("Background task failed: %s", name)

    task.add_done_callback(_log_result)
    return task
