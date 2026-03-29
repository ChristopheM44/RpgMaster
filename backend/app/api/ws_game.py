from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/game/{session_id}")
async def game_websocket(websocket: WebSocket, session_id: str):
    """WebSocket endpoint for real-time game communication."""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            # Echo back for now - will be replaced by game loop
            await websocket.send_json({
                "event_type": "echo",
                "payload": data,
                "session_id": session_id,
            })
    except WebSocketDisconnect:
        pass
