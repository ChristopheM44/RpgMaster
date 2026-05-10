import pytest

from app.models.character import Character
from app.services.trade_service import trade_service


@pytest.mark.asyncio
async def test_give_item_moves_instance_between_characters(db_session):
    giver = Character(
        name="Nia",
        species="human",
        char_class="cleric",
        level=1,
        ability_scores={"str": 10, "dex": 10, "con": 12, "int": 10, "wis": 15, "cha": 10},
        hp_current=9,
        hp_max=9,
        equipment=[{"id": "healing_potion_1", "template_id": "healing_potion", "name_fr": "Potion", "equipped": True}],
        session_id="session-1",
    )
    receiver = Character(
        name="Oren",
        species="human",
        char_class="fighter",
        level=1,
        ability_scores={"str": 15, "dex": 10, "con": 12, "int": 10, "wis": 10, "cha": 10},
        hp_current=11,
        hp_max=11,
        equipment=[],
        session_id="session-1",
    )
    db_session.add_all([giver, receiver])
    await db_session.commit()
    await db_session.refresh(giver)
    await db_session.refresh(receiver)

    await trade_service.give_item(
        session_id="session-1",
        from_character_id=giver.id,
        to_character_id=receiver.id,
        item_id="healing_potion_1",
        db=db_session,
    )
    await db_session.refresh(giver)
    await db_session.refresh(receiver)

    assert giver.equipment == []
    assert receiver.equipment[0]["id"] == "healing_potion_1"
    assert receiver.equipment[0]["equipped"] is False
