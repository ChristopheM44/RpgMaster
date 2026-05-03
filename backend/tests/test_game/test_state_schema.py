from __future__ import annotations

import pytest

from app.game.state_schema import STATE_SCHEMA_VERSION, migrate_state_data, validate_state_data


def test_migrate_state_data_adds_schema_version() -> None:
    migrated = migrate_state_data({"characters": {"hero-1": {"name": "Aria"}}})

    assert migrated["schema_version"] == STATE_SCHEMA_VERSION
    validate_state_data(migrated)


def test_migrate_state_data_normalizes_uppercase_phase() -> None:
    migrated = migrate_state_data({"phase": "COMBAT"})

    assert migrated["phase"] == "combat"


def test_validate_state_data_rejects_unknown_phase() -> None:
    with pytest.raises(ValueError):
        validate_state_data({"schema_version": STATE_SCHEMA_VERSION, "phase": "dream"})
