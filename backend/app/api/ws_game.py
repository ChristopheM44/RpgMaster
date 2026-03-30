"""WebSocket endpoint for real-time game communication.

Protocol summary
----------------

Client → Server (JSON):

    {"type": "join",   "character_id": "<id>"}
    {"type": "action", "action_type": "free_text|attack|cast_spell|use_item|move|end_turn",
                       "content": "Je cherche des pièges",
                       "target_id": "<id|null>"}
    {"type": "ping"}

Server → Client (JSON):

    {"event_type": "session_state", "session_id": "...", "payload": {...}, "timestamp": "..."}
    {"event_type": "narration",     "session_id": "...", "payload": {"text": "..."}, ...}
    {"event_type": "roll_result",   "session_id": "...", "payload": {...}, ...}
    {"event_type": "turn_start",    "session_id": "...", "payload": {"combatant_id": "..."}, ...}
    {"event_type": "phase_change",  "session_id": "...", "payload": {"phase": "..."}, ...}
    {"event_type": "error",         "session_id": "...", "payload": {"message": "..."}, ...}
    {"event_type": "pong"}

Connection lifecycle
--------------------
1. Client connects: session is opened/loaded from DB, client receives ``session_state``.
2. Client sends ``join`` with its character_id → ``player_joined`` broadcast.
3. Client sends ``action`` messages → dispatched to the game layer → results broadcast.
4. Client disconnects: ``player_left`` broadcast, session closed if no more clients.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, Optional, Set

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.game.action_resolver import ActionResolver
from app.game.event_bus import EventType, GameEvent, event_bus
from app.game.session_manager import SessionManager
from app.models.session import SessionStatus

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Module-level session manager (shared across all WS connections)
# ---------------------------------------------------------------------------

session_manager = SessionManager()
action_resolver = ActionResolver()

# ---------------------------------------------------------------------------
# Incoming message schemas
# ---------------------------------------------------------------------------


class JoinMessage(BaseModel):
    type: str  # "join"
    character_id: str


class PlayerActionMessage(BaseModel):
    type: str  # "action"
    action_type: str  # free_text | attack | cast_spell | use_item | move | end_turn
    content: Optional[str] = None
    target_id: Optional[str] = None
    character_id: Optional[str] = None


class PingMessage(BaseModel):
    type: str  # "ping"


# ---------------------------------------------------------------------------
# Connection manager
# ---------------------------------------------------------------------------


class ConnectionManager:
    """Tracks all active WebSocket connections grouped by session.

    Provides broadcast helpers used both by the relay task and by
    game-layer code that wants to push events directly.
    """

    def __init__(self) -> None:
        # session_id -> set of connected websockets
        self._connections: Dict[str, Set[WebSocket]] = {}

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

    async def broadcast(self, session_id: str, data: Dict[str, Any]) -> None:
        """Send *data* to all WebSocket clients connected to *session_id*."""
        dead: Set[WebSocket] = set()
        for ws in list(self._connections.get(session_id, set())):
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
        for ws in dead:
            self.disconnect(session_id, ws)

    async def send_to(self, websocket: WebSocket, data: Dict[str, Any]) -> None:
        """Send *data* to a single WebSocket client."""
        try:
            await websocket.send_json(data)
        except Exception as exc:
            logger.warning("Failed to send to WS client: %s", exc)


# Module-level singleton
connection_manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Relay task
# ---------------------------------------------------------------------------


async def _relay_events(websocket: WebSocket, queue: asyncio.Queue) -> None:
    """Background coroutine: forward events from *queue* to *websocket*.

    Runs as a sibling task alongside the receive loop.  Exits when cancelled
    or when the WebSocket closes.
    """
    try:
        while True:
            event: GameEvent = await queue.get()
            payload = event.model_dump(mode="json")
            await websocket.send_json(payload)
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        logger.debug("Relay task ended: %s", exc)


# ---------------------------------------------------------------------------
# Action dispatcher
# ---------------------------------------------------------------------------


async def _dispatch_action(
    session_id: str,
    action: PlayerActionMessage,
    db: AsyncSession,
) -> None:
    """Process a player action through the full pipeline and broadcast results.

    Pipeline : engine resolution → GM narration → event bus → WebSocket clients.
    """
    active = session_manager.get_session(session_id)
    if active is None:
        await event_bus.publish_to_session(
            session_id,
            EventType.ERROR,
            {"message": f"Session '{session_id}' is not active."},
            source="ws_game",
        )
        return

    # Full pipeline: engine → GM agent → events
    await action_resolver.resolve(
        session_id=session_id,
        action_type=action.action_type,
        content=action.content,
        character_id=action.character_id,
        target_id=action.target_id,
        active=active,
    )

    # Advance turn counter and notify clients
    active.turn_number += 1
    active.mark_dirty()

    await event_bus.publish_to_session(
        session_id,
        EventType.TURN_END,
        {"turn_number": active.turn_number},
        source="ws_game",
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_session_state_payload(session_id: str) -> Dict[str, Any]:
    """Build the ``session_state`` event payload from the active session."""
    active = session_manager.get_session(session_id)
    if active is None:
        return {"session_id": session_id, "phase": "unknown"}
    turn_data = active.turn_manager.to_dict()
    return {
        "session_id": session_id,
        "phase": active.phase.value,
        "turn_number": active.turn_number,
        "round_number": active.round_number,
        "turn_order": turn_data.get("order", []),
        "current_turn_index": turn_data.get("index", 0),
        "valid_transitions": [
            s.value for s in active.game_loop.get_valid_transitions(active.phase)
        ],
    }


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------


@router.websocket("/ws/game/{session_id}")
async def game_websocket(
    websocket: WebSocket,
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Main WebSocket endpoint for real-time game communication."""
    await websocket.accept()

    # ------------------------------------------------------------------
    # 1. Open / load session
    # ------------------------------------------------------------------
    try:
        await session_manager.open_session(session_id, db)
    except KeyError:
        await websocket.send_json({
            "event_type": EventType.ERROR,
            "session_id": session_id,
            "payload": {"message": f"Session '{session_id}' not found."},
        })
        await websocket.close(code=4404)
        return

    # ------------------------------------------------------------------
    # 2. Register connection and subscribe to event bus
    # ------------------------------------------------------------------
    connection_manager.connect(session_id, websocket)
    queue = event_bus.subscribe(session_id)

    # Start relay task (event bus → this websocket)
    relay_task = asyncio.create_task(_relay_events(websocket, queue))

    # ------------------------------------------------------------------
    # 3. Send initial session state
    # ------------------------------------------------------------------
    await websocket.send_json({
        "event_type": EventType.SESSION_STATE,
        "session_id": session_id,
        "payload": _build_session_state_payload(session_id),
    })

    character_id: Optional[str] = None

    try:
        # ----------------------------------------------------------------
        # 4. Receive loop
        # ----------------------------------------------------------------
        while True:
            try:
                raw = await websocket.receive_json()
            except Exception:
                break  # client disconnected mid-message

            msg_type = raw.get("type", "")

            # --- ping ---------------------------------------------------
            if msg_type == "ping":
                await websocket.send_json({"event_type": "pong"})
                continue

            # --- join ---------------------------------------------------
            if msg_type == "join":
                try:
                    join = JoinMessage(**raw)
                except ValidationError as exc:
                    await websocket.send_json({
                        "event_type": EventType.ERROR,
                        "session_id": session_id,
                        "payload": {"message": str(exc)},
                    })
                    continue

                character_id = join.character_id
                await event_bus.publish_to_session(
                    session_id,
                    EventType.PLAYER_JOINED,
                    {"character_id": character_id},
                    source="ws_game",
                )
                logger.info("Player joined session %s with character %s.", session_id, character_id)
                continue

            # --- action -------------------------------------------------
            if msg_type == "action":
                try:
                    action = PlayerActionMessage(**raw)
                except ValidationError as exc:
                    await websocket.send_json({
                        "event_type": EventType.ERROR,
                        "session_id": session_id,
                        "payload": {"message": str(exc)},
                    })
                    continue

                await _dispatch_action(session_id, action, db)
                continue

            # --- unknown type -------------------------------------------
            await websocket.send_json({
                "event_type": EventType.ERROR,
                "session_id": session_id,
                "payload": {"message": f"Unknown message type: '{msg_type}'."},
            })

    except WebSocketDisconnect:
        pass
    finally:
        # ----------------------------------------------------------------
        # 5. Cleanup
        # ----------------------------------------------------------------
        relay_task.cancel()
        await asyncio.gather(relay_task, return_exceptions=True)

        event_bus.unsubscribe(session_id, queue)
        connection_manager.disconnect(session_id, websocket)

        if character_id:
            await event_bus.publish_to_session(
                session_id,
                EventType.PLAYER_LEFT,
                {"character_id": character_id},
                source="ws_game",
            )

        # Close session only when last client disconnects
        if connection_manager.connection_count(session_id) == 0:
            try:
                await session_manager.close_session(session_id, db)
            except Exception as exc:
                logger.warning("Error closing session %s on last disconnect: %s", session_id, exc)

        logger.info("WS closed: session=%s character=%s", session_id, character_id)
