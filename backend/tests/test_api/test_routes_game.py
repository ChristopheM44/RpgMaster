from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest


def _action_by_type(actions, action_type):
    return next((a for a in actions if a.type == action_type), None)


def test_opening_response_uses_opening_scene_as_physical_scene() -> None:
    """L'ouverture matérialise seulement la scène jouable explicite."""
    from app.api.routes_game import _opening_response

    active = SimpleNamespace(state_data={"characters": {"thorvald": {"name": "Thorvald"}}})
    campaign_context = {
        "active_chapter": {
            "key_locations": ["Goldenthrone"],
            "initial_state": (
                "Wakanga engage le groupe à Goldenthrone pour voyager vers Port Nyanzaru."
            ),
            "involved_npcs": ["Wakanga O'tamu"],
            "clues": ["La licence de marchandage cachée dans le module."],
            "opening_scene": {
                "region": "Chult",
                "place": "Port Nyanzaru",
                "venue": "Auberge du Poisson Grillé",
                "description": "Azaka observe la salle commune depuis le comptoir.",
                "present_npcs": [
                    {"id": "azaka", "name": "Azaka", "description": "Guide présente."}
                ],
                "visible_clues": [
                    {
                        "id": "carte_tachee",
                        "name": "Carte tachée",
                        "description": "Une carte humide dépasse d'une sacoche.",
                    }
                ],
                "time_of_day": "dusk",
                "weather": "Chaleur humide",
            },
        },
        "player_contract": {
            "hook": "Wakanga engage le groupe pour Port Nyanzaru.",
            "known_objectives": ["Trouver la source de la malédiction"],
        },
    }

    response = _opening_response(active, campaign_context=campaign_context)

    journal = _action_by_type(response.actions, "journal_update")
    assert journal is not None
    assert journal.params["location_region"] == "Chult"
    assert journal.params["location_place"] == "Port Nyanzaru"
    assert journal.params["location_venue"] == "Auberge du Poisson Grillé"
    assert journal.params["time_of_day"] == "dusk"
    assert journal.params["weather"] == "Chaleur humide"

    scene = _action_by_type(response.actions, "scene_layout")
    assert scene is not None
    assert "Azaka observe" in scene.params["description"]
    assert "Wakanga engage" not in scene.params["description"]

    poi_ids = [poi["id"] for poi in scene.params["pois"]]
    assert "situation_initiale" not in poi_ids
    assert "source_information" not in poi_ids
    assert "azaka" in poi_ids
    assert "wakanga_o_tamu" not in poi_ids
    assert "carte_tachee" in poi_ids
    # Le briefing public (known_objectives) doit être visible : le joueur sait
    # pourquoi son personnage est là dès l'ouverture.
    assert "Mission confiée" in response.narration
    assert "Trouver la source de la malédiction" in response.narration
    assert "première scène jouable" not in response.narration
    assert "Un cap possible se dessine" not in response.narration
    assert "Vous pouvez" not in response.narration
    assert response.narration.endswith("Que faites-vous ?")
    assert any(
        exit_["leads_to"] == "trouver_source_malediction"
        for exit_ in scene.params["exits"]
    )


def test_opening_response_does_not_add_route_exit_inside_square() -> None:
    from app.api.routes_game import _opening_response

    active = SimpleNamespace(state_data={"characters": {"vel": {"name": "Vel"}}})
    campaign_context = {
        "active_chapter": {
            "opening_scene": {
                "region": "Cité d'Azur",
                "place": "Place du Marché Central",
                "venue": "Pavillon des Festivités",
                "description": "La foule du festival s'agite sur les pavés autour du pavillon.",
                "present_npcs": [],
                "visible_clues": [],
            },
        },
        "player_contract": {
            "known_objectives": ["Rejoindre les quais"],
        },
    }

    response = _opening_response(active, campaign_context=campaign_context)

    scene = _action_by_type(response.actions, "scene_layout")
    assert scene is not None
    assert all(exit_["id"] != "prendre_route_objectif" for exit_ in scene.params["exits"])


def test_opening_response_does_not_derive_weather_and_time_from_initial_state() -> None:
    """Le moment et la météo viennent de opening_scene, pas du contexte."""
    from app.api.routes_game import _opening_response

    active = SimpleNamespace(state_data={"characters": {}})
    campaign_context = {
        "active_chapter": {
            "key_locations": ["Crypte oubliée"],
            "initial_state": "À la tombée de la nuit, sous une pluie battante, le groupe arrive.",
            "opening_scene": {
                "place": "Crypte oubliée",
                "description": "Une antichambre sèche et silencieuse.",
                "time_of_day": "morning",
                "weather": None,
            },
        },
    }

    response = _opening_response(active, campaign_context=campaign_context)

    journal = _action_by_type(response.actions, "journal_update")
    assert journal is not None
    assert journal.params["time_of_day"] == "morning"
    assert "weather" not in journal.params


def test_opening_response_uses_migrated_legacy_opening_scene() -> None:
    """Un ancien dossier migré vers opening_scene reste une scène d'embauche jouable."""
    from app.api.routes_game import _infer_opening_scene_from_context, _opening_response

    active = SimpleNamespace(state_data={"characters": {"thorvald": {"name": "Thorvald"}}})
    campaign_context = {
        "active_chapter": {
            "key_locations": ["Goldenthrone"],
            "initial_state": (
                "Les PJ arrivent par téléportation dans le quartier du port. "
                "Syndra se repose chez Wakanga O'tamu."
            ),
            "involved_npcs": [
                "Syndra Silvane",
                "Wakanga O'tamu",
                "Jobal",
                "Zindar",
                "Grandfather Zitembe",
            ],
        },
        "player_contract": {
            "title": "La Tombe de l'Anihilation",
            "hook": (
                "L'archmage Syndra Silvane se consume lentement. "
                "Elle vous engage pour voyager vers Port Nyanzaru."
            ),
            "known_objectives": ["Trouver la source de la malédiction de mort"],
        },
    }
    campaign_context["active_chapter"]["opening_scene"] = _infer_opening_scene_from_context(
        campaign_context,
        "Goldenthrone",
    )

    response = _opening_response(active, campaign_context=campaign_context)
    journal = _action_by_type(response.actions, "journal_update")
    assert journal is not None
    assert journal.params["location_region"] is None
    assert journal.params["location_place"] == "Goldenthrone"
    assert journal.params["location_venue"] == "Chez Wakanga O'tamu"

    scene = _action_by_type(response.actions, "scene_layout")
    assert scene is not None
    assert "Syndra Silvane" in scene.params["description"]
    assert "Wakanga O'tamu" in scene.params["description"]

    poi_ids = [poi["id"] for poi in scene.params["pois"]]
    assert "syndra_silvane" in poi_ids
    assert "wakanga_o_tamu" in poi_ids
    assert "Jobal" not in response.narration
    assert "Zindar" not in response.narration
    assert "Grandfather Zitembe" not in response.narration
    assert "Syndra Silvane attend le groupe" in response.narration
    assert "Wakanga O'tamu" in response.narration
    # Le briefing public (known_objectives) apparaît bien — c'est l'objectif
    # officiel connu du groupe.
    assert "Mission confiée" in response.narration
    assert "Trouver la source de la malédiction de mort" in response.narration
    assert "Vous pouvez" not in response.narration
    assert response.narration.endswith("Que faites-vous ?")


@pytest.mark.asyncio
async def test_missing_opening_scene_is_migrated_before_opening(monkeypatch) -> None:
    from app.api import routes_game

    campaign_context = {
        "active_chapter": {
            "id": "chapter_1",
            "key_locations": ["Goldenthrone"],
            "initial_state": "Syndra se repose chez Wakanga O'tamu.",
            "involved_npcs": ["Syndra Silvane", "Wakanga O'tamu"],
        },
        "player_contract": {
            "hook": "Syndra Silvane engage le groupe.",
            "known_objectives": ["Trouver la source de la malédiction de mort"],
        },
    }
    monkeypatch.setattr(
        "app.services.campaign_dossier_service.campaign_for_session",
        AsyncMock(return_value=None),
    )

    migrated = await routes_game._migrate_missing_opening_scene(
        "session-1",
        campaign_context,
        AsyncMock(),
    )

    assert migrated is True
    opening_scene = campaign_context["active_chapter"]["opening_scene"]
    assert opening_scene["place"] == "Goldenthrone"
    assert opening_scene["present_npcs"][0]["id"] == "syndra_silvane"


def test_opening_response_falls_back_for_empty_context() -> None:
    """Sans dossier riche, l'ouverture reste fonctionnelle avec valeurs neutres."""
    from app.api.routes_game import _opening_response

    active = SimpleNamespace(state_data={"characters": {}})
    response = _opening_response(active, campaign_context={})

    journal = _action_by_type(response.actions, "journal_update")
    assert journal is not None
    assert journal.params["time_of_day"] == "morning"
    assert "weather" not in journal.params

    scene = _action_by_type(response.actions, "scene_layout")
    assert scene is not None
    poi_ids = [poi["id"] for poi in scene.params["pois"]]
    assert "ambiance_initiale" not in poi_ids
    assert "abri_terrain" in poi_ids
    assert "zone_instable" in poi_ids
    assert "source_information" not in poi_ids


def test_opening_response_separates_hook_from_scene() -> None:
    """La narration d'ouverture commence par le lieu physique puis le contexte."""
    from app.api.routes_game import _hook_context_text, _scene_context_text

    campaign_context = {
        "active_chapter": {
            "key_locations": ["Goldenthrone"],
            "initial_state": (
                "L'archmage Syndra Silvane se consume lentement à Goldenthrone."
            ),
            "involved_npcs": ["Syndra Silvane"],
            "stakes": "La malédiction s'aggrave chaque jour.",
            "opening_scene": {
                "place": "Port Nyanzaru",
                "venue": "Auberge du Poisson Grillé",
                "description": "Une salle commune ouverte aux questions.",
            },
        },
        "player_contract": {
            "title": "La Tombe de l'Anihilation",
            "hook": "Syndra vous engage pour voyager vers Port Nyanzaru.",
            "known_objectives": ["Trouver la source de la malédiction"],
        },
    }

    hook = _hook_context_text(campaign_context)
    scene = _scene_context_text(campaign_context)

    # La scène mentionne le lieu physique
    assert "Auberge du Poisson Grillé" in scene
    assert "première scène" not in scene
    assert "Syndra vous engage" not in scene

    # Le hook contient le contexte public, sans objectif ni formule de structure.
    assert "Syndra vous engage" in hook
    assert "Trouver la source" not in hook
    assert "Un cap possible se dessine" not in hook
    assert "première scène" not in hook


def test_opening_response_hides_private_or_structural_meta_text() -> None:
    """La narration publique ne révèle ni menus, ni objectifs, ni enjeux privés."""
    from app.api.routes_game import _opening_response

    active = SimpleNamespace(state_data={"characters": {"shade": {"name": "Shade"}}})
    campaign_context = {
        "active_chapter": {
            "stakes": "Si les PJ échouent, le culte obtient la clé.",
            "opening_scene": {
                "place": "Port Nyanzaru",
                "venue": "Marché aux Épices",
                "description": "Un homme au chapeau à plumes fait signe près d'une tente bleue.",
                "present_npcs": [{"id": "contact", "name": "Homme au chapeau"}],
                "visible_clues": [{"id": "tente_bleue", "name": "Tente bleue"}],
            },
        },
        "player_contract": {
            "title": "La Tombe de l'annihilation",
            "hook": "La Guilde des Cartographes vous a donné rendez-vous ici.",
            "known_objectives": ["Atteindre la Tombe de l'annihilation"],
        },
    }

    response = _opening_response(active, campaign_context=campaign_context)
    narration = response.narration

    assert "première scène jouable" not in narration
    assert "Un cap possible se dessine" not in narration
    assert "Si les PJ échouent" not in narration
    # known_objectives est PUBLIC (la mission officielle du groupe) et doit
    # apparaître dans le briefing d'ouverture.
    assert "Mission confiée" in narration
    assert "Atteindre la Tombe de l'annihilation" in narration
    assert "Vous pouvez" not in narration
    # Le hook est une accroche publique jouable : il explique pourquoi le
    # groupe est impliqué avant de cadrer la scène immédiate.
    assert "La Guilde des Cartographes" in narration
    assert narration.endswith("Que faites-vous ?")


def test_campaign_opening_text_surfaces_public_hook() -> None:
    """La narration d'ouverture révèle l'accroche publique de campagne."""
    from app.api.routes_game import _campaign_opening_text

    campaign_context = {
        "active_chapter": {
            "key_locations": ["Port Nyanzaru"],
            "opening_scene": {
                "place": "Port Nyanzaru",
                "venue": "Marché aux Épices",
                "description": "Le marché bourdonne d'activité sous la chaleur tropicale.",
                "present_npcs": [
                    {
                        "id": "contact",
                        "name": "Volothamp Geddarm",
                        "description": "un homme au chapeau à plumes",
                    }
                ],
            },
        },
        "player_contract": {
            "hook": "La Guilde des Cartographes vous engage pour atteindre Chult.",
            "known_objectives": [
                "Cartographier les ruines oubliées de la jungle de Chult"
            ],
        },
    }

    text = _campaign_opening_text(campaign_context)

    assert "Accroche" in text
    assert "Guilde des Cartographes" in text
    # La scène et l'affordance NPC restent présentes.
    assert "Port Nyanzaru" in text or "Marché" in text
    assert "chapeau à plumes" in text
    assert text.endswith("Que faites-vous ?")


def test_campaign_opening_text_surfaces_known_objective_briefing() -> None:
    """L'ouverture inclut le hook public et les known_objectives.

    Le joueur doit savoir POURQUOI son groupe est sur place dès l'ouverture,
    via l'accroche et l'objectif officiel.
    """
    from app.api.routes_game import _campaign_opening_text

    campaign_context = {
        "active_chapter": {
            "opening_scene": {
                "place": "Port Nyanzaru",
                "venue": "Marché aux Épices",
                "description": "Le marché grouille.",
                "present_npcs": [
                    {
                        "id": "contact",
                        "name": "Volothamp",
                        "description": "un homme au chapeau à plumes",
                    }
                ],
            },
        },
        "player_contract": {
            "hook": "Une commanditaire vous paie pour partir vers Chult.",
            "known_objectives": [
                "Cartographier les ruines oubliées de la jungle de Chult"
            ],
        },
    }

    text = _campaign_opening_text(campaign_context)

    assert "Accroche" in text
    assert "commanditaire" in text
    assert "Mission confiée au groupe" in text
    assert "Cartographier les ruines oubliées" in text


def test_campaign_opening_text_without_known_objective_skips_briefing() -> None:
    """Sans known_objectives, l'ouverture n'inclut pas de ligne de briefing.

    Le système doit dégrader proprement quand le contrat joueur ne porte pas
    d'objectif explicite (campagne libre, partie d'amorce, etc.).
    """
    from app.api.routes_game import _campaign_opening_text

    campaign_context = {
        "active_chapter": {
            "opening_scene": {
                "place": "Port Nyanzaru",
                "venue": "Marché aux Épices",
                "description": "Le marché grouille.",
                "present_npcs": [],
            },
        },
        "player_contract": {},
    }

    text = _campaign_opening_text(campaign_context)
    assert "Mission confiée" not in text
    assert text.endswith("Que faites-vous ?")


def test_seed_campaign_opening_quest_never_uses_hook() -> None:
    from app.api.routes_game import _seed_campaign_opening_quest

    active = SimpleNamespace(state_data={})
    campaign_context = {
        "player_contract": {
            "hook": "SECRET_ARTEFACT necromantique sous la ville.",
            "pitch_public": "Une disparition inquiète le quartier.",
            "known_objectives": ["Retrouver la personne disparue"],
        }
    }

    assert _seed_campaign_opening_quest(active, campaign_context) is True

    quest = active.state_data["quests"][0]
    assert quest["id"] == "campaign_opening"
    assert quest["summary"] == "Une disparition inquiète le quartier."
    assert "SECRET_ARTEFACT" not in quest["summary"]


@pytest.mark.asyncio
async def test_send_campaign_opening_narration_uses_llm_text_only(monkeypatch) -> None:
    from app.agents.schemas import GMAction, GMResponse
    from app.api import routes_game

    active = SimpleNamespace(
        state_data={
            "characters": {"shade": {"name": "Shade", "is_ai": True}},
            "campaign_context": {
                "player_contract": {
                    "hook": "Un message public invite le groupe à suivre la piste.",
                    "pitch_public": "Public pitch.",
                    "known_objectives": ["Suivre la piste publique"],
                },
                "active_chapter": {
                    "opening_scene": {
                        "place": "Vieille route",
                        "description": "La brume colle aux bottes.",
                    }
                },
            },
        }
    )
    captured: dict = {}

    async def fake_open_scene(self, **kwargs):
        captured["brief"] = kwargs["opening_brief"]
        return GMResponse(
            narration="SENTINEL_NARRATION",
            actions=[
                GMAction(
                    type="quest_add",
                    params={"id": "llm_quest", "title": "Ne pas exécuter"},
                )
            ],
        )

    async def fake_publish(session_id, active_session, db, response, *, quest_changed):
        captured["response"] = response
        captured["quest_changed"] = quest_changed

    monkeypatch.setattr(routes_game.GMAgent, "open_scene", fake_open_scene)
    monkeypatch.setattr(routes_game, "_publish_opening_scene", fake_publish)
    monkeypatch.setattr(routes_game.event_bus, "publish_to_session", AsyncMock())

    await routes_game._send_campaign_opening_narration(
        "session-1",
        active,
        active.state_data["campaign_context"],
        db=None,
    )

    response = captured["response"]
    assert response.narration == "SENTINEL_NARRATION"
    assert [action.type for action in response.actions] == [
        "journal_update",
        "scene_layout",
        "region_map_update",
    ]
    assert "llm_quest" not in str(response.actions)
    assert captured["quest_changed"] is True
    assert "## PUBLIC JOUEURS" in captured["brief"]
    assert "Accroche publique" in captured["brief"]
    assert "## PRIVÉ MJ" in captured["brief"]


@pytest.mark.asyncio
async def test_send_campaign_opening_narration_falls_back_on_llm_fallback(monkeypatch) -> None:
    from app.agents.gm_agent import _FALLBACK_NARRATION
    from app.agents.schemas import GMResponse
    from app.api import routes_game

    active = SimpleNamespace(
        state_data={
            "characters": {},
            "campaign_context": {
                "player_contract": {
                    "hook": "Un message public invite le groupe à suivre la piste.",
                    "pitch_public": "Public pitch.",
                    "known_objectives": ["Suivre la piste publique"],
                },
                "active_chapter": {
                    "opening_scene": {
                        "place": "Vieille route",
                        "description": "La brume colle aux bottes.",
                    }
                },
            },
        }
    )
    captured: dict = {}

    async def fake_open_scene(self, **kwargs):
        return GMResponse(narration=_FALLBACK_NARRATION, actions=[])

    async def fake_publish(session_id, active_session, db, response, *, quest_changed):
        captured["response"] = response

    monkeypatch.setattr(routes_game.GMAgent, "open_scene", fake_open_scene)
    monkeypatch.setattr(routes_game, "_publish_opening_scene", fake_publish)
    monkeypatch.setattr(routes_game.event_bus, "publish_to_session", AsyncMock())

    await routes_game._send_campaign_opening_narration(
        "session-1",
        active,
        active.state_data["campaign_context"],
        db=None,
    )

    assert captured["response"].narration != _FALLBACK_NARRATION
    assert "Mission confiée" in captured["response"].narration
    assert "Que faites-vous ?" in captured["response"].narration


@pytest.mark.asyncio
async def test_publish_opening_scene_normalizes_path_closer_and_clears_flag(monkeypatch) -> None:
    from app.agents.schemas import GMResponse
    from app.api import routes_game
    from app.game.event_bus import EventType

    published: list[tuple[str, dict]] = []

    class FakeExecutor:
        def __init__(self, *args, **kwargs):
            pass

        async def execute_gm_response(self, response, active, db, *, session_id=None):
            return None

    async def fake_publish(session_id, event_type, payload, source=None):
        published.append((event_type, payload))

    active = SimpleNamespace(
        state_data={
            "_opening_narration_in_progress": True,
            "campaign_context": {
                "active_chapter": {
                    "opening_scene": {
                        "place": "Résidence de Wakanga",
                        "description": "Un salon calme autour d'une table basse.",
                    }
                }
            },
        },
        mark_dirty=lambda: None,
    )

    monkeypatch.setattr(routes_game, "GMResponseExecutor", FakeExecutor)
    monkeypatch.setattr(routes_game.session_manager, "save_state", AsyncMock())
    monkeypatch.setattr(routes_game.event_bus, "publish_to_session", fake_publish)
    monkeypatch.setattr(
        routes_game,
        "_build_session_state_payload_with_maps",
        AsyncMock(return_value={}),
    )
    monkeypatch.setattr("app.services.message_service.persist_narration", AsyncMock())

    await routes_game._publish_opening_scene(
        "session-1",
        active,
        db=None,
        response=GMResponse(
            narration="Syndra vous observe. Quel chemin souhaitez-vous prendre ?",
            actions=[],
        ),
        quest_changed=False,
    )

    assert active.state_data["welcome_narration_sent"] is True
    assert "_opening_narration_in_progress" not in active.state_data
    narration_payload = next(
        payload for event, payload in published if event == EventType.NARRATION
    )
    assert narration_payload["text"] == "Syndra vous observe. Que faites-vous ?"


@pytest.mark.asyncio
async def test_create_save_requires_name_schema(async_client) -> None:
    session_resp = await async_client.post("/api/sessions/", json={"name": "Save Test"})
    session_id = session_resp.json()["id"]

    response = await async_client.post(f"/api/game/{session_id}/saves", json={})

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_save_rejects_blank_name(async_client) -> None:
    session_resp = await async_client.post("/api/sessions/", json={"name": "Save Test"})
    session_id = session_resp.json()["id"]

    response = await async_client.post(f"/api/game/{session_id}/saves", json={"name": " "})

    assert response.status_code == 422
