from __future__ import annotations

import json

import pytest
from sqlalchemy import select

from app.models.game_state import GameState
from app.services import campaign_dossier_service

SECRET = "SECRET_NEVER_LEAK"

BASE_CHARACTER = {
    "name": "Mira",
    "species": "human",
    "char_class": "fighter",
    "ability_scores": {"str": 15, "dex": 12, "con": 14, "int": 10, "wis": 11, "cha": 13},
    "hp_current": 12,
    "hp_max": 12,
}


class DummyForgeAgent:
    async def forge_dossier(self, campaign, brief, options, import_sources):
        title = brief.get("title") or campaign["name"]
        return {
            "player_contract": {
                "title": title,
                "pitch_public": "Des brumes coupent les routes du Hinterland.",
                "tones": ["Mystère", "Exploration"],
                "duration": "3 sessions",
                "hook": "Une lueur bleue attire les voyageurs vers la vieille mine.",
                "visible_chapters": [
                    {
                        "id": "chapter_1",
                        "num": "I",
                        "title": "La vieille route",
                        "state": "active",
                        "sessions": 0,
                        "summary": "Le groupe suit les premières rumeurs.",
                    },
                    {
                        "id": "chapter_2",
                        "num": "II",
                        "title": "La mine close",
                        "state": "planned",
                        "sessions": 0,
                        "summary": "La piste mène sous la colline.",
                    },
                ],
                "known_objectives": ["Comprendre l'origine des brumes."],
                "played_summary": "",
            },
            "gm_dossier": {
                "narrative_arc": "Le capitaine local protège un culte.",
                "chapters": [
                    {
                        "id": "chapter_1",
                        "title": "La vieille route",
                        "state": "active",
                        "objective": "Laisser le groupe choisir ses premiers alliés.",
                        "stakes": "Les disparitions continuent.",
                        "initial_state": "Une route noyée de brume.",
                        "key_locations": ["Vieille route"],
                        "involved_npcs": ["Bram"],
                        "clues": ["Une lanterne bleue"],
                        "secrets": [SECRET],
                        "complications": ["Un témoin ment"],
                        "possible_exits": ["Négocier", "Explorer"],
                        "indicative_dcs": [{"label": "Pister", "ability": "wis", "dc": 13}],
                        "possible_srd_encounters": ["bandit"],
                    },
                    {
                        "id": "chapter_2",
                        "title": "La mine close",
                        "state": "planned",
                        "secrets": [f"{SECRET}_FUTURE"],
                    },
                ],
                "important_npcs": [{"name": "Bram", "secret": SECRET}],
                "locations": [{"name": "Mine", "secret": SECRET}],
                "factions": [],
                "secrets": [SECRET],
                "revelations": [],
                "fronts": [],
                "quests": [{"id": "brumes", "title": "Les brumes", "public": True}],
                "complications": [],
                "clues": [],
                "light_mechanics": [],
            },
            "played_canon": {
                "established_facts": [],
                "player_decisions": [],
                "quests": [],
                "npc_relationships": [],
                "revealed_secrets": [],
                "plan_changes": [],
                "rolling_summary": "",
                "chapter_progression": [],
            },
            "active_chapter_id": "chapter_1",
        }

    async def synthesize_canon(
        self,
        player_contract,
        gm_dossier,
        played_canon,
        game_state,
        recent_messages,
    ):
        event = game_state.get("canon_event", {})
        return {
            "established_facts": [event.get("established_fact", "La brume est réelle.")],
            "player_decisions": [event.get("player_decision", "Le groupe avance.")],
            "quests": game_state.get("quests", []),
            "npc_relationships": [],
            "revealed_secrets": [],
            "plan_changes": [event.get("plan_change", "Le plan prévu change.")],
            "rolling_summary": event.get("rolling_summary", "Le groupe a changé le cours prévu."),
            "chapter_progression": [
                {"id": "chapter_1", "state": "done", "sessions": 1, "summary": "Route sécurisée."},
                {"id": "chapter_2", "state": "active", "sessions": 0, "summary": "La mine attend."},
            ],
        }


@pytest.fixture(autouse=True)
def dummy_forge_agent(monkeypatch):
    monkeypatch.setattr(campaign_dossier_service, "CampaignForgeAgent", DummyForgeAgent)


async def _create_campaign(async_client):
    response = await async_client.post(
        "/api/campaigns",
        json={"name": "Les Brumes du Hinterland", "description": "Brief public"},
    )
    assert response.status_code == 201
    return response.json()


async def _forge_and_validate(async_client) -> dict:
    campaign = await _create_campaign(async_client)
    campaign_id = campaign["id"]
    draft = await async_client.post(
        f"/api/campaigns/{campaign_id}/forge-draft",
        json={"brief": {"title": "Les Brumes du Hinterland"}, "options": {}},
    )
    assert draft.status_code == 200
    contract = draft.json()["player_contract"]
    validated = await async_client.post(
        f"/api/campaigns/{campaign_id}/validate-contract",
        json={"player_contract": contract},
    )
    assert validated.status_code == 200
    return {"campaign_id": campaign_id, "contract": contract}


@pytest.mark.asyncio
async def test_campaign_dossier_public_endpoints_never_leak_private_blocks(async_client):
    campaign = await _create_campaign(async_client)
    campaign_id = campaign["id"]

    imported = await async_client.post(
        f"/api/campaigns/{campaign_id}/import-source",
        json={
            "kind": "text",
            "title": "Aventure privée",
            "content": f"Le grand twist est {SECRET}.",
        },
    )
    assert imported.status_code == 200
    assert SECRET not in imported.text

    draft = await async_client.post(
        f"/api/campaigns/{campaign_id}/forge-draft",
        json={"brief": {"title": "Les Brumes du Hinterland"}, "options": {}},
    )
    assert draft.status_code == 200
    assert SECRET not in draft.text

    contract = draft.json()["player_contract"]
    validated = await async_client.post(
        f"/api/campaigns/{campaign_id}/validate-contract",
        json={"player_contract": contract},
    )
    assert validated.status_code == 200
    assert SECRET not in validated.text

    scenario = await async_client.get(f"/api/campaigns/{campaign_id}/scenario")
    assert scenario.status_code == 200
    assert SECRET not in scenario.text

    campaign_detail = await async_client.get(f"/api/campaigns/{campaign_id}")
    assert campaign_detail.status_code == 200
    assert SECRET not in campaign_detail.text

    campaign_list = await async_client.get("/api/campaigns")
    assert campaign_list.status_code == 200
    assert SECRET not in campaign_list.text


@pytest.mark.asyncio
async def test_campaign_scenario_returns_player_timeline(async_client):
    forged = await _forge_and_validate(async_client)
    response = await async_client.get(f"/api/campaigns/{forged['campaign_id']}/scenario")

    assert response.status_code == 200
    data = response.json()
    assert data["generation_status"] == "validated"
    assert data["player_contract"]["title"] == "Les Brumes du Hinterland"
    assert data["timeline"][0]["title"] == "La vieille route"
    assert data["current_chapter"]["id"] == "chapter_1"
    assert data["known_objectives"] == ["Comprendre l'origine des brumes."]
    assert "gm_dossier" not in json.dumps(data)
    assert "import_sources" not in json.dumps(data)


@pytest.mark.asyncio
async def test_campaign_gm_dossier_endpoint_exposes_author_notes_only(async_client):
    forged = await _forge_and_validate(async_client)
    response = await async_client.get(f"/api/campaigns/{forged['campaign_id']}/gm-dossier")

    assert response.status_code == 200
    data = response.json()
    serialized = json.dumps(data, ensure_ascii=False)
    assert data["campaign_id"] == forged["campaign_id"]
    assert data["generation_status"] == "validated"
    assert data["active_chapter_id"] == "chapter_1"
    assert data["gm_dossier"]["chapters"][0]["secrets"] == [SECRET]
    assert SECRET in serialized
    assert "import_sources" not in serialized


@pytest.mark.asyncio
async def test_start_game_injects_minimal_campaign_context(async_client, db_session):
    forged = await _forge_and_validate(async_client)
    campaign_id = forged["campaign_id"]

    session_resp = await async_client.post("/api/sessions/", json={"name": "Session 1"})
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    attach = await async_client.post(
        f"/api/campaigns/{campaign_id}/sessions",
        json={"session_id": session_id},
    )
    assert attach.status_code == 200

    char_resp = await async_client.post(
        "/api/characters/",
        json={**BASE_CHARACTER, "session_id": session_id},
    )
    assert char_resp.status_code == 201

    start = await async_client.post(f"/api/game/{session_id}/start", json={})
    assert start.status_code == 200

    result = await db_session.execute(select(GameState).where(GameState.session_id == session_id))
    game_state = result.scalar_one()
    context = game_state.state_data["campaign_context"]

    assert context["campaign_id"] == campaign_id
    assert context["active_chapter"]["id"] == "chapter_1"
    assert context["played_canon"]["rolling_summary"] == ""
    serialized = json.dumps(context, ensure_ascii=False)
    assert "gm_dossier" not in serialized
    assert "import_sources" not in serialized
    assert f"{SECRET}_FUTURE" not in serialized
    assert SECRET not in serialized


@pytest.mark.asyncio
async def test_synthesize_canon_updates_player_summary_and_chapter_progress(async_client):
    forged = await _forge_and_validate(async_client)
    campaign_id = forged["campaign_id"]

    response = await async_client.post(
        f"/api/campaigns/{campaign_id}/synthesize-canon",
        json={
            "game_state": {
                "canon_event": {
                    "established_fact": "Le groupe a épargné le témoin.",
                    "player_decision": "Bram devient un allié.",
                    "plan_change": "Le témoin ne meurt pas comme prévu.",
                    "rolling_summary": "Le groupe a sauvé Bram et changé la piste.",
                },
                "quests": [
                    {
                        "id": "brumes",
                        "title": "Les brumes",
                        "summary": "Bram connaît une piste.",
                        "status": "active",
                    }
                ],
            },
            "recent_messages": [],
        },
    )
    assert response.status_code == 200

    scenario = await async_client.get(f"/api/campaigns/{campaign_id}/scenario")
    data = scenario.json()
    assert data["played_summary"] == "Le groupe a sauvé Bram et changé la piste."
    assert data["timeline"][0]["state"] == "done"
    assert data["timeline"][1]["state"] == "active"
    assert data["quests"][0]["title"] == "Les brumes"
