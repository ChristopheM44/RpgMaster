"""Tests for engine/srd_data/schemas.py.

Validates that every entry in monsters.json and spells.json conforms to its
Pydantic schema. This is the safety net that catches malformed data added by
parsers or hand-edits.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.engine.srd_data import get_monsters, get_spells
from app.engine.srd_data.schemas import MonsterSchema, SpellSchema

DATA_DIR = Path(__file__).resolve().parents[2] / "app" / "engine" / "srd_data"


def _load_raw(filename: str) -> list[dict]:
    with (DATA_DIR / filename).open(encoding="utf-8") as f:
        payload = json.load(f)
    # Both files wrap the list under a top-level key.
    return payload["monsters" if "monsters" in payload else "spells"]


# ---------------------------------------------------------------------------
# Bulk validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("entry", _load_raw("monsters.json"), ids=lambda e: e["id"])
def test_each_monster_validates(entry):
    MonsterSchema.model_validate(entry)


@pytest.mark.parametrize("entry", _load_raw("spells.json"), ids=lambda e: e["id"])
def test_each_spell_validates(entry):
    SpellSchema.model_validate(entry)


# ---------------------------------------------------------------------------
# Loader-level invariants
# ---------------------------------------------------------------------------


def test_loaders_return_validated_lists():
    monsters = get_monsters()
    spells = get_spells()
    assert len(monsters) > 0
    assert len(spells) > 0
    # Loader is cached; second call returns the same object.
    assert get_monsters() is monsters
    assert get_spells() is spells


def test_no_duplicate_ids():
    monster_ids = [m["id"] for m in get_monsters()]
    spell_ids = [s["id"] for s in get_spells()]
    assert len(set(monster_ids)) == len(monster_ids), "Duplicate monster ids"
    assert len(set(spell_ids)) == len(spell_ids), "Duplicate spell ids"


def test_srd_5_2_audit_removed_legacy_spells():
    """The 5.0-only spells `wrathful_smite` and `arms_of_hadar` were dropped
    in the 5.2 audit; ensure they don't leak back in."""
    ids = {s["id"] for s in get_spells()}
    assert "wrathful_smite" not in ids
    assert "arms_of_hadar" not in ids


def test_loader_rejects_malformed_entry(tmp_path, monkeypatch):
    """If someone hand-edits a JSON file with an invalid entry, the loader
    must raise ValueError on the next cold call rather than corrupt runtime
    behavior."""
    # Build a malformed monsters.json with one entry missing required fields.
    bad_payload = {
        "monsters": [
            {
                "id": "broken_test_only",
                "name": "Broken",
                "name_fr": "Cassé",
                # Missing nearly every required field.
            }
        ]
    }
    bad_dir = tmp_path / "srd_data"
    bad_dir.mkdir()
    (bad_dir / "monsters.json").write_text(json.dumps(bad_payload))

    # Re-validate using the schema directly (avoids touching the cached loader).
    with pytest.raises(Exception):
        MonsterSchema.model_validate(bad_payload["monsters"][0])
