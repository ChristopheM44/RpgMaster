from __future__ import annotations

from sqlalchemy import delete, func, select

from app.game.runtime import session_manager
from app.models.campaign import Campaign
from app.models.campaign_dossier import CampaignDossier
from app.models.character import Character
from app.models.game_state import GameState
from app.models.message import Message, MessageRole, MessageType
from app.models.save_slot import SaveSlot
from app.models.session import Session, SessionStatus

BASE_CHARACTER = {
    "species": "human",
    "char_class": "fighter",
    "ability_scores": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 13, "cha": 8},
    "hp_current": 12,
    "hp_max": 12,
}


async def _seed_chronicle(async_client, db_session) -> tuple[str, str, str]:
    campaign_resp = await async_client.post(
        "/api/campaigns",
        json={"name": "Brumes Portatives", "description": "Chronique à emporter"},
    )
    assert campaign_resp.status_code == 201
    campaign = campaign_resp.json()
    campaign_id = campaign["id"]
    first_session_id = campaign["session_ids"][0]

    char_resp = await async_client.post(
        "/api/characters/",
        json={**BASE_CHARACTER, "name": "Mira", "session_id": first_session_id},
    )
    assert char_resp.status_code == 201

    advance_resp = await async_client.post(
        f"/api/campaigns/{campaign_id}/advance",
        json={"new_session_name": "Session 2 - La Mine"},
    )
    assert advance_resp.status_code == 200
    second_session_id = advance_resp.json()["new_session_id"]

    second_char_result = await db_session.execute(
        select(Character).where(Character.session_id == second_session_id)
    )
    second_char = second_char_result.scalar_one()
    second_char.hp_current = 7
    second_char.xp = 350
    second_char.gp = 12

    state_data = {
        "phase": "exploration",
        "schema_version": 1,
        "characters": {
            second_char.id: {
                "name": second_char.name,
                "hp": 7,
                "hp_max": second_char.hp_max,
                "xp": 350,
            }
        },
        "chronicle": [{"id": "bram", "kind": "npc", "name": "Bram", "note": "Allié"}],
        "current_scene": {
            "visual_asset": {
                "provider": "local",
                "model": "test",
                "status": "ready",
                "prompt": "mine",
                "prompt_hash": "hash",
                "url": "http://localhost:9999/map.png",
            }
        },
        "turn_manager": {
            "order": [{"combatant_id": second_char.id, "name": second_char.name}],
            "index": 0,
        },
    }
    db_session.add_all(
        [
            GameState(
                session_id=second_session_id,
                turn_number=4,
                round_number=2,
                state_data=state_data,
            ),
            Message(
                session_id=second_session_id,
                role=MessageRole.GM,
                speaker="MJ",
                message_type=MessageType.NARRATION,
                content="La mine respire dans le noir.",
                metadata_={"scene_id": "mine"},
            ),
            Message(
                session_id=second_session_id,
                role=MessageRole.SYSTEM,
                speaker="Mira",
                message_type=MessageType.ROLL_RESULT,
                content="Jet de Sagesse",
                metadata_={"dice_notation": "1d20+2", "rolls": [15], "total": 17},
            ),
            SaveSlot(
                id="11111111-1111-4111-8111-111111111111",
                session_id=second_session_id,
                name="Avant la porte",
                phase="exploration",
                turn_number=4,
                round_number=2,
                state_data=state_data,
                characters_snapshot=[
                    {
                        "id": second_char.id,
                        "name": second_char.name,
                        "hp_current": 7,
                        "hp_max": second_char.hp_max,
                        "hp_temp": 0,
                        "level": second_char.level,
                        "xp": 350,
                        "ability_scores": second_char.ability_scores,
                        "equipment": second_char.equipment,
                        "spell_slots": second_char.spell_slots,
                        "hit_dice": second_char.hit_dice,
                        "known_spells": second_char.known_spells,
                        "conditions": second_char.conditions,
                        "proficiencies": second_char.proficiencies,
                    }
                ],
            ),
            CampaignDossier(
                id="22222222-2222-4222-8222-222222222222",
                campaign_id=campaign_id,
                player_contract={
                    "title": "Brumes Portatives",
                    "pitch_public": "Une mine sous la brume.",
                    "tones": ["Mystère"],
                    "duration": "2 sessions",
                    "hook": "Bram appelle les héros.",
                    "visible_chapters": [
                        {
                            "id": "chapter_1",
                            "num": "I",
                            "title": "La route",
                            "state": "done",
                            "sessions": 1,
                            "summary": "La route a parlé.",
                        }
                    ],
                    "known_objectives": ["Comprendre la mine."],
                    "played_summary": "Bram a été sauvé.",
                },
                gm_dossier={
                    "narrative_arc": "SECRET_NEVER_LEAK mène au cœur de la mine.",
                    "chapters": [],
                    "important_npcs": [{"name": "Bram", "secret": "SECRET_NEVER_LEAK"}],
                    "locations": [],
                    "factions": [],
                    "secrets": ["SECRET_NEVER_LEAK"],
                    "revelations": [],
                    "fronts": [],
                    "quests": [],
                    "complications": [],
                    "clues": [],
                    "light_mechanics": [],
                },
                played_canon={
                    "established_facts": ["Bram existe."],
                    "player_decisions": ["Mira a ouvert la marche."],
                    "quests": [{"id": "mine", "title": "La Mine"}],
                    "npc_relationships": [],
                    "revealed_secrets": ["Un symbole a été révélé."],
                    "plan_changes": [],
                    "rolling_summary": "Bram a été sauvé.",
                    "chapter_progression": [],
                },
                import_sources=[
                    {
                        "id": "source-1",
                        "kind": "text",
                        "title": "Notes privées",
                        "content": "secret",
                    }
                ],
                active_chapter_id="chapter_1",
                generation_status="validated",
            ),
        ]
    )
    await db_session.commit()
    return campaign_id, first_session_id, second_session_id


async def _clear_database(db_session) -> None:
    for model in (CampaignDossier, SaveSlot, Message, Character, GameState, Session, Campaign):
        await db_session.execute(delete(model))
    await db_session.commit()


async def test_export_import_round_trip_preserves_chronicle(async_client, db_session):
    campaign_id, first_session_id, second_session_id = await _seed_chronicle(
        async_client, db_session
    )

    export_resp = await async_client.get(f"/api/campaigns/{campaign_id}/export")
    assert export_resp.status_code == 200
    assert export_resp.headers["content-disposition"].endswith(".json\"")
    archive = export_resp.json()

    assert archive["format"] == "rpgmaster.chronicle"
    assert archive["format_version"] == 1
    assert archive["campaign"]["session_ids"] == [first_session_id, second_session_id]
    assert archive["dossier"]["gm_dossier"]["secrets"] == ["SECRET_NEVER_LEAK"]
    assert archive["sessions"][1]["messages"][1]["metadata"]["total"] == 17
    assert archive["sessions"][1]["save_slots"][0]["characters_snapshot"][0]["xp"] == 350
    assert archive["manifest"]["warnings"]

    await _clear_database(db_session)

    import_resp = await async_client.post("/api/campaigns/import", json=archive)
    assert import_resp.status_code == 200
    imported = import_resp.json()
    assert imported["campaign"]["id"] == campaign_id
    assert imported["active_session_id"] == second_session_id
    assert imported["imported"]["sessions"] == 2
    assert imported["imported"]["messages"] == 2
    assert imported["warnings"]

    dossier_result = await db_session.execute(
        select(CampaignDossier).where(CampaignDossier.campaign_id == campaign_id)
    )
    dossier = dossier_result.scalar_one()
    assert dossier.generation_status == "validated"
    assert dossier.gm_dossier["secrets"] == ["SECRET_NEVER_LEAK"]
    assert dossier.import_sources[0]["title"] == "Notes privées"

    messages_result = await db_session.execute(
        select(Message).where(Message.session_id == second_session_id).order_by(Message.created_at)
    )
    messages = list(messages_result.scalars().all())
    assert [m.message_type for m in messages] == [MessageType.NARRATION, MessageType.ROLL_RESULT]
    assert messages[1].metadata_["dice_notation"] == "1d20+2"

    save_result = await db_session.execute(
        select(SaveSlot).where(SaveSlot.session_id == second_session_id)
    )
    save = save_result.scalar_one()
    assert save.characters_snapshot[0]["xp"] == 350


async def test_import_preview_and_import_report_uuid_collisions(async_client, db_session):
    campaign_id, _, _ = await _seed_chronicle(async_client, db_session)
    archive = (await async_client.get(f"/api/campaigns/{campaign_id}/export")).json()

    preview_resp = await async_client.post("/api/campaigns/import/preview", json=archive)
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert preview["manifest"]["campaign"]["id"] == campaign_id
    assert any(conflict["kind"] == "campaign" for conflict in preview["conflicts"])

    import_resp = await async_client.post("/api/campaigns/import", json=archive)
    assert import_resp.status_code == 409
    assert any(
        conflict["kind"] == "campaign"
        for conflict in import_resp.json()["detail"]["conflicts"]
    )


async def test_invalid_import_is_rejected_without_partial_write(async_client, db_session):
    campaign_id, _, _ = await _seed_chronicle(async_client, db_session)
    archive = (await async_client.get(f"/api/campaigns/{campaign_id}/export")).json()
    await _clear_database(db_session)
    archive["sessions"][0]["messages"].append(
        {
            "id": "33333333-3333-4333-8333-333333333333",
            "session_id": archive["sessions"][0]["session"]["id"],
            "role": "dragon",
            "speaker": "MJ",
            "message_type": "narration",
            "content": "Impossible.",
            "metadata": None,
            "created_at": "2026-01-01T00:00:00",
        }
    )

    response = await async_client.post("/api/campaigns/import", json=archive)
    assert response.status_code == 422

    count_result = await db_session.execute(select(func.count()).select_from(Campaign))
    assert count_result.scalar_one() == 0


async def test_export_flushes_active_session_state(async_client, db_session):
    campaign_id, _, second_session_id = await _seed_chronicle(async_client, db_session)
    active = await session_manager.open_session(second_session_id, db_session)
    active.phase = SessionStatus.COMBAT
    active.turn_number = 99
    active.round_number = 5
    active.state_data["phase"] = "combat"
    active.state_data["combatants"] = {"enemy_1": {"name": "Ombre", "hp": 3}}
    active.mark_dirty()

    try:
        response = await async_client.get(f"/api/campaigns/{campaign_id}/export")
        assert response.status_code == 200
        archive = response.json()
        game_state = next(
            bundle["game_state"]
            for bundle in archive["sessions"]
            if bundle["session"]["id"] == second_session_id
        )
        assert game_state["turn_number"] == 99
        assert game_state["round_number"] == 5
        assert game_state["state_data"]["combatants"]["enemy_1"]["hp"] == 3
    finally:
        await session_manager.close_session(second_session_id, db_session)
