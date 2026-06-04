from __future__ import annotations

import asyncio
import json
import socket

import pytest
from sqlalchemy import select

from app.models.campaign_dossier import CampaignDossier
from app.models.game_state import GameState
from app.models.message import Message
from app.security_url import UnsafeUrlError, validate_public_http_url
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
    def _chapters(self, count: int = 2) -> list[dict]:
        return [
            {
                "id": f"chapter_{idx}",
                "num": campaign_dossier_service._roman(idx),
                "title": f"Chapitre {idx}",
                "state": "active" if idx == 1 else "planned",
                "sessions": 0,
                "summary": f"Résumé public {idx}.",
            }
            for idx in range(1, count + 1)
        ]

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
                        "opening_scene": {
                            "region": "Hinterland",
                            "place": "Vieille route",
                            "venue": None,
                            "description": "La vieille route disparaît dans une brume basse.",
                            "present_npcs": [
                                {
                                    "id": "bram",
                                    "name": "Bram",
                                    "description": (
                                        "Bram serre une lanterne contre sa poitrine, voix rauque "
                                        "et bottes couvertes de boue froide."
                                    ),
                                    "action_hint": "Lui demander ce qu'il a vu dans la brume.",
                                    "opening_intent": (
                                        "Il veut être cru sans révéler tout de suite "
                                        "qui l'a menacé."
                                    ),
                                }
                            ],
                            "visible_clues": [
                                {
                                    "id": "lanterne_bleue",
                                    "name": "Une lanterne bleue",
                                    "description": "Une lueur bleue pulse au bord de la route.",
                                }
                            ],
                            "exits": [],
                            "time_of_day": "morning",
                            "weather": "Brume",
                        },
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

    async def normalize_import_source(self, source):
        return {
            "title": source.get("title") or "Source",
            "summary_private": "Résumé privé.",
            "public_hook": "Accroche publique.",
            "locations": [],
            "npcs": [],
            "secrets": [],
            "quests": [],
            "encounters": [],
        }

    async def forge_outline(self, campaign, brief, options, source_notes):
        count = int(options.get("chapter_count") or 2)
        return {
            "player_contract": {
                "title": brief.get("title") or campaign["name"],
                "pitch_public": "Une aventure découpée en chapitres.",
                "tones": ["Mystère"],
                "duration": f"{count} chapitres",
                "hook": "Une piste attire les héros.",
                "visible_chapters": self._chapters(count),
                "known_objectives": ["Suivre la piste."],
                "played_summary": "",
            },
            "active_chapter_id": "chapter_1",
        }

    async def forge_chapter(
        self,
        campaign,
        player_contract,
        visible_chapter,
        chapter_index,
        chapter_total,
        source_notes,
        options,
    ):
        return {
            "id": visible_chapter["id"],
            "title": visible_chapter["title"],
            "state": visible_chapter["state"],
            "objective": f"Objectif privé {chapter_index}.",
            "stakes": f"Enjeux {chapter_index}.",
            "initial_state": f"État initial {chapter_index}.",
            "opening_scene": {
                "region": "Côte",
                "place": f"Lieu {chapter_index}",
                "venue": None,
                "description": "La pluie frappe les pierres et l'air sent le sel froid.",
                "present_npcs": [],
                "visible_clues": [],
                "exits": [],
                "time_of_day": "morning",
                "weather": "Pluie",
            },
            "key_locations": [f"Lieu {chapter_index}"],
            "involved_npcs": [],
            "clues": [],
            "secrets": [f"Secret {chapter_index}"],
            "complications": [],
            "possible_exits": [],
            "indicative_dcs": [],
            "possible_srd_encounters": [],
        }

    async def forge_global_indexes(
        self,
        campaign,
        brief,
        options,
        player_contract,
        chapters,
        source_notes,
    ):
        return {
            "narrative_arc": "Arc privé global.",
            "important_npcs": [],
            "bestiary": [],
            "companion_seeds": [],
            "locations": [{"name": chapter["title"]} for chapter in chapters],
            "factions": [],
            "secrets": [],
            "revelations": [],
            "fronts": [],
            "quests": [],
            "complications": [],
            "clues": [],
            "light_mechanics": [],
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
    from app.agents.gm_agent import _FALLBACK_NARRATION
    from app.agents.schemas import GMResponse
    from app.api import routes_game

    async def fallback_open_scene(self, **kwargs):
        return GMResponse(narration=_FALLBACK_NARRATION, actions=[])

    monkeypatch.setattr(campaign_dossier_service, "CampaignForgeAgent", DummyForgeAgent)
    monkeypatch.setattr(routes_game.GMAgent, "open_scene", fallback_open_scene)


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
    return {
        "campaign_id": campaign_id,
        "contract": contract,
        "session_id": campaign["session_ids"][0],
    }


async def _poll_forge_job(async_client, campaign_id: str, job_id: str) -> dict:
    for _ in range(50):
        response = await async_client.get(f"/api/campaigns/{campaign_id}/forge-draft/jobs/{job_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["status"] in {"completed", "failed"}:
            return payload
        await asyncio.sleep(0.02)
    raise AssertionError("Forge job did not finish")


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
async def test_import_source_uses_configured_source_max_chars(
    async_client,
    db_session,
    monkeypatch,
):
    monkeypatch.setattr(campaign_dossier_service, "get_source_max_chars", lambda: 12)
    campaign = await _create_campaign(async_client)

    response = await async_client.post(
        f"/api/campaigns/{campaign['id']}/import-source",
        json={
            "kind": "text",
            "title": "Long markdown",
            "content": "abcdefghijklmnop",
        },
    )

    assert response.status_code == 200
    result = await db_session.execute(
        select(CampaignDossier).where(CampaignDossier.campaign_id == campaign["id"])
    )
    dossier = result.scalar_one()
    assert dossier.import_sources[0]["content"] == "abcdefghijk…"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "url",
    [
        "file:///etc/passwd",
        "ftp://example.com/adventure.txt",
        "http://localhost/adventure",
        "http://127.0.0.1/adventure",
        "http://[::1]/adventure",
        "http://10.0.0.1/adventure",
        "http://user:pass@example.com/adventure",
    ],
)
async def test_import_source_rejects_unsafe_urls(async_client, url: str):
    campaign = await _create_campaign(async_client)

    response = await async_client.post(
        f"/api/campaigns/{campaign['id']}/import-source",
        json={"kind": "url", "url": url},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_public_url_validator_rejects_dns_to_private_ip(monkeypatch):
    def fake_getaddrinfo(*args, **kwargs):
        return [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                6,
                "",
                ("192.168.1.42", 443),
            )
        ]

    monkeypatch.setattr(socket, "getaddrinfo", fake_getaddrinfo)

    with pytest.raises(UnsafeUrlError):
        await validate_public_http_url("https://campaign.example/source")


@pytest.mark.asyncio
async def test_import_source_fetches_public_url_without_redirects(async_client, monkeypatch):
    campaign = await _create_campaign(async_client)
    captured: dict[str, object] = {}

    async def fake_validate(url: str) -> str:
        captured["validated_url"] = url
        return url

    class DummyResponse:
        status_code = 200
        is_redirect = False
        content = b"<html><body><h1>Aventure publique</h1></body></html>"
        encoding = "utf-8"

        def raise_for_status(self) -> None:
            return None

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            captured["client_kwargs"] = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str) -> DummyResponse:
            captured["fetched_url"] = url
            return DummyResponse()

    monkeypatch.setattr(campaign_dossier_service, "validate_public_http_url", fake_validate)
    monkeypatch.setattr(campaign_dossier_service.httpx, "AsyncClient", DummyAsyncClient)

    response = await async_client.post(
        f"/api/campaigns/{campaign['id']}/import-source",
        json={"kind": "url", "url": "https://campaign.example/source"},
    )

    assert response.status_code == 200
    assert response.json()["source"]["title"] == "https://campaign.example/source"
    assert captured["validated_url"] == "https://campaign.example/source"
    assert captured["fetched_url"] == "https://campaign.example/source"
    assert captured["client_kwargs"] == {"timeout": 5.0, "follow_redirects": False}


@pytest.mark.asyncio
async def test_import_source_rejects_redirects(async_client, monkeypatch):
    campaign = await _create_campaign(async_client)

    async def fake_validate(url: str) -> str:
        return url

    class DummyResponse:
        status_code = 302
        is_redirect = True
        content = b""
        encoding = "utf-8"

        def raise_for_status(self) -> None:
            return None

    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str) -> DummyResponse:
            return DummyResponse()

    monkeypatch.setattr(campaign_dossier_service, "validate_public_http_url", fake_validate)
    monkeypatch.setattr(campaign_dossier_service.httpx, "AsyncClient", DummyAsyncClient)

    response = await async_client.post(
        f"/api/campaigns/{campaign['id']}/import-source",
        json={"kind": "url", "url": "https://campaign.example/source"},
    )

    assert response.status_code == 422


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
async def test_forge_draft_persists_campaign_starting_level(async_client):
    campaign = await _create_campaign(async_client)
    response = await async_client.post(
        f"/api/campaigns/{campaign['id']}/forge-draft",
        json={
            "brief": {"title": "Les Brumes du Hinterland"},
            "options": {"starting_level": 3},
        },
    )
    assert response.status_code == 200

    detail = await async_client.get(f"/api/campaigns/{campaign['id']}")
    assert detail.status_code == 200
    assert detail.json()["starting_level"] == 3


@pytest.mark.asyncio
async def test_forge_job_preserves_all_detected_chapters(async_client):
    campaign = await _create_campaign(async_client)

    started = await async_client.post(
        f"/api/campaigns/{campaign['id']}/forge-draft/jobs",
        json={
            "brief": {"title": "Grande campagne"},
            "options": {"chapter_count": 18},
        },
    )

    assert started.status_code == 200
    job = await _poll_forge_job(async_client, campaign["id"], started.json()["job_id"])
    assert job["status"] == "completed"
    assert job["total_steps"] == 20
    assert len(job["player_contract"]["visible_chapters"]) == 18

    gm_response = await async_client.get(f"/api/campaigns/{campaign['id']}/gm-dossier")
    assert gm_response.status_code == 200
    gm_chapters = gm_response.json()["gm_dossier"]["chapters"]
    public_ids = [chapter["id"] for chapter in job["player_contract"]["visible_chapters"]]
    private_ids = [chapter["id"] for chapter in gm_chapters]
    assert len(gm_chapters) == 18
    assert private_ids == public_ids


def test_resolve_duration_scratch_scope_is_authoritative():
    svc = campaign_dossier_service
    base = {"narrative_structure": "epic_5_acts"}
    # En scratch / 5 actes, le scope dérive la durée et écrase la valeur du LLM.
    assert (
        svc._resolve_duration({"duration": "9 sessions"}, {}, {**base, "scope": "one-shot"}, 1)
        == "1 session"
    )
    assert svc._resolve_duration({}, {}, {**base, "scope": "mini-chronique"}, 3) == "3-5 sessions"
    assert (
        svc._resolve_duration({}, {}, {**base, "scope": "chronique longue"}, 5) == "6-10 sessions"
    )


def test_resolve_duration_import_derives_from_chapter_count():
    svc = campaign_dossier_service
    options = {"narrative_structure": "adaptive", "scope": "one-shot"}
    # En import / adaptive, le scope est ignoré : la durée suit le nombre de chapitres.
    assert svc._resolve_duration({}, {}, options, 8) == svc._duration_from_chapter_count(8)
    assert svc._resolve_duration({}, {}, options, 8) == "8-12 sessions"


def test_resolve_duration_preserves_existing_when_no_options():
    svc = campaign_dossier_service
    # Chemin de re-sanitisation (10 appelants avec options=None) : durée stockée préservée.
    assert svc._resolve_duration({"duration": "4 sessions"}, {}, None, 3) == "4 sessions"
    # Scope inconnu en 5 actes → repli sur le défaut, pas de crash.
    unknown = {"narrative_structure": "epic_5_acts", "scope": "saga"}
    assert svc._resolve_duration({}, {}, unknown, 2) == "3-5 sessions"


@pytest.mark.asyncio
async def test_forge_job_one_shot_scope_yields_single_chapter_and_session(async_client):
    campaign = await _create_campaign(async_client)

    started = await async_client.post(
        f"/api/campaigns/{campaign['id']}/forge-draft/jobs",
        json={
            "brief": {"title": "Le Phare englouti"},
            "options": {
                "scope": "one-shot",
                "narrative_structure": "epic_5_acts",
                "chapter_count": 1,
            },
        },
    )

    assert started.status_code == 200
    job = await _poll_forge_job(async_client, campaign["id"], started.json()["job_id"])
    assert job["status"] == "completed"
    contract = job["player_contract"]
    # scope=one-shot dérive la durée (override du "1 chapitres" renvoyé par l'agent).
    assert contract["duration"] == "1 session"
    assert len(contract["visible_chapters"]) == 1


@pytest.mark.asyncio
async def test_forge_job_records_phase_retries(async_client, monkeypatch):
    monkeypatch.setattr(campaign_dossier_service, "FORGE_PHASE_RETRY_BASE_DELAY", 0.0)

    class FlakyForgeAgent(DummyForgeAgent):
        attempts = 0

        async def forge_outline(self, campaign, brief, options, source_notes):
            type(self).attempts += 1
            if type(self).attempts == 1:
                raise ValueError("JSON tronqué")
            return await super().forge_outline(campaign, brief, options, source_notes)

    monkeypatch.setattr(campaign_dossier_service, "CampaignForgeAgent", FlakyForgeAgent)
    campaign = await _create_campaign(async_client)

    started = await async_client.post(
        f"/api/campaigns/{campaign['id']}/forge-draft/jobs",
        json={"brief": {"title": "Retry visible"}, "options": {"chapter_count": 2}},
    )

    assert started.status_code == 200
    job = await _poll_forge_job(async_client, campaign["id"], started.json()["job_id"])
    assert job["status"] == "completed"
    assert job["retry_count"] >= 1
    assert any(
        event["type"] == "phase_retry" and "JSON tronqué" in event["error"]
        for event in job["events"]
    )


@pytest.mark.asyncio
async def test_legacy_forge_draft_does_not_fallback_when_sources_are_imported(
    async_client,
    monkeypatch,
):
    class FailingForgeAgent(DummyForgeAgent):
        async def forge_dossier(self, campaign, brief, options, import_sources):
            raise ValueError("JSON tronqué")

    monkeypatch.setattr(campaign_dossier_service, "CampaignForgeAgent", FailingForgeAgent)
    campaign = await _create_campaign(async_client)
    imported = await async_client.post(
        f"/api/campaigns/{campaign['id']}/import-source",
        json={"kind": "text", "title": "Source longue", "content": "Chapitre 1"},
    )
    assert imported.status_code == 200

    response = await async_client.post(
        f"/api/campaigns/{campaign['id']}/forge-draft",
        json={"brief": {"title": "Source fragile"}, "options": {}},
    )

    assert response.status_code == 502
    gm_response = await async_client.get(f"/api/campaigns/{campaign['id']}/gm-dossier")
    assert gm_response.status_code == 200
    assert gm_response.json()["generation_status"] == "failed"
    assert len(gm_response.json()["gm_dossier"]["chapters"]) == 1
    assert gm_response.json()["gm_dossier"]["chapters"][0]["title"] == "Prologue"


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
async def test_gm_prompt_context_contains_private_chapter_and_npcs(
    async_client,
    db_session,
):
    forged = await _forge_and_validate(async_client)
    session_id = forged["session_id"]

    public_context = await campaign_dossier_service.compile_campaign_context_for_session(
        session_id,
        db_session,
    )
    private_context = await campaign_dossier_service.build_gm_prompt_context(
        session_id,
        db_session,
        {"gm_scene_state": {"scene_1": {"goal": "Comprendre la brume."}}},
    )

    public_serialized = json.dumps(public_context, ensure_ascii=False)
    private_serialized = json.dumps(private_context, ensure_ascii=False)

    assert public_context is not None
    assert SECRET not in public_serialized
    assert private_context["active_chapter"]["secrets"] == [SECRET]
    assert any(npc["name"] == "Bram" for npc in private_context["important_npcs"])
    assert private_context["gm_scene_state"]["scene_1"]["goal"] == "Comprendre la brume."
    assert SECRET in private_serialized


@pytest.mark.asyncio
async def test_personas_endpoint_returns_dossier_personas(async_client):
    """L'endpoint /personas liste les personas de la campagne par type."""
    forged = await _forge_and_validate(async_client)
    response = await async_client.get(f"/api/campaigns/{forged['campaign_id']}/personas")

    assert response.status_code == 200
    data = response.json()
    assert data["campaign_id"] == forged["campaign_id"]
    # 3 buckets toujours présents (même vides)
    assert "npcs" in data
    assert "monsters" in data
    assert "companions" in data
    assert "counts" in data
    # Le DummyForgeAgent retourne `important_npcs: [{"name": "Bram", "secret": ...}]`
    # qui est coerced en NPCPersona light via _coerce_legacy_npc_dict
    assert data["counts"]["npcs"] >= 1
    bram = next((n for n in data["npcs"] if n["name"] == "Bram"), None)
    assert bram is not None
    assert bram["persona_type"] == "npc"
    assert bram["importance"] == "light"  # coerced from legacy format


@pytest.mark.asyncio
async def test_forge_dossier_npc_descriptions_are_roleplay_grade(async_client):
    forged = await _forge_and_validate(async_client)
    response = await async_client.get(f"/api/campaigns/{forged['campaign_id']}/gm-dossier")

    assert response.status_code == 200
    npc = response.json()["gm_dossier"]["chapters"][0]["opening_scene"]["present_npcs"][0]
    assert "Bram serre une lanterne" in npc["description"]
    assert "voix rauque" in npc["description"]
    assert npc["action_hint"] == "Lui demander ce qu'il a vu dans la brume."
    assert "menacé" in npc["opening_intent"]
    assert len(npc["description"]) <= 260
    assert len(npc["opening_intent"]) <= 200


@pytest.mark.asyncio
async def test_start_game_injects_minimal_campaign_context(async_client, db_session):
    forged = await _forge_and_validate(async_client)
    campaign_id = forged["campaign_id"]
    session_id = forged["session_id"]

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
    assert game_state.state_data["quests"][0]["id"] == "campaign_opening"
    assert "Des brumes coupent les routes" in game_state.state_data["quests"][0]["summary"]
    assert "Une lueur bleue" not in game_state.state_data["quests"][0]["summary"]
    assert game_state.state_data["current_scene"]["scene_id"] == "scene_vieille_route"
    assert len(game_state.state_data["current_scene"]["pois"]) >= 3
    assert "bram" in game_state.state_data["npc_states"]
    assert game_state.state_data["world_maps"]["region_map"] is None

    messages = await db_session.execute(
        select(Message).where(Message.session_id == session_id).order_by(Message.created_at.desc())
    )
    opening = messages.scalars().first()
    assert opening is not None
    assert "La partie commence" not in opening.content
    assert "Le rideau se lève" not in opening.content
    # Le hook est l'accroche publique jouable : la narration explique pourquoi
    # le groupe est là, puis montre le lieu et l'affordance NPC.
    assert "Une lueur bleue attire les voyageurs" in opening.content
    assert "Que faites-vous ?" in opening.content

    state_response = await async_client.get(f"/api/game/{session_id}/state")
    assert state_response.status_code == 200
    payload = state_response.json()
    assert payload["region_map"]["current_node_id"] == "vieille_route"
    assert payload["current_scene"]["scene_id"] == "scene_vieille_route"


@pytest.mark.asyncio
async def test_initial_campaign_session_ignores_stale_played_canon(async_client, db_session):
    forged = await _forge_and_validate(async_client)
    campaign_id = forged["campaign_id"]

    synth = await async_client.post(
        f"/api/campaigns/{campaign_id}/synthesize-canon",
        json={
            "game_state": {
                "canon_event": {
                    "rolling_summary": "Une ancienne session place déjà le groupe ailleurs.",
                    "established_fact": "Ancien fait contaminant.",
                }
            },
            "recent_messages": [],
        },
    )
    assert synth.status_code == 200

    session_id = forged["session_id"]
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

    assert context["played_canon"]["rolling_summary"] == ""
    assert context["continuity"]["played_summary"] == ""
    assert context["player_contract"]["played_summary"] == ""
    assert "ancienne session" not in json.dumps(context, ensure_ascii=False).lower()


@pytest.mark.asyncio
async def test_start_game_without_campaign_uses_ephemeral_maps(async_client, db_session):
    session_resp = await async_client.post("/api/sessions/", json={"name": "Session libre"})
    assert session_resp.status_code == 201
    session_id = session_resp.json()["id"]

    char_resp = await async_client.post(
        "/api/characters/",
        json={**BASE_CHARACTER, "session_id": session_id},
    )
    assert char_resp.status_code == 201

    start = await async_client.post(f"/api/game/{session_id}/start", json={})
    assert start.status_code == 200

    result = await db_session.execute(select(GameState).where(GameState.session_id == session_id))
    game_state = result.scalar_one()
    current_scene_id = game_state.state_data["current_scene"]["scene_id"]
    current_node_id = game_state.state_data["world_maps"]["region_map"]["current_node_id"]
    assert current_scene_id.startswith("scene_")
    assert current_scene_id == f"scene_{current_node_id}"

    state_response = await async_client.get(f"/api/game/{session_id}/state")
    assert state_response.status_code == 200
    payload = state_response.json()
    assert payload["region_map"]["current_node_id"] == current_node_id
    assert payload["city_maps"] == {}


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


# ---------------------------------------------------------------------------
# A5 — Révélation événementielle (record_revealed_secret + survie à la synthèse)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_record_revealed_secret_persists_and_is_idempotent(async_client, db_session):
    forged = await _forge_and_validate(async_client)
    campaign_id = forged["campaign_id"]

    await campaign_dossier_service.record_revealed_secret(
        campaign_id, "Le marchand finance les pillards.", db_session
    )
    # Idempotent : un même secret n'est pas dupliqué.
    await campaign_dossier_service.record_revealed_secret(
        campaign_id, "Le marchand finance les pillards.", db_session
    )

    result = await db_session.execute(
        select(CampaignDossier).where(CampaignDossier.campaign_id == campaign_id)
    )
    dossier = result.scalar_one()
    assert dossier.played_canon["revealed_secrets"] == ["Le marchand finance les pillards."]


@pytest.mark.asyncio
async def test_canon_synthesis_preserves_recorded_revealed_secret(async_client, db_session):
    """Le secret enregistré déterministiquement survit à une passe de synthèse
    LLM qui renvoie revealed_secrets vide (DummyForgeAgent.synthesize_canon)."""
    forged = await _forge_and_validate(async_client)
    campaign_id = forged["campaign_id"]

    await campaign_dossier_service.record_revealed_secret(
        campaign_id, "La relique est une contrefaçon.", db_session
    )

    synth = await async_client.post(
        f"/api/campaigns/{campaign_id}/synthesize-canon",
        json={"game_state": {"canon_event": {}}, "recent_messages": []},
    )
    assert synth.status_code == 200

    await db_session.commit()
    result = await db_session.execute(
        select(CampaignDossier).where(CampaignDossier.campaign_id == campaign_id)
    )
    dossier = result.scalar_one()
    await db_session.refresh(dossier)
    assert "La relique est une contrefaçon." in dossier.played_canon["revealed_secrets"]


# ---------------------------------------------------------------------------
# A6 — Reset canon initial aligné entre les deux compilateurs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gm_prompt_context_resets_canon_on_initial_session(async_client, db_session):
    """build_gm_prompt_context vide played_canon sur la session initiale, comme
    le compilateur public — pas de canon semé par la forge côté MJ non plus."""
    forged = await _forge_and_validate(async_client)
    campaign_id = forged["campaign_id"]
    session_id = forged["session_id"]  # session initiale (session_ids[0])

    # Semer un canon "déjà joué" via synthèse, comme une session antérieure.
    await async_client.post(
        f"/api/campaigns/{campaign_id}/synthesize-canon",
        json={
            "game_state": {
                "canon_event": {
                    "rolling_summary": "Résumé d'une session précédente.",
                    "established_fact": "Fait contaminant.",
                }
            },
            "recent_messages": [],
        },
    )

    private_context = await campaign_dossier_service.build_gm_prompt_context(
        session_id, db_session, None
    )
    # played_canon ne doit pas resurgir côté MJ sur la session initiale.
    played = private_context.get("played_canon", {})
    assert played.get("rolling_summary", "") == ""
    assert played.get("established_facts", []) == []
    assert "session précédente" not in json.dumps(private_context, ensure_ascii=False).lower()
