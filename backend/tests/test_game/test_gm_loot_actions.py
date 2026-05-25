import pytest

from app.game.gm_response_executor import GMResponseExecutor
from app.game.session_manager import ActiveSession
from app.models.campaign import Campaign
from app.models.campaign_dossier import CampaignDossier
from app.models.character import Character
from app.models.session import SessionStatus


@pytest.mark.asyncio
async def test_gm_loot_currency_and_xp_actions_apply_to_character(db_session):
    char = Character(
        name="Pax",
        species="human",
        char_class="fighter",
        level=1,
        ability_scores={"str": 15, "dex": 10, "con": 12, "int": 10, "wis": 10, "cha": 10},
        hp_current=11,
        hp_max=11,
        session_id="session-1",
    )
    db_session.add(char)
    await db_session.commit()
    await db_session.refresh(char)

    active = ActiveSession(
        session_id="session-1",
        phase=SessionStatus.ENCOUNTER_END,
        state_data={"characters": {char.id: {"name": char.name, "level": 1, "hp": 11}}},
    )
    executor = GMResponseExecutor(source="test")

    await executor.execute_action(
        "session-1",
        "xp_grant",
        {"target": "party", "amount": 300},
        active,
        db=db_session,
    )
    await executor.execute_action(
        "session-1",
        "currency_grant",
        {"target": char.id, "gp": 1, "sp": 2, "cp": 3},
        active,
        db=db_session,
    )
    await executor.execute_action(
        "session-1",
        "loot_grant",
        {"target": char.id, "items": [{"template_id": "healing_potion", "quantity": 1}]},
        active,
        db=db_session,
    )
    await db_session.refresh(char)

    assert char.xp == 300
    assert char.level == 1
    assert (char.gp, char.sp, char.cp) == (1, 2, 3)
    assert char.equipment[0]["template_id"] == "healing_potion"


@pytest.mark.asyncio
async def test_gm_loot_grant_uses_custom_item_before_srd_and_tracks_unique(db_session):
    campaign = Campaign(
        id="campaign-1",
        name="Cendres",
        description="",
        session_ids=["session-unique"],
    )
    dossier = CampaignDossier(
        id="dossier-1",
        campaign_id=campaign.id,
        player_contract={},
        gm_dossier={
            "items": [
                {
                    "id": "healing_potion",
                    "template_id": "healing_potion",
                    "name": "Ashen Tonic",
                    "name_fr": "Tonique de cendre",
                    "category": "consumable",
                    "item_type": "consumable",
                    "effect": {"kind": "heal", "dice": "4d4+4"},
                    "unique": True,
                }
            ],
        },
        played_canon={"granted_unique_items": []},
        import_sources=[],
        forge_job={},
        active_chapter_id="chapter_1",
        generation_status="validated",
    )
    char = Character(
        name="Pax",
        species="human",
        char_class="fighter",
        level=1,
        ability_scores={"str": 15, "dex": 10, "con": 12, "int": 10, "wis": 10, "cha": 10},
        hp_current=11,
        hp_max=11,
        session_id="session-unique",
    )
    db_session.add_all([campaign, dossier, char])
    await db_session.commit()
    await db_session.refresh(char)

    active = ActiveSession(
        session_id="session-unique",
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {char.id: {"name": char.name, "level": 1, "hp": 11}},
            "campaign_context": {
                "campaign_id": campaign.id,
                "items": dossier.gm_dossier["items"],
                "played_canon": {"granted_unique_items": []},
            },
        },
    )
    executor = GMResponseExecutor(source="test")

    params = {"target": char.id, "items": [{"template_id": "healing-potion", "quantity": 1}]}
    await executor.execute_action("session-unique", "loot_grant", params, active, db=db_session)
    await executor.execute_action("session-unique", "loot_grant", params, active, db=db_session)

    await db_session.refresh(char)
    await db_session.refresh(dossier)

    assert len(char.equipment) == 1
    assert char.equipment[0]["name"] == "Ashen Tonic"
    assert char.equipment[0]["effect"]["dice"] == "4d4+4"
    assert dossier.played_canon["granted_unique_items"] == ["healing_potion"]
    assert active.state_data["campaign_context"]["played_canon"]["granted_unique_items"] == [
        "healing_potion"
    ]
