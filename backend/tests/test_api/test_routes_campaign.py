from __future__ import annotations

import pytest
from sqlalchemy import delete

from app.models.session import Session

BASE_CHARACTER = {
    "species": "human",
    "char_class": "fighter",
    "ability_scores": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 13, "cha": 8},
    "hp_current": 12,
    "hp_max": 12,
}


@pytest.mark.asyncio
async def test_campaign_counts_characters_added_after_session_creation(async_client):
    campaign_resp = await async_client.post(
        "/api/campaigns",
        json={"name": "Chroniques des Brumes", "description": ""},
    )
    assert campaign_resp.status_code == 201
    campaign_id = campaign_resp.json()["id"]

    advance_resp = await async_client.post(
        f"/api/campaigns/{campaign_id}/advance",
        json={"new_session_name": "Session 1"},
    )
    assert advance_resp.status_code == 200
    session_id = advance_resp.json()["new_session_id"]

    for name in ("Mira", "Orin"):
        char_resp = await async_client.post(
            "/api/characters/",
            json={**BASE_CHARACTER, "name": name, "session_id": session_id},
        )
        assert char_resp.status_code == 201

    detail_resp = await async_client.get(f"/api/campaigns/{campaign_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["counts"]["characters"] == 2

    list_resp = await async_client.get("/api/campaigns")
    assert list_resp.status_code == 200
    campaigns = list_resp.json()
    listed = next(c for c in campaigns if c["id"] == campaign_id)
    assert listed["counts"]["characters"] == 2


@pytest.mark.asyncio
async def test_get_campaign_prunes_stale_session_ids(async_client, db_session):
    campaign_resp = await async_client.post(
        "/api/campaigns",
        json={"name": "Vestiges", "description": ""},
    )
    assert campaign_resp.status_code == 201
    campaign_id = campaign_resp.json()["id"]

    first_session = await async_client.post(
        f"/api/campaigns/{campaign_id}/advance",
        json={"new_session_name": "Session 1"},
    )
    assert first_session.status_code == 200

    second_session = await async_client.post(
        f"/api/campaigns/{campaign_id}/advance",
        json={"new_session_name": "Session 2"},
    )
    assert second_session.status_code == 200
    deleted_session_id = first_session.json()["new_session_id"]
    surviving_session_id = second_session.json()["new_session_id"]

    await db_session.execute(delete(Session).where(Session.id == deleted_session_id))
    await db_session.commit()

    detail_resp = await async_client.get(f"/api/campaigns/{campaign_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["session_ids"] == [surviving_session_id]
    assert detail["current_session_index"] == 0
    assert detail["counts"]["sessions"] == 1

    list_resp = await async_client.get("/api/campaigns")
    assert list_resp.status_code == 200
    listed = next(c for c in list_resp.json() if c["id"] == campaign_id)
    assert listed["session_ids"] == [surviving_session_id]
    assert listed["current_session_index"] == 0
