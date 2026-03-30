from __future__ import annotations

import pytest


# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_classes(async_client):
    """Liste toutes les classes SRD."""
    response = await async_client.get("/api/srd/classes")
    assert response.status_code == 200
    data = response.json()
    assert "classes" in data
    assert "total" in data
    assert data["total"] > 0
    assert len(data["classes"]) == data["total"]


@pytest.mark.asyncio
async def test_get_class_valid(async_client):
    """Récupération d'une classe par ID valide."""
    # Récupérer la liste pour obtenir un ID réel
    list_resp = await async_client.get("/api/srd/classes")
    first_id = list_resp.json()["classes"][0]["id"]

    response = await async_client.get(f"/api/srd/classes/{first_id}")
    assert response.status_code == 200
    assert response.json()["id"] == first_id


@pytest.mark.asyncio
async def test_get_class_not_found(async_client):
    """404 pour une classe inexistante."""
    response = await async_client.get("/api/srd/classes/classe_inconnue")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Espèces
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_species(async_client):
    """Liste toutes les espèces SRD."""
    response = await async_client.get("/api/srd/species")
    assert response.status_code == 200
    data = response.json()
    assert "species" in data
    assert "total" in data
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_get_species_valid(async_client):
    """Récupération d'une espèce par ID valide."""
    list_resp = await async_client.get("/api/srd/species")
    first_id = list_resp.json()["species"][0]["id"]

    response = await async_client.get(f"/api/srd/species/{first_id}")
    assert response.status_code == 200
    assert response.json()["id"] == first_id


@pytest.mark.asyncio
async def test_get_species_not_found(async_client):
    """404 pour une espèce inexistante."""
    response = await async_client.get("/api/srd/species/espece_inconnue")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Sorts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_spells(async_client):
    """Liste tous les sorts SRD."""
    response = await async_client.get("/api/srd/spells")
    assert response.status_code == 200
    data = response.json()
    assert "spells" in data
    assert "total" in data
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_list_spells_filter_by_level(async_client):
    """Filtrage des sorts par niveau."""
    response = await async_client.get("/api/srd/spells?level=0")
    assert response.status_code == 200
    data = response.json()
    for spell in data["spells"]:
        assert spell["level"] == 0


@pytest.mark.asyncio
async def test_list_spells_filter_by_class(async_client):
    """Filtrage des sorts par classe."""
    # Récupérer une classe valide présente dans les sorts
    all_resp = await async_client.get("/api/srd/spells")
    all_spells = all_resp.json()["spells"]

    # Trouver une classe présente dans au moins un sort
    char_class = None
    for spell in all_spells:
        classes = spell.get("classes", [])
        if classes:
            char_class = classes[0]
            break

    if char_class is None:
        pytest.skip("Aucun sort avec une classe définie dans les données SRD")

    response = await async_client.get(f"/api/srd/spells?char_class={char_class}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    for spell in data["spells"]:
        assert char_class in spell.get("classes", [])


@pytest.mark.asyncio
async def test_get_spell_valid(async_client):
    """Récupération d'un sort par ID valide."""
    list_resp = await async_client.get("/api/srd/spells")
    first_id = list_resp.json()["spells"][0]["id"]

    response = await async_client.get(f"/api/srd/spells/{first_id}")
    assert response.status_code == 200
    assert response.json()["id"] == first_id


@pytest.mark.asyncio
async def test_get_spell_not_found(async_client):
    """404 pour un sort inexistant."""
    response = await async_client.get("/api/srd/spells/sort_inconnu")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Monstres
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_monsters(async_client):
    """Liste tous les monstres SRD."""
    response = await async_client.get("/api/srd/monsters")
    assert response.status_code == 200
    data = response.json()
    assert "monsters" in data
    assert "total" in data
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_list_monsters_filter_by_cr(async_client):
    """Filtrage des monstres par CR max."""
    response = await async_client.get("/api/srd/monsters?max_cr=1")
    assert response.status_code == 200
    data = response.json()
    for monster in data["monsters"]:
        assert monster.get("cr", 0) <= 1


@pytest.mark.asyncio
async def test_list_monsters_cr_zero(async_client):
    """Filtrage avec max_cr=0 ne retourne que les monstres CR 0."""
    response = await async_client.get("/api/srd/monsters?max_cr=0")
    assert response.status_code == 200
    data = response.json()
    for monster in data["monsters"]:
        assert monster.get("cr", 0) <= 0


@pytest.mark.asyncio
async def test_get_monster_valid(async_client):
    """Récupération d'un monstre par ID valide."""
    list_resp = await async_client.get("/api/srd/monsters")
    first_id = list_resp.json()["monsters"][0]["id"]

    response = await async_client.get(f"/api/srd/monsters/{first_id}")
    assert response.status_code == 200
    assert response.json()["id"] == first_id


@pytest.mark.asyncio
async def test_get_monster_not_found(async_client):
    """404 pour un monstre inexistant."""
    response = await async_client.get("/api/srd/monsters/monstre_inconnu")
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Équipement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_equipment(async_client):
    """Liste tout l'équipement SRD."""
    response = await async_client.get("/api/srd/equipment")
    assert response.status_code == 200
    data = response.json()
    assert "equipment" in data
    assert "total" in data
    assert data["total"] > 0


@pytest.mark.asyncio
async def test_list_equipment_filter_by_category(async_client):
    """Filtrage de l'équipement par catégorie."""
    # Récupérer une catégorie valide
    all_resp = await async_client.get("/api/srd/equipment")
    all_items = all_resp.json()["equipment"]

    category = None
    for item in all_items:
        if item.get("category"):
            category = item["category"]
            break

    if category is None:
        pytest.skip("Aucun équipement avec une catégorie définie")

    response = await async_client.get(f"/api/srd/equipment?category={category}")
    assert response.status_code == 200
    data = response.json()
    assert data["total"] > 0
    for item in data["equipment"]:
        assert item.get("category") == category


@pytest.mark.asyncio
async def test_get_equipment_valid(async_client):
    """Récupération d'un équipement par ID valide."""
    list_resp = await async_client.get("/api/srd/equipment")
    first_id = list_resp.json()["equipment"][0]["id"]

    response = await async_client.get(f"/api/srd/equipment/{first_id}")
    assert response.status_code == 200
    assert response.json()["id"] == first_id


@pytest.mark.asyncio
async def test_get_equipment_not_found(async_client):
    """404 pour un équipement inexistant."""
    response = await async_client.get("/api/srd/equipment/objet_inconnu")
    assert response.status_code == 404
