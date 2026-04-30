from __future__ import annotations

import pytest

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
