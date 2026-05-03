from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Tracks active WebSocket connections grouped by session."""

    def __init__(self) -> None:
        self._connections: dict[str, set[WebSocket]] = {}

    def connect(self, session_id: str, websocket: WebSocket) -> None:
        self._connections.setdefault(session_id, set()).add(websocket)
        logger.debug(
            "WS connected: session=%s total=%d",
            session_id,
            len(self._connections[session_id]),
        )

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        connections = self._connections.get(session_id, set())
        connections.discard(websocket)
        if not connections:
            self._connections.pop(session_id, None)
        logger.debug("WS disconnected: session=%s", session_id)

    def connection_count(self, session_id: str) -> int:
        return len(self._connections.get(session_id, set()))

    async def broadcast(self, session_id: str, data: dict[str, Any]) -> None:
        dead: set[WebSocket] = set()
        for ws in list(self._connections.get(session_id, set())):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    async def send_to(self, websocket: WebSocket, data: dict[str, Any]) -> None:
        try:
            await websocket.send_json(data)
        except Exception as exc:
            logger.warning("Failed to send to WS client: %s", exc)
