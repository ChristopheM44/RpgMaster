"""Tests for level-up and ASI REST endpoints."""
from __future__ import annotations

import pytest

_BASE = {
    "name": "Thassk",
    "species": "human",
    "char_class": "fighter",
    "ability_scores": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 13, "cha": 8},
    "hp_current": 11,
    "hp_max": 11,
}


async def _create(async_client, **overrides):
    payload = {**_BASE, **overrides}
    r = await async_client.post("/api/characters/", json=payload)
    assert r.status_code == 201
    return r.json()


# ── POST /level-up ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_level_up_insufficient_xp(async_client):
    """400 si le personnage n'a pas assez d'XP."""
    char = await _create(async_client, xp=0)
    r = await async_client.post(f"/api/characters/{char['id']}/level-up")
    assert r.status_code == 400
    assert "XP insuffisant" in r.json()["detail"]


@pytest.mark.asyncio
async def test_level_up_success(async_client):
    """200 avec niveau, PV et résultat corrects quand XP >= 300 (niveau 2)."""
    char = await _create(async_client, xp=300)
    r = await async_client.post(f"/api/characters/{char['id']}/level-up")
    assert r.status_code == 200
    data = r.json()
    assert data["old_level"] == 1
    assert data["new_level"] == 2
    assert data["hp_gained"] > 0
    assert data["character"]["level"] == 2
    assert data["character"]["hp_max"] > char["hp_max"]


@pytest.mark.asyncio
async def test_level_up_already_at_target(async_client):
    """400 si le personnage est déjà au niveau correspondant à ses XP."""
    char = await _create(async_client, xp=300, level=2)
    r = await async_client.post(f"/api/characters/{char['id']}/level-up")
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_level_up_not_found(async_client):
    """404 si le personnage n'existe pas."""
    r = await async_client.post("/api/characters/nonexistent-id/level-up")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_level_up_marks_pending_asi_at_level_4(async_client):
    """Le passage au niveau 4 marque pending_asi=True dans la réponse."""
    char = await _create(async_client, xp=2700, level=3)
    r = await async_client.post(f"/api/characters/{char['id']}/level-up")
    assert r.status_code == 200
    data = r.json()
    assert data["requires_asi"] is True
    assert 4 in data["asi_levels_granted"]
    assert data["character"]["pending_asi"] is True


# ── POST /asi-choice ───────────────────────────────────────────────────────────


async def _char_with_pending_asi(async_client):
    """Helper: crée un personnage au niveau 3 avec 2700 XP, le monte au 4 (ASI)."""
    char = await _create(async_client, xp=2700, level=3)
    r = await async_client.post(f"/api/characters/{char['id']}/level-up")
    assert r.status_code == 200
    return r.json()["character"]


@pytest.mark.asyncio
async def test_asi_plus_two(async_client):
    """+2 à une stat augmente le score de 2, efface pending_asi."""
    char = await _char_with_pending_asi(async_client)
    old_str = char["ability_scores"]["str"]
    r = await async_client.post(
        f"/api/characters/{char['id']}/asi-choice",
        json={"mode": "plus_two", "ability": "str"},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ability_scores"]["str"] == min(20, old_str + 2)
    assert data["pending_asi"] is False


@pytest.mark.asyncio
async def test_asi_plus_one_two(async_client):
    """+1 à deux stats différentes."""
    char = await _char_with_pending_asi(async_client)
    old_str = char["ability_scores"]["str"]
    old_dex = char["ability_scores"]["dex"]
    r = await async_client.post(
        f"/api/characters/{char['id']}/asi-choice",
        json={"mode": "plus_one_two", "abilities": ["str", "dex"]},
    )
    assert r.status_code == 200
    data = r.json()
    assert data["ability_scores"]["str"] == min(20, old_str + 1)
    assert data["ability_scores"]["dex"] == min(20, old_dex + 1)
    assert data["pending_asi"] is False


@pytest.mark.asyncio
async def test_asi_duplicate_abilities_rejected(async_client):
    """plus_one_two avec deux fois la même stat → 400."""
    char = await _char_with_pending_asi(async_client)
    r = await async_client.post(
        f"/api/characters/{char['id']}/asi-choice",
        json={"mode": "plus_one_two", "abilities": ["str", "str"]},
    )
    assert r.status_code == 400
    assert "différentes" in r.json()["detail"]


@pytest.mark.asyncio
async def test_asi_cap_at_20(async_client):
    """Score plafonné à 20 même si la valeur de base est déjà haute."""
    char = await _create(async_client, xp=2700, level=3,
                         ability_scores={"str": 20, "dex": 12, "con": 14,
                                         "int": 10, "wis": 13, "cha": 8})
    await async_client.post(f"/api/characters/{char['id']}/level-up")
    r = await async_client.post(
        f"/api/characters/{char['id']}/asi-choice",
        json={"mode": "plus_two", "ability": "str"},
    )
    assert r.status_code == 200
    assert r.json()["ability_scores"]["str"] == 20


@pytest.mark.asyncio
async def test_asi_no_pending(async_client):
    """400 si aucune ASI en attente."""
    char = await _create(async_client)
    r = await async_client.post(
        f"/api/characters/{char['id']}/asi-choice",
        json={"mode": "plus_two", "ability": "str"},
    )
    assert r.status_code == 400
    assert "en attente" in r.json()["detail"]


@pytest.mark.asyncio
async def test_asi_invalid_mode(async_client):
    """Mode inconnu → 400."""
    char = await _char_with_pending_asi(async_client)
    r = await async_client.post(
        f"/api/characters/{char['id']}/asi-choice",
        json={"mode": "plus_five", "ability": "str"},
    )
    assert r.status_code == 400
