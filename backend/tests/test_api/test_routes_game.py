from __future__ import annotations

from types import SimpleNamespace

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


def test_opening_response_legacy_fallback_keeps_hiring_scene_playable() -> None:
    """Les anciens dossiers sans opening_scene restent une scène d'embauche jouable."""
    from app.api.routes_game import _opening_response

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
    assert "Syndra Silvane se tient face au groupe" in response.narration
    assert "Wakanga O'tamu" in response.narration
    # Le briefing public (known_objectives) apparaît bien — c'est l'objectif
    # officiel connu du groupe.
    assert "Mission confiée" in response.narration
    assert "Trouver la source de la malédiction de mort" in response.narration
    assert "Vous pouvez" not in response.narration
    assert response.narration.endswith("Que faites-vous ?")


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
    assert "ambiance_initiale" in poi_ids
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
    # Le hook (twist secret du MJ) ne doit JAMAIS apparaître en narration
    # visible. Il alimente le briefing privé du MJ, pas le texte lu aux
    # joueurs.
    assert "La Guilde des Cartographes" not in narration
    assert narration.endswith("Que faites-vous ?")


def test_campaign_opening_text_excludes_hook_secret() -> None:
    """La narration d'ouverture ne révèle pas le hook de campagne (secret du MJ).

    Le hook contient le twist central ("le fléau est libéré", "la tombe est
    réelle") ; il doit alimenter le briefing privé MJ, pas le texte lu aux
    joueurs. La narration visible = briefing public + lieu + scène + PNJ.
    """
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
            "hook": (
                "La tombe légendaire est bien réelle, "
                "et quelqu'un cherche à en libérer le fléau."
            ),
            "known_objectives": [
                "Cartographier les ruines oubliées de la jungle de Chult"
            ],
        },
    }

    text = _campaign_opening_text(campaign_context)

    # Le secret de campagne ne doit pas apparaître.
    assert "fléau" not in text.lower()
    assert "tombe" not in text.lower()
    assert "réelle" not in text.lower()
    # La scène et l'affordance NPC restent présentes.
    assert "Port Nyanzaru" in text or "Marché" in text
    assert "chapeau à plumes" in text
    assert text.endswith("Que faites-vous ?")


def test_campaign_opening_text_surfaces_known_objective_briefing() -> None:
    """L'ouverture inclut le briefing public (known_objectives) sans le hook.

    Le joueur doit savoir POURQUOI son groupe est sur place dès l'ouverture,
    via ``known_objectives``. Le ``hook`` (twist privé MJ) reste invisible.
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
            "hook": "Le fléau de la tombe est sur le point d'être libéré.",
            "known_objectives": [
                "Cartographier les ruines oubliées de la jungle de Chult"
            ],
        },
    }

    text = _campaign_opening_text(campaign_context)

    assert "Mission confiée au groupe" in text
    assert "Cartographier les ruines oubliées" in text
    # Le hook reste exclu.
    assert "fléau" not in text.lower()
    assert "tombe" not in text.lower()


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
