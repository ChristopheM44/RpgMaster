from app.engine.inventory import (
    can_equip_in_slot,
    carrying_capacity,
    encumbrance_level,
    slots_for_item,
    total_weight,
)


def test_weight_and_encumbrance():
    equipment = [{"weight_lb": 5, "quantity": 2}, {"weight": 1}]
    assert total_weight(equipment) == 11
    capacity = carrying_capacity(10)
    assert capacity == 150
    assert encumbrance_level(80, capacity) == "normal"
    assert encumbrance_level(120, capacity) == "encumbered"
    assert encumbrance_level(160, capacity) == "heavily"


def test_two_handed_weapon_occupies_both_hands():
    item = {"item_type": "weapon", "category": "martial", "properties": ["two-handed"]}
    assert slots_for_item(item) == {"main_hand", "off_hand"}


def test_slot_conflict_detected():
    current = [
        {
            "id": "greataxe_1",
            "item_type": "weapon",
            "category": "martial",
            "properties": ["two-handed"],
            "equipped": True,
            "occupied_slots": ["main_hand", "off_hand"],
        }
    ]
    shield = {"id": "shield_1", "category": "shield", "item_type": "shield"}
    ok, reason = can_equip_in_slot(shield, None, current)
    assert not ok
    assert reason
