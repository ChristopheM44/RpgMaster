import pytest

from app.game.gm_response_executor import GMResponseExecutor
from app.game.session_manager import ActiveSession
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
