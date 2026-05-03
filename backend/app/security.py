from __future__ import annotations

from typing import Optional

from fastapi import Request, WebSocket

from app.config import settings


def _configured_token() -> str:
    return settings.app_access_token.strip()


def _bearer_value(value: Optional[str]) -> str:
    if not value:
        return ""
    prefix = "Bearer "
    if value.startswith(prefix):
        return value[len(prefix):].strip()
    return value.strip()


def access_token_required() -> bool:
    return bool(_configured_token())


def is_valid_access_token(token: Optional[str]) -> bool:
    expected = _configured_token()
    if not expected:
        return True
    return _bearer_value(token) == expected


def request_has_valid_access_token(request: Request) -> bool:
    token = request.headers.get("authorization") or request.headers.get("x-rpgmaster-token")
    return is_valid_access_token(token)


def websocket_has_valid_access_token(websocket: WebSocket) -> bool:
    token = (
        websocket.query_params.get("access_token")
        or websocket.headers.get("authorization")
        or websocket.headers.get("x-rpgmaster-token")
    )
    return is_valid_access_token(token)
