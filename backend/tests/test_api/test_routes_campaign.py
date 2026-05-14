from __future__ import annotations

import pytest
from sqlalchemy import delete, select

from app.models.campaign import Campaign
from app.models.campaign_dossier import CampaignDossier
from app.models.character import Character
from app.models.game_state import GameState
from app.models.message import Message, MessageRole, MessageType
from app.models.save_slot import SaveSlot
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


@pytest.mark.asyncio
async def test_reset_campaign_keeps_current_session_and_clears_played_state(
    async_client,
    db_session,
):
    campaign_resp = await async_client.post(
        "/api/campaigns",
        json={"name": "Brumes rejouables", "description": "Campagne test"},
    )
    assert campaign_resp.status_code == 201
    campaign_id = campaign_resp.json()["id"]

    result = await db_session.execute(select(Campaign).where(Campaign.id == campaign_id))
    campaign = result.scalar_one()
    campaign.starting_level = 2
    await db_session.commit()

    first_resp = await async_client.post(
        f"/api/campaigns/{campaign_id}/advance",
        json={"new_session_name": "Session 1"},
    )
    assert first_resp.status_code == 200
    first_session_id = first_resp.json()["new_session_id"]

    char_resp = await async_client.post(
        "/api/characters/",
        json={
            "name": "Elora",
            "species": "human",
            "char_class": "wizard",
            "level": 4,
            "ability_scores": {
                "str": 8,
                "dex": 14,
                "con": 14,
                "int": 17,
                "wis": 10,
                "cha": 10,
            },
            "hp_current": 9,
            "hp_max": 30,
            "xp": 2700,
            "gp": 25,
            "sp": 4,
            "cp": 2,
            "spell_slots": {"1": {"total": 4, "used": 3}, "2": {"total": 3, "used": 2}},
            "hit_dice": {"die": 6, "total": 4, "used": 3},
            "known_spells": ["magic_missile"],
            "conditions": ["poisoned"],
            "personality": {"trait": "curious", "pending_asi": True, "pending_asi_levels": [4]},
            "session_id": first_session_id,
        },
    )
    assert char_resp.status_code == 201

    second_resp = await async_client.post(
        f"/api/campaigns/{campaign_id}/advance",
        json={"new_session_name": "Session 2"},
    )
    assert second_resp.status_code == 200
    current_session_id = second_resp.json()["new_session_id"]

    chars_result = await db_session.execute(
        select(Character).where(Character.session_id == current_session_id)
    )
    current_char = chars_result.scalar_one()
    current_char.xp = 5000
    current_char.gp = 99
    current_char.sp = 8
    current_char.cp = 7
    current_char.hp_current = 1
    current_char.conditions = ["frightened"]
    current_char.spell_slots = {"1": {"total": 4, "used": 4}, "2": {"total": 3, "used": 3}}
    current_char.hit_dice = {"die": 6, "total": 4, "used": 4}
    current_char.personality = {
        **dict(current_char.personality or {}),
        "pending_asi": True,
        "pending_asi_levels": [4],
    }

    db_session.add_all([
        GameState(
            session_id=current_session_id,
            turn_number=9,
            round_number=3,
            state_data={
                "phase": "combat",
                "quests": [{"id": "played", "title": "Jouée"}],
                "world_maps": {"region_map": {"id": "played-map"}, "city_maps": {}},
            },
        ),
        Message(
            session_id=current_session_id,
            role=MessageRole.GM,
            speaker="MJ",
            message_type=MessageType.NARRATION,
            content="Un événement joué.",
        ),
        SaveSlot(
            id="save-reset-test",
            session_id=current_session_id,
            name="Avant reset",
            phase="combat",
            turn_number=9,
            round_number=3,
            state_data={"phase": "combat"},
            characters_snapshot=[],
        ),
        CampaignDossier(
            id="dossier-reset-test",
            campaign_id=campaign_id,
            player_contract={
                "title": "Brumes rejouables",
                "pitch_public": "Une route noyée de brume.",
                "tones": ["Mystère"],
                "duration": "3 sessions",
                "hook": "La brume appelle.",
                "visible_chapters": [
                    {
                        "id": "chapter_1",
                        "num": "I",
                        "title": "Route",
                        "state": "done",
                        "sessions": 2,
                        "summary": "La route a été jouée.",
                    },
                    {
                        "id": "chapter_2",
                        "num": "II",
                        "title": "Mine",
                        "state": "active",
                        "sessions": 1,
                        "summary": "La mine attend.",
                    },
                ],
                "known_objectives": ["Comprendre la brume."],
                "played_summary": "Le groupe a déjà tout changé.",
            },
            gm_dossier={
                "narrative_arc": "Secret conservé.",
                "chapters": [],
                "important_npcs": [{"name": "Bram"}],
                "region_map": {"id": "private-map"},
                "city_maps": {"ville": {"id": "ville"}},
                "active_city_id": "ville",
            },
            played_canon={
                "established_facts": ["Fait joué"],
                "player_decisions": ["Décision jouée"],
                "quests": [{"id": "played"}],
                "npc_relationships": [{"id": "bram"}],
                "revealed_secrets": ["Secret révélé"],
                "plan_changes": ["Plan changé"],
                "rolling_summary": "Résumé joué",
                "chapter_progression": [{"id": "chapter_2", "state": "active"}],
            },
            import_sources=[{"id": "source-1", "kind": "text", "title": "Source privée"}],
            active_chapter_id="chapter_2",
            generation_status="validated",
        ),
    ])
    await db_session.commit()

    response = await async_client.post(f"/api/campaigns/{campaign_id}/reset")

    assert response.status_code == 200
    payload = response.json()
    assert payload["session_id"] == current_session_id
    assert payload["characters_reset"] == 1
    assert payload["sessions_removed"] == 1
    assert payload["campaign"]["session_ids"] == [current_session_id]
    assert payload["campaign"]["current_session_index"] == 0
    assert payload["campaign"]["starting_level"] == 2

    db_session.expire_all()

    deleted_session = await db_session.execute(
        select(Session).where(Session.id == first_session_id)
    )
    assert deleted_session.scalar_one_or_none() is None

    session_result = await db_session.execute(
        select(Session).where(Session.id == current_session_id)
    )
    session = session_result.scalar_one()
    assert session.status.value == "lobby"

    assert (
        await db_session.execute(select(Message).where(Message.session_id == current_session_id))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(select(SaveSlot).where(SaveSlot.session_id == current_session_id))
    ).scalar_one_or_none() is None
    assert (
        await db_session.execute(
            select(GameState).where(GameState.session_id == current_session_id)
        )
    ).scalar_one_or_none() is None

    reset_char_result = await db_session.execute(
        select(Character).where(Character.session_id == current_session_id)
    )
    reset_char = reset_char_result.scalar_one()
    assert reset_char.level == 2
    assert reset_char.xp == 0
    assert (reset_char.gp, reset_char.sp, reset_char.cp) == (0, 0, 0)
    assert reset_char.hp_current == reset_char.hp_max == 14
    assert reset_char.hp_temp == 0
    assert reset_char.spell_slots == {"1": {"total": 3, "used": 0}}
    assert reset_char.hit_dice == {"die": 6, "total": 2, "used": 0}
    assert reset_char.conditions == []
    assert reset_char.known_spells == ["magic_missile"]
    assert reset_char.personality == {"trait": "curious"}

    dossier_result = await db_session.execute(
        select(CampaignDossier).where(CampaignDossier.campaign_id == campaign_id)
    )
    dossier = dossier_result.scalar_one()
    assert dossier.import_sources == [{"id": "source-1", "kind": "text", "title": "Source privée"}]
    assert dossier.played_canon["rolling_summary"] == ""
    assert dossier.played_canon["established_facts"] == []
    assert dossier.player_contract["played_summary"] == ""
    assert [chapter["state"] for chapter in dossier.player_contract["visible_chapters"]] == [
        "active",
        "planned",
    ]
    assert [chapter["sessions"] for chapter in dossier.player_contract["visible_chapters"]] == [
        0,
        0,
    ]
    assert dossier.gm_dossier["narrative_arc"] == "Secret conservé."
    assert dossier.gm_dossier["region_map"] is None
    assert dossier.gm_dossier["city_maps"] == {}
    assert dossier.gm_dossier["active_city_id"] is None
    assert dossier.active_chapter_id == "chapter_1"


@pytest.mark.asyncio
async def test_reset_campaign_without_session_creates_current_lobby_session(
    async_client,
    db_session,
):
    campaign_resp = await async_client.post(
        "/api/campaigns",
        json={"name": "Campagne vide", "description": ""},
    )
    assert campaign_resp.status_code == 201
    campaign_id = campaign_resp.json()["id"]

    response = await async_client.post(f"/api/campaigns/{campaign_id}/reset")

    assert response.status_code == 200
    payload = response.json()
    assert payload["characters_reset"] == 0
    assert payload["sessions_removed"] == 0
    assert len(payload["campaign"]["session_ids"]) == 1
    session_id = payload["session_id"]

    session_result = await db_session.execute(select(Session).where(Session.id == session_id))
    session = session_result.scalar_one()
    assert session.status.value == "lobby"
    assert session.name == "Session 1 - Campagne vide"


@pytest.mark.asyncio
async def test_reset_campaign_not_found(async_client):
    response = await async_client.post(
        "/api/campaigns/00000000-0000-0000-0000-000000000000/reset"
    )

    assert response.status_code == 404
