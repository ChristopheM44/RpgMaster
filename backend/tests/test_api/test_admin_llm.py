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
async def test_llm_settings_include_and_update_source_max_chars(
    async_client,
    monkeypatch,
) -> None:
    monkeypatch.setattr(config, "_runtime_llm", {}, raising=False)
    monkeypatch.setattr(config, "_save_runtime_llm", lambda: None, raising=False)
    monkeypatch.setattr(settings, "source_max_chars", 120_000)

    current = await async_client.get("/api/admin/llm/settings")
    assert current.status_code == 200
    assert current.json()["source_max_chars"] == 120_000

    updated = await async_client.put(
        "/api/admin/llm/settings",
        json={"source_max_chars": 800_000},
    )

    assert updated.status_code == 200
    assert updated.json()["source_max_chars"] == 800_000
    assert config._runtime_llm["source_max_chars"] == 800_000


@pytest.mark.asyncio
async def test_llm_settings_reject_invalid_source_max_chars(async_client) -> None:
    response = await async_client.put(
        "/api/admin/llm/settings",
        json={"source_max_chars": 999},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_llm_model_info_uses_ollama_show_and_extracts_characteristics(
    async_client,
    monkeypatch,
) -> None:
    captured: dict[str, object] = {}

    class DummyResponse:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> dict[str, object]:
            return {
                "details": {
                    "family": "gemma3",
                    "families": ["gemma3"],
                    "parameter_size": "31B",
                    "quantization_level": "Q4_K_M",
                    "format": "gguf",
                },
                "model_info": {"gemma3.context_length": 262_144},
                "parameters": "temperature 0.7\nnum_ctx 262144",
            }

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def post(self, url: str, json: dict[str, object]) -> DummyResponse:
            captured["url"] = url
            captured["json"] = json
            return DummyResponse()

    monkeypatch.setattr(
        config,
        "_runtime_llm",
        {
            "ollama_base_url": "http://localhost:11434",
            "ollama_api_key": "secret-key",
        },
        raising=False,
    )
    monkeypatch.setattr(routes_admin.httpx, "AsyncClient", DummyAsyncClient)

    response = await async_client.get("/api/admin/llm/model-info?model=gemma4:31b")

    assert response.status_code == 200
    assert captured["url"] == "http://localhost:11434/api/show"
    assert captured["json"] == {"model": "gemma4:31b"}
    assert captured["kwargs"] == {
        "timeout": 5.0,
        "headers": {"Authorization": "Bearer secret-key"},
    }
    assert response.json() == {
        "model": "gemma4:31b",
        "family": "gemma3",
        "families": ["gemma3"],
        "parameter_size": "31B",
        "quantization_level": "Q4_K_M",
        "format": "gguf",
        "context_length": 262_144,
        "num_ctx": 262_144,
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
