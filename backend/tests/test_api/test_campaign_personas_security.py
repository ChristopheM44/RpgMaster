"""Sécurité de GET /campaigns/{id}/personas : pas de fuite de champs GM-only.

Cet endpoint n'a aucun consommateur frontend mais reste accessible sans auth
dédiée ; il doit donc retourner une vue player-safe (sans ``secrets``,
``motivations.hidden`` ni ``quest_hooks``), à l'inverse de ``/gm-dossier`` qui
reste un outil MJ légitime et expose ces champs par design.
"""

from __future__ import annotations

import pytest

from app.models.campaign_dossier import CampaignDossier

NPC_WITH_SECRETS = {
    "id": "npc_vael",
    "name": "Vael",
    "archetype": "mentor",
    "short_description": "Un vieux sage qui en sait plus qu'il ne le dit.",
    "persona_type": "npc",
    "importance": "standard",
    "attitude_default": "friendly",
    "motivations": {
        "visible": ["Aider les voyageurs"],
        "hidden": ["Protège un artefact maudit caché sous le temple"],
        "fears": ["Que le secret soit découvert"],
    },
    "secrets": ["Vael a tué son frère il y a 30 ans"],
    "quest_hooks": ["Vael cherche quelqu'un pour récupérer l'artefact"],
    "catchphrases": ["Le temps révèle toujours la vérité..."],
}


@pytest.mark.asyncio
async def test_get_campaign_personas_filters_gm_only_fields(async_client, db_session):
    campaign_resp = await async_client.post(
        "/api/campaigns",
        json={"name": "Campagne des secrets", "description": ""},
    )
    assert campaign_resp.status_code == 201
    campaign_id = campaign_resp.json()["id"]

    db_session.add(
        CampaignDossier(
            id="dossier-personas-security-test",
            campaign_id=campaign_id,
            gm_dossier={
                "narrative_arc": "Arc secret.",
                "chapters": [],
                "important_npcs": [NPC_WITH_SECRETS],
            },
        )
    )
    await db_session.commit()

    response = await async_client.get(f"/api/campaigns/{campaign_id}/personas")

    assert response.status_code == 200
    body = response.json()

    # La persona a bien été chargée (sinon les assertions d'absence ci-dessous
    # passeraient trivialement sur une liste vide).
    assert body["counts"]["npcs"] == 1
    npc = body["npcs"][0]
    assert npc["id"] == "npc_vael"
    assert npc["name"] == "Vael"
    assert npc["motivations"]["visible"] == ["Aider les voyageurs"]
    assert npc["catchphrases"] == ["Le temps révèle toujours la vérité..."]

    # Les champs GM-only ne doivent plus apparaître dans la réponse.
    assert "secrets" not in npc
    assert "quest_hooks" not in npc
    assert "hidden" not in npc["motivations"]


@pytest.mark.asyncio
async def test_get_campaign_gm_dossier_still_exposes_secrets(async_client, db_session):
    """Contrôle négatif : l'endpoint MJ /gm-dossier garde son comportement legacy."""
    campaign_resp = await async_client.post(
        "/api/campaigns",
        json={"name": "Campagne des secrets MJ", "description": ""},
    )
    assert campaign_resp.status_code == 201
    campaign_id = campaign_resp.json()["id"]

    db_session.add(
        CampaignDossier(
            id="dossier-gm-dossier-control-test",
            campaign_id=campaign_id,
            gm_dossier={
                "narrative_arc": "Arc secret.",
                "chapters": [],
                "important_npcs": [NPC_WITH_SECRETS],
            },
        )
    )
    await db_session.commit()

    response = await async_client.get(f"/api/campaigns/{campaign_id}/gm-dossier")

    assert response.status_code == 200
    body = response.json()
    npc = body["gm_dossier"]["important_npcs"][0]
    assert npc["secrets"] == ["Vael a tué son frère il y a 30 ans"]
    assert npc["motivations"]["hidden"] == ["Protège un artefact maudit caché sous le temple"]
