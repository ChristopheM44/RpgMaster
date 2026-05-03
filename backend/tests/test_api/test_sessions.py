from __future__ import annotations

import pytest


@pytest.mark.asyncio
async def test_list_sessions_empty(async_client):
    """Liste vide au départ."""
    response = await async_client.get("/api/sessions/")
    assert response.status_code == 200
    data = response.json()
    assert data["sessions"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_api_requires_access_token_when_configured(async_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_access_token", "test-token")

    response = await async_client.get("/api/sessions/")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_api_accepts_bearer_access_token(async_client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "app_access_token", "test-token")

    response = await async_client.get(
        "/api/sessions/",
        headers={"Authorization": "Bearer test-token"},
    )
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_create_session(async_client):
    """Création d'une session retourne 201 avec les données correctes."""
    response = await async_client.post("/api/sessions/", json={"name": "La Caverne du Dragon"})
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "La Caverne du Dragon"
    assert data["status"] == "lobby"
    assert "id" in data
    assert "created_at" in data
    assert "updated_at" in data


@pytest.mark.asyncio
async def test_create_session_name_required(async_client):
    """Le nom est obligatoire."""
    response = await async_client.post("/api/sessions/", json={})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_session_name_not_empty(async_client):
    """Le nom ne peut pas être vide."""
    response = await async_client.post("/api/sessions/", json={"name": ""})
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_list_sessions_with_data(async_client):
    """La liste retourne les sessions créées."""
    await async_client.post("/api/sessions/", json={"name": "Session A"})
    await async_client.post("/api/sessions/", json={"name": "Session B"})

    response = await async_client.get("/api/sessions/")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 2
    assert len(data["sessions"]) == 2


@pytest.mark.asyncio
async def test_list_sessions_pagination(async_client):
    """La pagination (skip/limit) fonctionne."""
    for i in range(5):
        await async_client.post("/api/sessions/", json={"name": f"Session {i}"})

    response = await async_client.get("/api/sessions/?skip=2&limit=2")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 5
    assert len(data["sessions"]) == 2


@pytest.mark.asyncio
async def test_get_session(async_client):
    """Récupération d'une session par ID."""
    create_resp = await async_client.post("/api/sessions/", json={"name": "Test Session"})
    session_id = create_resp.json()["id"]

    response = await async_client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == session_id
    assert data["name"] == "Test Session"


@pytest.mark.asyncio
async def test_get_session_not_found(async_client):
    """404 pour un ID inexistant."""
    response = await async_client.get("/api/sessions/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_session_name(async_client):
    """Mise à jour du nom d'une session."""
    create_resp = await async_client.post("/api/sessions/", json={"name": "Ancien Nom"})
    session_id = create_resp.json()["id"]

    response = await async_client.put(
        f"/api/sessions/{session_id}", json={"name": "Nouveau Nom"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Nouveau Nom"
    assert data["id"] == session_id


@pytest.mark.asyncio
async def test_update_session_status(async_client):
    """Mise à jour du statut d'une session."""
    create_resp = await async_client.post("/api/sessions/", json={"name": "Session"})
    session_id = create_resp.json()["id"]

    response = await async_client.put(
        f"/api/sessions/{session_id}", json={"status": "character_creation"}
    )
    assert response.status_code == 200
    assert response.json()["status"] == "character_creation"


@pytest.mark.asyncio
async def test_update_session_not_found(async_client):
    """404 lors de la mise à jour d'une session inexistante."""
    response = await async_client.put(
        "/api/sessions/00000000-0000-0000-0000-000000000000", json={"name": "X"}
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_session(async_client):
    """Suppression d'une session retourne 204."""
    create_resp = await async_client.post("/api/sessions/", json={"name": "À Supprimer"})
    session_id = create_resp.json()["id"]

    response = await async_client.delete(f"/api/sessions/{session_id}")
    assert response.status_code == 204

    # Vérification que la session n'existe plus
    get_resp = await async_client.get(f"/api/sessions/{session_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_delete_session_removes_campaign_reference(async_client):
    """La suppression d'une session nettoie aussi les campagnes qui la référencent."""
    campaign_resp = await async_client.post(
        "/api/campaigns",
        json={"name": "Chronique test", "description": ""},
    )
    campaign_id = campaign_resp.json()["id"]

    advance_resp = await async_client.post(
        f"/api/campaigns/{campaign_id}/advance",
        json={"new_session_name": "Session 1"},
    )
    session_id = advance_resp.json()["new_session_id"]

    delete_resp = await async_client.delete(f"/api/sessions/{session_id}")
    assert delete_resp.status_code == 204

    campaign_detail = await async_client.get(f"/api/campaigns/{campaign_id}")
    assert campaign_detail.status_code == 200
    data = campaign_detail.json()
    assert data["session_ids"] == []
    assert data["current_session_index"] == 0
    assert data["counts"]["sessions"] == 0


@pytest.mark.asyncio
async def test_delete_session_not_found(async_client):
    """404 lors de la suppression d'une session inexistante."""
    response = await async_client.delete("/api/sessions/00000000-0000-0000-0000-000000000000")
    assert response.status_code == 404
