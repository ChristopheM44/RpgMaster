from app.engine.level_up import compute_level_up


def test_compute_level_up_preserves_used_slots_and_hit_dice():
    result = compute_level_up(
        char_class="wizard",
        current_level=1,
        target_level=3,
        con_score=14,
        current_spell_slots={"1": {"total": 2, "used": 1}},
        current_hit_dice={"die": 6, "total": 1, "used": 1},
    )
    assert result.new_level == 3
    assert result.hp_total_gain == 12
    assert result.new_spell_slots == {
        "1": {"total": 4, "used": 1},
        "2": {"total": 2, "used": 0},
    }
    assert result.new_hit_dice == {"die": 6, "total": 3, "used": 1}


def test_compute_level_up_marks_asi_levels():
    result = compute_level_up(
        char_class="fighter",
        current_level=3,
        target_level=5,
        con_score=10,
        current_spell_slots={},
        current_hit_dice={"die": 10, "total": 3, "used": 0},
    )
    assert result.asi_levels_granted == [4]


def test_warlock_pact_magic_progression():
    result = compute_level_up(
        char_class="warlock",
        current_level=4,
        target_level=5,
        con_score=12,
        current_spell_slots={"2": {"total": 2, "used": 1}},
        current_hit_dice={"die": 8, "total": 4, "used": 0},
    )
    assert result.new_spell_slots == {"3": {"total": 2, "used": 0}}
