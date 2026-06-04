from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.game.action_mechanics import ActionMechanics
from app.game.action_pipeline import ActionPipeline, ActionRequest
from app.game.action_resolver import ActionResolver
from app.game.roll_executor import execute_roll_request
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus


def test_action_mechanics_normalizes_attack_roll_event() -> None:
    event = ActionMechanics()._normalize_roll_event(
        {
            "type": "attack",
            "d20_roll": 13,
            "attack_total": 18,
            "summary": "Attaque : 18 touche",
            "hit": True,
        }
    )

    assert event == {
        "dice_notation": "1d20",
        "rolls": [13],
        "total": 18,
        "modifier": 5,
        "label": "Attaque : 18 touche",
        "success": True,
    }


def test_action_mechanics_normalizes_social_skill_check_event() -> None:
    event = ActionMechanics()._normalize_roll_event(
        {
            "type": "skill_check",
            "skill": "persuasion",
            "dice_notation": "1d20",
            "rolls": [12],
            "d20_roll": 12,
            "modifier": 7,
            "total": 19,
            "dc": 15,
            "success": True,
            "label": "CHA (Persuasion)",
            "breakdown": "12 + 5 + 2 prof = 19 vs DC 15 ✓",
            "actor_id": "hero-1",
            "social_target_id": "azaka",
        }
    )

    assert event["dice_notation"] == "1d20"
    assert event["rolls"] == [12]
    assert event["modifier"] == 7
    assert event["label"] == "CHA (Persuasion)"
    assert event["success"] is True
    assert event["dc"] == 15
    assert event["character_id"] == "hero-1"
    assert event["social_target_id"] == "azaka"


def test_action_resolver_keeps_action_mechanics_facade() -> None:
    resolver = ActionResolver(gm_agent=AsyncMock())

    assert not isinstance(resolver, ActionMechanics)
    assert resolver._resolve_generic_roll("test")["type"] == "generic_roll"


def test_roll_executor_supports_social_target_metadata() -> None:
    active = SimpleNamespace(
        state_data={
            "characters": {
                "hero-1": {
                    "name": "Aria",
                    "ability_scores": {"cha": 14},
                    "level": 1,
                    "skill_proficiencies": ["persuasion"],
                }
            }
        }
    )

    event = execute_roll_request(
        {"skill": "persuasion", "dc": 10, "social_target": "goblin-1"},
        "hero-1",
        active,
    )

    assert event is not None
    assert event["character_id"] == "hero-1"
    assert event["social_target_id"] == "goblin-1"


def _persist_speaker(payload: dict) -> str:
    """Réplique la dérivation du speaker de persist_roll_result (message_service.py:74)."""
    return str(payload.get("character_name") or "Système")


def test_roll_executor_attributes_unresolved_target_to_a_pc() -> None:
    # Q7 — un jet SUBI (ex. crise d'horloge, save environnemental) sans cible
    # explicite résolue doit être rattaché à un PJ, jamais laissé à « Système ».
    active = SimpleNamespace(
        state_data={
            "characters": {
                "oaken-1": {
                    "name": "Oaken",
                    "ability_scores": {"dex": 12},
                    "level": 3,
                    "save_proficiencies": ["dexterity"],
                }
            }
        }
    )

    event = execute_roll_request({"ability": "dexterity", "save": True, "dc": 14}, None, active)

    assert event is not None
    assert event["character_id"] == "oaken-1"
    assert event["character_name"] == "Oaken"
    assert _persist_speaker(event) == "Oaken"
    assert _persist_speaker(event) != "Système"


def test_roll_executor_never_yields_empty_character_name() -> None:
    # Personnage sans clé "name" : character_name retombe sur l'id résolu (non
    # vide) — l'invariant « jamais Système pour un PJ » tient même en données
    # dégradées.
    active = SimpleNamespace(
        state_data={
            "characters": {
                "vael-1": {
                    "ability_scores": {"wis": 10},
                    "level": 1,
                }
            }
        }
    )

    event = execute_roll_request({"ability": "wisdom", "save": True, "dc": 12}, None, active)

    assert event is not None
    assert event["character_name"]  # non vide
    assert event["character_id"] == "vael-1"
    assert _persist_speaker(event) != "Système"


def test_scene_interaction_roll_keeps_character_name_through_roundtrip() -> None:
    # G-bis — un jet d'interaction de scène (clic-POI) traverse
    # execute_roll_request → _normalize_roll_event → _enrich_roll_event sans
    # perdre character_name, donc n'est jamais persisté « Système » ni rendu « — ».
    active = SimpleNamespace(
        state_data={
            "characters": {
                "thorvald-1": {
                    "name": "Thorvald",
                    "ability_scores": {"int": 8},  # mod -1, comme la chronique
                    "level": 1,
                    "skill_proficiencies": [],
                }
            }
        }
    )
    # Reproduit _resolve_scene_interaction_roll (action_pipeline.py:1066-1085) :
    # payload d'execute_roll_request, puis update type=skill_check + actor_id.
    raw = execute_roll_request({"skill": "investigation", "dc": 12}, "thorvald-1", active)
    assert raw is not None
    raw.update({"type": "skill_check", "actor_id": "thorvald-1"})

    normalized = ActionMechanics()._normalize_roll_event(raw)
    request = ActionRequest(
        session_id="s1",
        action_type="custom",
        actor_id="thorvald-1",
        actor_kind="player",
    )
    enriched = ActionPipeline._enrich_roll_event(normalized, request, "Thorvald", None)

    assert enriched["character_name"] == "Thorvald"
    assert _persist_speaker(enriched) == "Thorvald"
    assert _persist_speaker(enriched) != "Système"


def test_enrich_roll_event_backfills_character_name_from_actor() -> None:
    # Filet déterministe : même si character_name est absent du payload normalisé
    # (autre branche de _normalize_roll_event, ex. attaque), l'enrichissement le
    # restaure depuis l'acteur — jamais « Système » pour un acteur identifié.
    request = ActionRequest(
        session_id="s1",
        action_type="attack",
        actor_id="elara-1",
        actor_kind="companion",
    )
    enriched = ActionPipeline._enrich_roll_event(
        {"dice_notation": "1d20", "rolls": [13], "total": 18, "modifier": 5},
        request,
        "Elara",
        None,
    )

    assert enriched["character_name"] == "Elara"
    assert _persist_speaker(enriched) == "Elara"


def test_enrich_roll_event_without_actor_name_stays_systeme_not_none() -> None:
    # Garde anti-piège str(None) : sans nom d'acteur disponible, character_name
    # reste absent → speaker « Système » (comportement actuel), JAMAIS « None ».
    request = ActionRequest(session_id="s1", action_type="custom", actor_kind="player")
    enriched = ActionPipeline._enrich_roll_event(
        {"dice_notation": "1d20", "rolls": [5], "total": 5, "modifier": 0},
        request,
        None,  # type: ignore[arg-type]  # acteur inconnu (jet d'environnement non rattaché)
        None,
    )

    assert not enriched.get("character_name")
    speaker = _persist_speaker(enriched)
    assert speaker == "Système"
    assert speaker != "None"


@pytest.mark.asyncio
async def test_action_mechanics_resolves_spell_from_caster_snapshot_without_db() -> None:
    active = ActiveSession(session_id="session-1", phase=SessionStatus.COMBAT)
    active.state_data["combatants"] = {"goblin-1": {"ac": 10}}

    result = await ActionMechanics()._resolve_cast_spell(
        "session-1",
        "hero-1",
        "fire_bolt",
        None,
        "goblin-1",
        active,
        {
            "char_class": "wizard",
            "level": 1,
            "ability_scores": {"int": 16},
            "slots_remaining": {},
        },
    )

    assert result["type"] == "cast_spell"
    assert result["spell_id"] == "fire_bolt"
    assert "summary" in result
