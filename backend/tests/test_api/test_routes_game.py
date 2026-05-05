from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_create_save_requires_name_schema(async_client) -> None:
    session_resp = await async_client.post("/api/sessions/", json={"name": "Save Test"})
    session_id = session_resp.json()["id"]

    response = await async_client.post(f"/api/game/{session_id}/saves", json={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_save_rejects_blank_name(async_client) -> None:
    session_resp = await async_client.post("/api/sessions/", json={"name": "Save Test"})
    session_id = session_resp.json()["id"]

    response = await async_client.post(f"/api/game/{session_id}/saves", json={"name": " "})

    assert response.status_code == 422
