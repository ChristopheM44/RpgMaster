from app.engine.xp import level_from_xp, xp_for_level, xp_to_next_level


def test_xp_threshold_lookup():
    assert xp_for_level(1) == 0
    assert xp_for_level(5) == 6500
    assert level_from_xp(0) == 1
    assert level_from_xp(299) == 1
    assert level_from_xp(300) == 2
    assert level_from_xp(355000) == 20


def test_xp_to_next_level():
    assert xp_to_next_level(0, 1) == 300
    assert xp_to_next_level(300, 1) == 0
    assert xp_to_next_level(400, 2) == 500
    assert xp_to_next_level(999999, 20) == 0
