import random

from app.engine.loot import loot_for_encounter


def test_loot_for_encounter_is_deterministic_with_seed():
    first = loot_for_encounter(
        total_cr=2,
        monster_xp=400,
        difficulty="medium",
        rng=random.Random(42),
    )
    second = loot_for_encounter(
        total_cr=2,
        monster_xp=400,
        difficulty="medium",
        rng=random.Random(42),
    )
    assert first == second
    assert first.coins.gp >= 0
    assert isinstance(first.items, list)
