from __future__ import annotations

import pytest

from app.engine.dice import RollResult
from app.game.session_manager import ActiveSession, SessionManager
from app.models.character import Character
from app.models.session import Session, SessionStatus
from app.services.equipment_service import EquipmentService
from app.services.rest_service import RestService, build_hit_dice


def _hero(session_id: str, **overrides) -> Character:
    data = {
        "name": "Thorvald",
        "species": "human",
        "char_class": "fighter",
        "level": 1,
        "ability_scores": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 10},
        "hp_current": 5,
        "hp_max": 12,
        "hp_temp": 0,
        "equipment": [],
        "spell_slots": {"1": {"total": 2, "used": 1}},
        "hit_dice": {"die": 10, "total": 1, "used": 0},
        "known_spells": [],
        "conditions": [],
        "proficiencies": {},
        "personality": {},
        "session_id": session_id,
    }
    data.update(overrides)
    return Character(**data)


@pytest.mark.asyncio
async def test_equipment_service_toggles_armor_without_unequipping_shield(db_session) -> None:
    session = Session(name="Inventory", status=SessionStatus.EXPLORATION)
    db_session.add(session)
    await db_session.commit()

    char = _hero(
        session.id,
        equipment=[
            {
                "id": "chain_mail",
                "name_fr": "Cotte de mailles",
                "category": "heavy",
                "equipped": True,
            },
            {"id": "leather", "name_fr": "Cuir", "category": "light", "equipped": False},
            {"id": "shield", "name_fr": "Bouclier", "category": "shield", "equipped": False},
        ],
    )
    db_session.add(char)
    await db_session.commit()

    active = ActiveSession(session_id=session.id, phase=SessionStatus.EXPLORATION)
    active.state_data["characters"] = {char.id: {"equipment": list(char.equipment), "hp": 5}}

    service = EquipmentService()
    shield = await service.equip_item(
        character_id=char.id,
        item_id="shield",
        db=db_session,
        active=active,
    )
    assert next(item for item in shield.equipment if item["id"] == "shield")["equipped"] is True
    assert next(item for item in shield.equipment if item["id"] == "chain_mail")["equipped"] is True

    armor = await service.equip_item(
        character_id=char.id,
        item_id="leather",
        db=db_session,
        active=active,
    )
    assert next(item for item in armor.equipment if item["id"] == "leather")["equipped"] is True
    assert next(item for item in armor.equipment if item["id"] == "chain_mail")["equipped"] is False
    assert next(item for item in armor.equipment if item["id"] == "shield")["equipped"] is True
    assert active.state_data["characters"][char.id]["equipment"] == armor.equipment


@pytest.mark.asyncio
async def test_equipment_service_uses_healing_potion_and_decrements_quantity(
    db_session,
    monkeypatch,
) -> None:
    session = Session(name="Potion", status=SessionStatus.EXPLORATION)
    db_session.add(session)
    await db_session.commit()

    char = _hero(
        session.id,
        hp_current=3,
        hp_max=10,
        equipment=[{"id": "healing_potion", "name_fr": "Potion de soin", "quantity": 2}],
    )
    db_session.add(char)
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.equipment_service.roll",
        lambda _notation: RollResult("2d4+2", [2, 3], [2, 3], 2, 7),
    )

    active = ActiveSession(session_id=session.id, phase=SessionStatus.EXPLORATION)
    active.state_data["characters"] = {char.id: {"equipment": list(char.equipment), "hp": 3}}

    result = await EquipmentService().use_item(
        character_id=char.id,
        item_id="healing_potion",
        db=db_session,
        active=active,
    )

    assert result.hp == 10
    assert result.hp_delta == 7
    assert result.equipment[0]["quantity"] == 1
    assert active.state_data["characters"][char.id]["hp"] == 10


@pytest.mark.asyncio
async def test_rest_service_short_rest_spends_hit_dice_and_caps_healing(
    db_session,
    monkeypatch,
) -> None:
    session = Session(name="Short Rest", status=SessionStatus.EXPLORATION)
    db_session.add(session)
    await db_session.commit()

    char = _hero(session.id, hp_current=9, hp_max=12)
    db_session.add(char)
    await db_session.commit()

    monkeypatch.setattr(
        "app.services.rest_service.roll",
        lambda _notation: RollResult("1d10+2", [8], [8], 2, 10),
    )

    manager = SessionManager()
    active = ActiveSession(session_id=session.id, phase=SessionStatus.EXPLORATION)
    active.state_data["characters"] = {
        char.id: {
            "hp": 9,
            "hp_max": 12,
            "spell_slots": dict(char.spell_slots),
            "hit_dice": dict(char.hit_dice),
        }
    }
    manager._sessions[session.id] = active

    result = await RestService(manager).short_rest(
        session_id=session.id,
        active=active,
        db=db_session,
        hit_dice_spend={char.id: 1},
    )

    assert result.updates[0].hp_delta == 3
    assert result.updates[0].hit_dice == {"die": 10, "total": 1, "used": 1}
    assert active.state_data["characters"][char.id]["hp"] == 12
    assert active.state_data["characters"][char.id]["hit_dice"]["used"] == 1


@pytest.mark.asyncio
async def test_rest_service_long_rest_restores_hp_spell_slots_and_hit_dice(db_session) -> None:
    session = Session(name="Long Rest", status=SessionStatus.ENCOUNTER_END)
    db_session.add(session)
    await db_session.commit()

    char = _hero(
        session.id,
        hp_current=2,
        hp_max=12,
        spell_slots={"1": {"total": 2, "used": 2}},
        hit_dice={"die": 10, "total": 1, "used": 1},
    )
    db_session.add(char)
    await db_session.commit()

    manager = SessionManager()
    active = ActiveSession(session_id=session.id, phase=SessionStatus.ENCOUNTER_END)
    active.state_data["characters"] = {
        char.id: {
            "hp": 2,
            "hp_max": 12,
            "spell_slots": dict(char.spell_slots),
            "hit_dice": dict(char.hit_dice),
        }
    }
    manager._sessions[session.id] = active

    result = await RestService(manager).long_rest(
        session_id=session.id,
        active=active,
        db=db_session,
    )

    assert result.updates[0].hp == 12
    assert result.updates[0].spell_slots["1"]["used"] == 0
    assert result.updates[0].hit_dice["used"] == 0
    assert active.phase == SessionStatus.EXPLORATION


def test_build_hit_dice_uses_class_hit_die_and_level() -> None:
    assert build_hit_dice("fighter", 3) == {"die": 10, "total": 3, "used": 0}
