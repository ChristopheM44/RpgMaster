import pytest

from app.models.character import Character
from app.services.currency_service import currency_service
from app.services.level_up_service import level_up_service
from app.services.xp_service import xp_service


@pytest.mark.asyncio
async def test_xp_service_does_not_mutate_level_until_level_up(db_session):
    char = Character(
        name="Ada",
        species="human",
        char_class="fighter",
        level=1,
        ability_scores={"str": 15, "dex": 10, "con": 14, "int": 10, "wis": 10, "cha": 10},
        hp_current=12,
        hp_max=12,
        session_id="session-1",
    )
    db_session.add(char)
    await db_session.commit()
    await db_session.refresh(char)

    grant = await xp_service.grant_xp(
        session_id="session-1",
        character_id=char.id,
        amount=400,
        db=db_session,
    )
    await db_session.refresh(char)

    assert grant.level_up_available
    assert char.xp == 400
    assert char.level == 1

    applied = await level_up_service.level_up_character(
        session_id="session-1",
        character_id=char.id,
        db=db_session,
    )
    await db_session.refresh(char)

    assert applied.applied
    assert char.level == 2
    assert char.hp_max > 12


@pytest.mark.asyncio
async def test_currency_service_normalizes_grants_and_spends(db_session):
    char = Character(
        name="Bryn",
        species="human",
        char_class="rogue",
        level=1,
        ability_scores={"str": 10, "dex": 15, "con": 12, "int": 10, "wis": 10, "cha": 10},
        hp_current=9,
        hp_max=9,
        session_id="session-1",
    )
    db_session.add(char)
    await db_session.commit()
    await db_session.refresh(char)

    await currency_service.grant_currency(
        session_id="session-1",
        character_id=char.id,
        gp=0,
        sp=12,
        cp=25,
        db=db_session,
    )
    await db_session.refresh(char)
    assert (char.gp, char.sp, char.cp) == (1, 4, 5)

    await currency_service.spend_currency(
        session_id="session-1",
        character_id=char.id,
        cost_gp=0.35,
        db=db_session,
    )
    await db_session.refresh(char)
    assert (char.gp, char.sp, char.cp) == (1, 1, 0)
