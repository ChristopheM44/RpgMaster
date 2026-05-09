from __future__ import annotations

import pytest

from app import config
from app.api import routes_admin
from app.config import settings


@pytest.fixture(autouse=True)
def reset_admin_rate_limiter():
    routes_admin.llm_ping_limiter.reset()
    yield
    routes_admin.llm_ping_limiter.reset()


@pytest.mark.asyncio
async def test_llm_health_uses_auth_header_and_normalized_url(
    async_client,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {"models": [{"name": "deepseek-v4-flash"}]}

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str) -> DummyResponse:
            captured["url"] = url
            return DummyResponse()

    monkeypatch.setattr(
        config,
        "_runtime_llm",
        {
            "ollama_base_url": " https://ollama.com/api/ ",
            "ollama_api_key": "  secret-key  ",
            "gm_model": "deepseek-v4-flash",
            "player_model": "deepseek-v4-flash",
        },
        raising=False,
    )
    monkeypatch.setattr(routes_admin.httpx, "AsyncClient", DummyAsyncClient)

    response = await async_client.get("/api/admin/llm/health")

    assert response.status_code == 200
    assert response.json()["available"] is True
    assert response.json()["models"] == ["deepseek-v4-flash"]
    assert captured["url"] == "https://ollama.com/api/tags"
    assert captured["kwargs"] == {
        "timeout": 5.0,
        "headers": {"Authorization": "Bearer secret-key"},
    }


@pytest.mark.asyncio
async def test_llm_ping_is_rate_limited_by_ip(async_client, monkeypatch) -> None:
    class DummyClient:
        async def chat(self, **kwargs) -> str:
            return "pong"

    monkeypatch.setattr(routes_admin.llm_router, "get_player_client", lambda: DummyClient())

    for _ in range(5):
        response = await async_client.post(
            "/api/admin/llm/ping",
            headers={"x-forwarded-for": "203.0.113.10"},
        )
        assert response.status_code == 200

    limited = await async_client.post(
        "/api/admin/llm/ping",
        headers={"x-forwarded-for": "203.0.113.10"},
    )

    assert limited.status_code == 429
    assert limited.headers["retry-after"]


@pytest.mark.asyncio
async def test_llm_ping_rate_limit_isolated_by_ip(async_client, monkeypatch) -> None:
    class DummyClient:
        async def chat(self, **kwargs) -> str:
            return "pong"

    monkeypatch.setattr(routes_admin.llm_router, "get_player_client", lambda: DummyClient())

    for _ in range(5):
        await async_client.post(
            "/api/admin/llm/ping",
            headers={"x-forwarded-for": "203.0.113.11"},
        )

    response = await async_client.post(
        "/api/admin/llm/ping",
        headers={"x-forwarded-for": "203.0.113.12"},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_admin_routes_use_global_token_when_admin_token_unset(
    async_client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_access_token", "app-token")
    monkeypatch.setattr(settings, "admin_access_token", "")

    denied = await async_client.get("/api/admin/llm/settings")
    allowed = await async_client.get(
        "/api/admin/llm/settings",
        headers={"Authorization": "Bearer app-token"},
    )

    assert denied.status_code == 401
    assert allowed.status_code == 200


@pytest.mark.asyncio
async def test_admin_routes_require_admin_token_when_configured(
    async_client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(settings, "app_access_token", "app-token")
    monkeypatch.setattr(settings, "admin_access_token", "admin-token")

    denied_without_token = await async_client.get("/api/admin/llm/settings")
    denied_with_app_token = await async_client.get(
        "/api/admin/llm/settings",
        headers={"Authorization": "Bearer app-token"},
    )
    allowed = await async_client.get(
        "/api/admin/llm/settings",
        headers={"Authorization": "Bearer admin-token"},
    )

    assert denied_without_token.status_code == 401
    assert denied_with_app_token.status_code == 401
    assert allowed.status_code == 200
