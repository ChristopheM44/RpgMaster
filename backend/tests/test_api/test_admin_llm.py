from __future__ import annotations

import pytest

from app import config
from app.api import routes_admin


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
