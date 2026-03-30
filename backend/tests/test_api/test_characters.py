from __future__ import annotations

import pytest

# Payload minimal valide pour créer un personnage
_BASE_CHARACTER = {
    "name": "Aragorn",
    "species": "human",
    "char_class": "fighter",
    "ability_scores": {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 13, "cha": 8},
    "hp_current": 12,
    "hp_max": 12,
}


@pytest.mark.asyncio
async def test_list_characters_empty(async_client):
    """Liste vide au départ."""
    response = await async_client.get("/api/characters/")
    assert response.status_code == 200
    data = response.json()
    assert data["characters"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_create_character(async_client):
    """Création d'un personnage retourne 201 avec les données correctes."""
    response = await async_client.post("/api/characters/", json=_BASE_CHARACTER)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Aragorn"
    assert data["species"] == "human"
    assert data["char_class"] == "fighter"
    assert data["level"] == 1
    assert data["is_ai"] is False
    assert "id" in data
    assert "created_at" in data


@pytest.mark.asyncio
async def test_create_character_name_required(async_client):
    """Le nom est obligatoire."""
    payload = {k: v for k, v in _BASE_CHARACTER.items() if k != "name"}
    response = await async_client.post("/api/characters/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_character_species_required(async_client):
    """L'espèce est obligatoire."""
    payload = {k: v for k, v in _BASE_CHARACTER.items() if k != "species"}
    response = await async_client.post("/api/characters/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_character_class_required(async_client):
    """La classe est obligatoire."""
    payload = {k: v for k, v in _BASE_CHARACTER.items() if k != "char_class"}
    response = await async_client.post("/api/characters/", json=payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_ai_character(async_client):
    """Création d'un personnage IA."""
    payload = {**_BASE_CHARACTER, "name": "Legolas (IA)", "is_ai": True, "player_name": None}
    response = await async_client.post("/api/characters/", json=payload)
    assert response.status_code == 201
    assert response.json()["is_ai"] is True


@pytest.mark.asyncio
async def test_list_characters_with_data(async_client):
    """La liste retourne les personnages créés."""
    await async_client.post("/api/characters/", json={**_BASE_CHARACTER, "name": "Perso A"})
    await async_client.post("/api/characters/", json={**_BASE_CHARACTER, "name": "Perso B"})

    response = await async_client.get("/api/characters/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["characters"]) == 2


@pytest.mark.asyncio
async def test_list_characters_filter_by_session(async_client):
    """Filtrage des personnages par session_id."""
    # Créer une session
    session_resp = await async_client.post("/api/sessions/", json={"name": "Session Test"})
    session_id = session_resp.json()["id"]

    # Personnage dans la session
    await async_client.post(
        "/api/characters/", json={**_BASE_CHARACTER, "name": "Dans Session", "session_id": session_id}
    )
    # Personnage sans session
    await async_client.post("/api/characters/", json={**_BASE_CHARACTER, "name": "Sans Session"})

    # Filtre par session
    response = await async_client.get(f"/api/characters/?session_id={session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["characters"][0]["name"] == "Dans Session"


@pytest.mark.asyncio
async def test_list_characters_pagination(async_client):
    """La pagination fonctionne."""
    for i in range(5):
        await async_client.post("/api/characters/", json={**_BASE_CHARACTER, "name": f"Perso {i}"})

    response = await async_client.get("/api/characters/?skip=1&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["characters"]) == 2


@pytest.mark.asyncio
async def test_get_character(async_client):
    """Récupération d'un personnage par ID."""
    create_resp = await async_client.post("/api/characters/", json=_BASE_CHARACTER)
    char_id = create_resp.json()["id"]

    response = await async_client.get(f"/api/characters/{char_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == char_id
    assert data["name"] == "Aragorn"


@pytest.mark.asyncio
async def test_get_character_not_found(async_client):
    """404 pour un personnage inexistant."""
    response = await async_client.get("/api/characters/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_character_name(async_client):
    """Mise à jour partielle : nom."""
    create_resp = await async_client.post("/api/characters/", json=_BASE_CHARACTER)
    char_id = create_resp.json()["id"]

    response = await async_client.put(f"/api/characters/{char_id}", json={"name": "Strider"})
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Strider"
    assert data["char_class"] == "fighter"  # Inchangé


@pytest.mark.asyncio
async def test_update_character_hp(async_client):
    """Mise à jour des points de vie."""
    create_resp = await async_client.post("/api/characters/", json=_BASE_CHARACTER)
    char_id = create_resp.json()["id"]

    response = await async_client.put(f"/api/characters/{char_id}", json={"hp_current": 5})
    assert response.status_code == 200
    assert response.json()["hp_current"] == 5


@pytest.mark.asyncio
async def test_update_character_level(async_client):
    """Mise à jour du niveau."""
    create_resp = await async_client.post("/api/characters/", json=_BASE_CHARACTER)
    char_id = create_resp.json()["id"]

    response = await async_client.put(f"/api/characters/{char_id}", json={"level": 5})
    assert response.status_code == 200
    assert response.json()["level"] == 5


@pytest.mark.asyncio
async def test_update_character_not_found(async_client):
    """404 lors de la mise à jour d'un personnage inexistant."""
    response = await async_client.put(
        "/api/characters/00000000-0000-0000-0000-000000000000", json={"name": "X"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_character(async_client):
    """Suppression d'un personnage retourne 204."""
    create_resp = await async_client.post("/api/characters/", json=_BASE_CHARACTER)
    char_id = create_resp.json()["id"]

    response = await async_client.delete(f"/api/characters/{char_id}")
    assert response.status_code == 204

    get_resp = await async_client.get(f"/api/characters/{char_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_character_not_found(async_client):
    """404 lors de la suppression d'un personnage inexistant."""
    response = await async_client.delete("/api/characters/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
