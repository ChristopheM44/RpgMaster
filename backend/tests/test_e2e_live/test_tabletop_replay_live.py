"""Live LLM replay tests for tabletop-fidelity invariants.

These tests intentionally do not mock the LLM. If the configured provider is
unavailable, the suite fails through the normal ERROR event path.

Configuration du provider (DÉCOUVERTE IMPORTANTE — ne pas chercher dans .env) :
    La config LLM live est lue depuis ``backend/.runtime/llm_runtime.json`` (le
    coffre runtime, perms 0600), chargé à l'import de ``app.config``. La CLÉ
    n'est JAMAIS lue depuis ``.env`` : ``config.get_ollama_api_key()`` ne
    consulte que ce runtime json, et ``Settings`` n'a aucun champ
    ``ollama_api_key`` — donc ``OLLAMA_API_KEY`` dans ``.env`` est décoratif et
    ignoré. (``ollama_base_url`` / ``gm_model`` / ``player_model`` retombent sur
    ``.env`` à défaut d'override runtime ; la clé, non.)

    On l'écrit via l'UI admin / l'endpoint ``update_llm_settings``, ou à la main
    dans le json. Config Ollama Cloud attendue (gemma4) :
        ollama_base_url = "https://ollama.com"
        gm_model        = "gemma4:31b"
        player_model    = "gemma4:31b"
        ollama_api_key  = "<clé Ollama Cloud, ~57 car. — secret, jamais commité>"

Lancer :
    cd backend && source .venv/bin/activate
    python -m pytest tests/test_e2e_live/ -m live_llm -v
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

import pytest

from app.agents.gm_agent import _FALLBACK_NARRATION, GMAgent
from app.game.action_pipeline import ActionPipeline, ActionRequest
from app.game.event_bus import EventType
from app.game.session_manager import ActiveSession
from app.game.travel_detection import detect_travel_intent, travel_intent_as_dict
from app.models.session import SessionStatus

SESSION_ID = "live-tabletop-replay"


class _CollectBus:
    def __init__(self) -> None:
        self.events: list[tuple[str, dict[str, Any]]] = []

    async def publish_to_session(self, session_id, event_type, payload, source=None):
        self.events.append((event_type, payload))


def _base_state() -> dict[str, Any]:
    return {
        "characters": {
            "thorvald": {
                "name": "Thorvald",
                "level": 1,
                "is_ai": False,
                "ability_scores": {"int": 12, "wis": 12, "cha": 10},
            },
            "elara": {"name": "Elara", "is_ai": True, "class_name": "Wizard"},
            "solana": {"name": "Solana", "is_ai": True, "class_name": "Cleric"},
        },
        "adventure_journal": {
            "location_region": "Désert d'Akhdar",
            "location_place": "Oasis corrompue",
            "time_of_day": "afternoon",
            "day_number": 3,
            "weather": "Chaleur sèche",
        },
        "current_scene": {
            "scene_id": "oasis_corrompue",
            "cols": 12,
            "rows": 12,
            "cell_size_m": 1.5,
            "terrain": "oasis_corrompue",
            "scene_theme": "desert",
            "description": "Une oasis basse, noircie par endroits, où l'eau dort sans reflet.",
            "pois": [
                {
                    "id": "bassin_noir",
                    "name": "Bassin noir",
                    "kind": "hazard",
                    "icon": "trap-danger",
                    "position": {"col": 5, "row": 5},
                    "description": "L'eau sombre frissonne malgré l'absence de vent.",
                    "physical_state": "eau opaque, surface huileuse",
                    "interactions": [
                        {
                            "id": "examine_surface",
                            "label": "Observer",
                            "intent": "examine",
                            "mechanics": {
                                "safe_observation": True,
                                "reveal_tier": "surface",
                            },
                        }
                    ],
                },
                {
                    "id": "journal_cache",
                    "name": "Journal caché",
                    "kind": "clue",
                    "icon": "clue",
                    "position": {"col": 7, "row": 6},
                    "description": "Une dalle plus claire dépasse entre les roseaux secs.",
                    "visibility": "hidden",
                    "discovered": False,
                    "interactions": [
                        {
                            "id": "search_journal",
                            "label": "Fouiller",
                            "intent": "search",
                            "mechanics": {
                                "roll": {
                                    "type": "check",
                                    "ability": "int",
                                    "skill": "Investigation",
                                    "dc": 1,
                                    "reason": "trouver l'objet caché",
                                },
                                "safe_observation": True,
                                "reveal_tier": "deep",
                            },
                        },
                        {
                            "id": "fail_search",
                            "label": "Inspecter vite",
                            "intent": "search",
                            "mechanics": {
                                "roll": {
                                    "type": "check",
                                    "ability": "int",
                                    "skill": "Investigation",
                                    "dc": 99,
                                    "reason": "comprendre les traces brouillées",
                                },
                                "safe_observation": True,
                                "reveal_tier": "interpreted",
                            },
                        },
                    ],
                },
            ],
            "exits": [
                {
                    "id": "vers_dunes",
                    "label": "Dunes basses",
                    "position": {"col": 11, "row": 7},
                    "leads_to": "dunes_basses",
                }
            ],
            "party_positions": {
                "thorvald": {"col": 5, "row": 7},
                "elara": {"col": 4, "row": 7},
                "solana": {"col": 5, "row": 8},
            },
        },
        "npc_states": {
            # Disparition DÉLIBÉRÉE que le groupe enquête (scénario disparition_guide).
            # On encode une absence narrative ancrée — `last_location` réel (≠ scène
            # courante) → bucket `absent_npcs`, où gm_narrate.txt interdit explicitement
            # de le faire parler — et NON l'artefact du bug P1 (`last_location=""`, qui
            # le rangeait en `unknown_location_npcs`, jamais rendu au MJ). Pas de
            # `disposition:"accompanying"` : ce serait re-encoder le bug d'évanouissement
            # au voyage que P1 corrige (cf. _travel_state + la baseline présente/accompanying
            # de test_live_llm_guide_survives_travel_transition).
            "khalid_guide": {
                "name": "Khalid le Guide",
                "status": "missing",
                "last_location": "piste_ambre",
                "known_to_party": True,
                "notes": ["Ses traces cessent près du bassin."],
            }
        },
    }


SCENARIOS: list[dict[str, Any]] = [
    {
        "id": "oasis_corrompue",
        "content": "J'observe l'eau noire et les roseaux sans rien toucher.",
    },
    {
        "id": "disparition_guide",
        "content": "J'appelle Khalid et je cherche des traces autour du bassin.",
    },
    {
        "id": "objet_cache",
        "content": "Je fouille près de la dalle claire pour trouver ce qui est caché.",
        "scene_poi_id": "journal_cache",
        "scene_interaction_id": "search_journal",
        "expect_roll": True,
        "expect_scene_update": True,
    },
    {
        "id": "discussion_compagnons",
        "content": "Elara, Solana, je veux vos avis : on fouille la dalle ou on suit les traces ?",
    },
    {
        "id": "echec_investigation",
        "content": "J'inspecte rapidement les traces brouillées près de la dalle.",
        "scene_poi_id": "journal_cache",
        "scene_interaction_id": "fail_search",
        "expect_roll": True,
        "expect_failure": True,
        "expect_scene_update": True,
    },
]


@pytest.mark.live_llm
async def test_live_llm_provider_responds_with_structured_gm_json() -> None:
    response = await GMAgent().narrate(
        game_state=_base_state(),
        player_action="Décris seulement l'ambiance immédiate de l'oasis.",
    )

    assert response.narration != _FALLBACK_NARRATION, (
        "Le LLM configuré ne répond pas : les replays live doivent échouer explicitement."
    )
    assert response.narration.strip()


@pytest.mark.live_llm
@pytest.mark.parametrize("scenario", SCENARIOS, ids=[scenario["id"] for scenario in SCENARIOS])
async def test_live_llm_tabletop_replay_scenario(scenario: dict[str, Any]) -> None:
    active = ActiveSession(
        session_id=SESSION_ID,
        phase=SessionStatus.EXPLORATION,
        state_data=deepcopy(_base_state()),
    )
    bus = _CollectBus()
    pipeline = ActionPipeline(GMAgent(), bus)

    await pipeline.resolve_and_publish(
        ActionRequest(
            session_id=SESSION_ID,
            actor_id="thorvald",
            actor_name="Thorvald",
            actor_kind="player",
            action_type="free_text",
            content=scenario["content"],
            target_id=None,
            scene_poi_id=scenario.get("scene_poi_id"),
            scene_interaction_id=scenario.get("scene_interaction_id"),
        ),
        active,
        db=None,
    )

    errors = [payload for event_type, payload in bus.events if event_type == EventType.ERROR]
    assert not errors, f"{scenario['id']} a produit une erreur système live LLM : {errors!r}"

    visible_text = "\n".join(
        str(payload.get("text") or payload.get("message") or "")
        for event_type, payload in bus.events
        if event_type in {EventType.NARRATION, EventType.DIALOGUE, EventType.ERROR}
    )
    assert visible_text.strip(), f"{scenario['id']} n'a produit aucune sortie visible."
    assert not _contains_diegetic_llm_error(visible_text)
    assert isinstance(active.state_data.get("current_scene"), dict)

    if scenario.get("expect_roll"):
        rolls = [
            payload for event_type, payload in bus.events if event_type == EventType.ROLL_RESULT
        ]
        assert rolls, f"{scenario['id']} devait résoudre un jet mécanique."
        roll = rolls[-1]
        assert roll["actor_id"] == "thorvald"
        assert roll["actor_name"] == "Thorvald"
        assert roll["actor_kind"] == "player"
        assert roll["scene_poi_id"] == scenario["scene_poi_id"]
        assert roll["dc"] is not None
        assert roll["margin"] == roll["total"] - roll["dc"]
        if scenario.get("expect_failure"):
            assert roll["success"] is False

    if scenario.get("expect_scene_update"):
        scene_events = [
            payload
            for event_type, payload in bus.events
            if event_type == EventType.SCENE_LAYOUT_CHANGED
        ]
        assert scene_events, f"{scenario['id']} devait publier une scène mise à jour."

    if scenario["id"] == "disparition_guide":
        khalid_dialogue = [
            payload
            for event_type, payload in bus.events
            if event_type == EventType.DIALOGUE and payload.get("speaker") == "Khalid le Guide"
        ]
        assert not khalid_dialogue

    assert _wrong_actor_discovery(visible_text) is None


def _contains_diegetic_llm_error(text: str) -> bool:
    lowered = text.casefold()
    markers = (
        "ollama",
        "provider llm",
        "serveur llm",
        "service ia indisponible",
        "n'a pas pu répondre",
        "injoignable",
    )
    return any(marker in lowered for marker in markers)


def _wrong_actor_discovery(text: str) -> str | None:
    if "Thorvald".casefold() in text.casefold():
        return None
    pattern = re.compile(
        r"\b(Elara|Solana)\b[^.!?\n]*(découvre|decouvre|trouve|repère|repere|comprend)",
        flags=re.IGNORECASE,
    )
    match = pattern.search(text)
    return match.group(1) if match else None


def _travel_state() -> dict[str, Any]:
    """Party on the amber trail with Khalid *accompanying*, an exit to the oasis."""
    return {
        "characters": {
            "thorvald": {
                "name": "Thorvald",
                "level": 1,
                "is_ai": False,
                "ability_scores": {"int": 12, "wis": 12, "cha": 10},
            },
            "elara": {"name": "Elara", "is_ai": True, "class_name": "Wizard"},
        },
        "adventure_journal": {
            "location_region": "Désert d'Akhdar",
            "location_place": "Piste d'Ambre",
            "time_of_day": "morning",
            "day_number": 1,
            "weather": "Chaleur sèche",
        },
        "current_scene": {
            "scene_id": "piste_ambre",
            "cols": 12,
            "rows": 12,
            "cell_size_m": 1.5,
            "terrain": "desert",
            "scene_theme": "desert",
            "description": "Une piste de sable bordée de carcasses desséchées de chameaux.",
            "pois": [
                {
                    "id": "khalid_guide",
                    "name": "Khalid le Guide",
                    "kind": "npc",
                    "icon": "npc",
                    "position": {"col": 5, "row": 6},
                    "known_to_party": True,
                }
            ],
            "exits": [
                {
                    "id": "vers_oasis",
                    "label": "Oasis d'Émeraude",
                    "position": {"col": 11, "row": 6},
                    "leads_to": "oasis_emeraude",
                }
            ],
            "party_positions": {
                "thorvald": {"col": 5, "row": 7},
                "elara": {"col": 4, "row": 7},
            },
        },
        "npc_states": {
            "khalid_guide": {
                "name": "Khalid le Guide",
                "status": "present",
                "disposition": "accompanying",
                "known_to_party": True,
                "last_location": "piste_ambre",
            }
        },
    }


@pytest.mark.live_llm
async def test_live_llm_guide_survives_travel_transition() -> None:
    """P1+P2 acceptance: an imperative travel phrase moves the scene, and the
    accompanying guide is carried across the transition rather than vanishing.

    Holds regardless of LLM whim: the deterministic travel fallback guarantees a
    SCENE_LAYOUT_CHANGED, and carry_accompanying_npcs guarantees the guide stays.
    """
    active = ActiveSession(
        session_id=SESSION_ID,
        phase=SessionStatus.EXPLORATION,
        state_data=deepcopy(_travel_state()),
    )
    bus = _CollectBus()
    pipeline = ActionPipeline(GMAgent(), bus)

    content = "Très bien, rendons-nous à l'oasis d'Émeraude, ouvrez la route Khalid."
    travel = travel_intent_as_dict(detect_travel_intent(content, active.state_data))
    assert travel and travel["is_travel"], "le marqueur impératif doit être détecté"

    await pipeline.resolve_and_publish(
        ActionRequest(
            session_id=SESSION_ID,
            actor_id="thorvald",
            actor_name="Thorvald",
            actor_kind="player",
            action_type="free_text",
            content=content,
            travel_intent=travel,
        ),
        active,
        db=None,
    )

    errors = [payload for event_type, payload in bus.events if event_type == EventType.ERROR]
    assert not errors, f"erreur système live LLM : {errors!r}"

    # Acceptance #2 — the imperative travel produced a real scene change.
    scene_changes = [
        payload
        for event_type, payload in bus.events
        if event_type == EventType.SCENE_LAYOUT_CHANGED
    ]
    assert scene_changes, "le voyage (« rendons-nous à… ») doit publier une nouvelle scène"

    # Acceptance #1 — the guide is carried, never frozen as "missing" in canon.
    khalid = active.state_data["npc_states"]["khalid_guide"]
    assert khalid["status"] == "present", "le guide ne doit pas disparaître au voyage"
    scene = active.state_data["current_scene"]
    assert any(p.get("id") == "khalid_guide" for p in scene.get("pois", []) or []), (
        "le guide doit rester un POI visible dans la nouvelle scène"
    )


@pytest.mark.live_llm
async def test_live_llm_opening_weaves_contract_without_labels() -> None:
    """P3 acceptance: the GM opening weaves the public contract into fiction —
    even a *meta* objective ("survivre aux conditions extrêmes") — and never
    pastes form labels ("Accroche :" / "Mission confiée :").

    Negative assertion by design: we don't check the contract is lexically
    *present* (that is the matching the P3 fix removed); we check the narration
    is real (not the fallback) and label-free.
    """
    game_state = {
        "characters": {
            "thorvald": {"name": "Thorvald", "level": 1, "is_ai": False},
        },
        "adventure_journal": {
            "location_region": "Désert d'Akhdar",
            "location_place": "Piste d'ambre",
            "time_of_day": "morning",
            "day_number": 1,
        },
        "campaign_context": {
            "player_contract": {
                "hook": (
                    "Une caravane a engagé le groupe pour traverser les terres "
                    "arides et découvrir pourquoi les oasis s'assèchent."
                ),
                "known_objectives": ["Survivre aux conditions extrêmes du désert"],
            },
            "active_chapter": {
                "opening_scene": {
                    "place": "Piste d'ambre",
                    "description": "Une piste de sable ocre serpente entre les dunes.",
                },
            },
        },
    }
    # Brief de PRODUCTION : il porte l'en-tête « - Accroche publique: … » et
    # « - Objectifs connus: … ». On vérifie que le LLM tisse ce contrat en
    # fiction sans recopier l'étiquette (le vrai risque de régression de P3).
    from app.api.routes_game import _build_opening_brief

    opening_brief = _build_opening_brief(game_state)
    assert "Accroche publique" in opening_brief, "garde : le brief réel doit porter le label"

    response = await GMAgent().open_scene(game_state=game_state, opening_brief=opening_brief)
    narration = str(getattr(response, "narration", "") or "")

    assert narration.strip(), "le LLM doit produire une ouverture jouable"
    assert narration != _FALLBACK_NARRATION, (
        "Le LLM configuré ne répond pas : les replays live doivent échouer explicitement."
    )
    # P3 — le LLM tisse le contrat en fiction sans recopier l'étiquette du brief.
    assert "Accroche" not in narration, f"étiquette recopiée dans l'ouverture : {narration!r}"
    assert "Mission confiée" not in narration, f"étiquette dans l'ouverture : {narration!r}"


def _proper_noun_tokens(name: str) -> list[str]:
    """Tokens d'un nom ressemblant à des noms propres (cohérence hook↔persona↔narration)."""
    stop = {
        "le",
        "la",
        "les",
        "du",
        "de",
        "des",
        "un",
        "une",
        "sir",
        "dame",
        "messire",
        "dom",
        "frere",
        "frère",
        "soeur",
        "sœur",
        "capitaine",
        "marchand",
        "marchande",
        "pretre",
        "prêtre",
        "pretresse",
        "prêtresse",
        "noble",
        "seigneur",
        "roi",
        "reine",
        "guilde",
        "archiviste",
        "maitre",
        "maître",
        "intendant",
        "intendante",
        "baron",
        "baronne",
        "comte",
        "comtesse",
        "abbe",
        "abbé",
        "doyen",
        "doyenne",
        "magistrat",
    }
    tokens = re.findall(r"[A-Za-zÀ-ÿ]{3,}", name)
    return [t for t in tokens if t.lower() not in stop]


@pytest.mark.live_llm
async def test_live_llm_forge_names_commissioner_and_opening_incarnates(db_session) -> None:
    """R4/N6 + N3 bout-en-bout : forge RÉELLE → ouverture RÉELLE.

    Forge une campagne « groupe engagé » avec le vrai LLM, puis vérifie :
      - FORME des données : commanditaire NOMMÉ dans important_npcs ET dans le hook
        (cohérence), objective_endpoint par chapitre, region_map semé (départ
        `current` + endpoint `rumored` + arête visible) ;
      - FIDÉLITÉ de l'ouverture LIVE : la narration NOMME le commanditaire et ne
        retombe pas sur « vos employeurs » anonyme, sans étiquette de fiche.
    """
    import uuid

    from app.api.routes_game import _build_opening_brief
    from app.models.campaign import Campaign
    from app.services import campaign_dossier_service as svc

    session_id = f"live-forge-{uuid.uuid4().hex[:8]}"
    campaign = Campaign(
        name="L'Escorte des Cendres",
        description=(
            "Un riche marchand engage une petite bande d'aventuriers pour escorter "
            "une cargaison précieuse jusqu'à une cité lointaine, à travers des terres "
            "infestées de pillards."
        ),
        session_ids=[session_id],
        current_session_index=0,
    )
    db_session.add(campaign)
    await db_session.commit()
    await db_session.refresh(campaign)

    brief = {"pitch": campaign.description, "title": campaign.name}
    options = {"narrative_structure": "epic_5_acts", "scope": "one-shot", "starting_level": 1}

    dossier = await svc._run_forge_job(uuid.uuid4().hex, campaign.id, brief, options, db_session)
    gm_dossier = dossier.gm_dossier
    contract = dossier.player_contract
    hook = str(contract.get("hook") or "")
    important_npcs = list(gm_dossier.get("important_npcs") or [])

    print("\n================ FORGE: HOOK ================")
    print(hook)
    print("================ IMPORTANT_NPCS ================")
    for npc in important_npcs:
        print(
            f"- {npc.get('name')} | archetype={npc.get('archetype')} | "
            f"attitude={npc.get('attitude_default')} | "
            f"visible={npc.get('motivations', {}).get('visible')}"
        )

    # --- Acceptance #1 : commanditaire NOMMÉ dans important_npcs ---
    assert important_npcs, "la forge doit produire des important_npcs (commanditaire compris)"
    commissioner = next(
        (n for n in important_npcs if "commanditaire" in str(n.get("archetype") or "").casefold()),
        None,
    )
    if commissioner is None:  # repli : le PNJ dont le nom propre apparaît dans le hook
        for npc in important_npcs:
            tokens = _proper_noun_tokens(str(npc.get("name") or ""))
            if any(t.lower() in hook.lower() for t in tokens):
                commissioner = npc
                break
    assert commissioner is not None, (
        "aucun commanditaire identifiable dans important_npcs: "
        f"{[(n.get('name'), n.get('archetype')) for n in important_npcs]}"
    )
    commissioner_name = str(commissioner.get("name") or "").strip()
    name_tokens = _proper_noun_tokens(commissioner_name)
    assert name_tokens, f"le commanditaire doit avoir un nom propre: {commissioner_name!r}"

    # --- Gate (advisor) : le hook NOMME le commanditaire (cohérence hook↔persona) ---
    assert any(t.lower() in hook.lower() for t in name_tokens), (
        f"le hook ne nomme pas le commanditaire {commissioner_name!r}: {hook!r}"
    )
    hook_low = hook.lower()
    for anon in ("vos employeurs", "votre employeur", "vos patrons", "votre patron"):
        assert anon not in hook_low, f"hook avec employeur anonyme ({anon!r}): {hook!r}"

    # --- N3 : objective_endpoint par chapitre ---
    chapters = list(gm_dossier.get("chapters") or [])
    assert chapters, "le dossier doit porter au moins un chapitre"
    endpoint = chapters[0].get("objective_endpoint") or {}
    print("================ OBJECTIVE_ENDPOINT (ch.1) ================")
    print(endpoint)
    assert isinstance(endpoint, dict) and str(endpoint.get("name") or "").strip(), (
        f"chapitre sans objective_endpoint nommé: {endpoint!r}"
    )
    assert str(endpoint.get("kind") or "").strip(), "objective_endpoint sans kind"

    # --- N3 : region_map semé (départ current + endpoint rumored + arête visible) ---
    region_map = gm_dossier.get("region_map") or {}
    nodes = list(region_map.get("nodes") or [])
    edges = list(region_map.get("edges") or [])
    statuses = {str(n.get("status") or "") for n in nodes}
    print("================ REGION_MAP ================")
    print("nodes:", [(n.get("name"), n.get("status")) for n in nodes])
    print("edges:", [(e.get("from"), e.get("to"), e.get("kind"), e.get("hidden")) for e in edges])
    assert "current" in statuses, f"region_map sans nœud `current`: {statuses}"
    assert "rumored" in statuses, f"region_map sans endpoint `rumored`: {statuses}"
    assert any(not e.get("hidden") for e in edges), "region_map sans arête visible vers l'endpoint"

    # --- Ouverture LIVE via le VRAI chemin de surfaçage (gm_private_context) ---
    await svc.validate_contract(campaign.id, contract, db_session)
    campaign_context = await svc.compile_campaign_context_for_session(session_id, db_session)
    assert campaign_context is not None
    opening_scene = (campaign_context.get("active_chapter") or {}).get("opening_scene") or {}
    state_data = {
        "characters": {"thorvald": {"name": "Thorvald", "level": 1, "is_ai": False}},
        "adventure_journal": {
            "location_region": str(opening_scene.get("region") or ""),
            "location_place": str(opening_scene.get("place") or "un lieu de départ"),
            "time_of_day": str(opening_scene.get("time_of_day") or "morning"),
            "day_number": 1,
        },
        "campaign_context": campaign_context,
    }
    gm_prompt_context = await svc.build_gm_prompt_context(session_id, db_session, state_data)
    assert gm_prompt_context.get("important_npcs"), "important_npcs doit remonter côté MJ privé"
    prompt_state = dict(state_data)
    prompt_state["_gm_prompt_context"] = gm_prompt_context

    opening_brief = _build_opening_brief(state_data)
    assert "Accroche publique" in opening_brief
    response = await GMAgent().open_scene(game_state=prompt_state, opening_brief=opening_brief)
    narration = str(getattr(response, "narration", "") or "")

    print("================ OUVERTURE (narration LIVE) ================")
    print(narration)
    print("================ known_objectives ================")
    print(contract.get("known_objectives"))
    print("============================================================\n")

    assert narration.strip(), "le LLM doit produire une ouverture jouable"
    assert narration != _FALLBACK_NARRATION, (
        "Le LLM configuré ne répond pas : les replays live doivent échouer explicitement."
    )
    # R4/N6 : la narration NOMME le commanditaire (pas « vos employeurs »).
    narration_low = narration.lower()
    assert any(t.lower() in narration_low for t in name_tokens), (
        f"l'ouverture ne nomme pas le commanditaire {commissioner_name!r}:\n{narration}"
    )
    for anon in ("vos employeurs", "votre employeur", "vos patrons", "votre patron"):
        assert anon not in narration_low, f"employeur anonyme ({anon!r}):\n{narration}"
    # P3 : pas d'étiquette de fiche dans la narration.
    assert "Accroche" not in narration, f"étiquette dans l'ouverture:\n{narration}"
    assert "Mission confiée" not in narration, f"étiquette dans l'ouverture:\n{narration}"
    assert not re.search(r"Commanditaire\s*:", narration), f"étiquette commanditaire:\n{narration}"


@pytest.mark.live_llm
async def test_live_llm_opening_names_absent_commissioner_without_materializing() -> None:
    """R4/N6 — cas « named-but-absent » : le commanditaire est ABSENT de la scène
    (groupe déjà en route, ``present_npcs=[]``) mais nommé dans le hook + le dossier MJ.

    Discrimine le renfort `gm_open_scene.txt:27` : NOMMER le commanditaire comme source
    HORS-SCÈNE de la mission ≠ le matérialiser. Le run forge réel l'avait placé présent
    au campement de départ (cas facile) ; ici on prouve qu'il est cité même absent, sans
    retomber sur « vos employeurs » et sans le faire surgir physiquement.
    """
    from app.api.routes_game import _build_opening_brief

    commissioner = {
        "id": "veyra_alenne",
        "name": "la marchande Veyra Alenne",
        "archetype": "commanditaire",
        "short_description": "Marchande prudente qui a financé l'expédition depuis Sel-d'Ambre.",
        "voice": {"gender": "female", "age_range": "adult", "speech_register": "formal"},
        "motivations": {"visible": ["Récupérer sa cargaison disparue avant la foire"]},
        "importance": "standard",
        "persona_type": "npc",
        "attitude_default": "friendly",
        "quest_hooks": ["Prime promise au retour de la cargaison"],
    }
    game_state = {
        "characters": {"thorvald": {"name": "Thorvald", "level": 1, "is_ai": False}},
        "adventure_journal": {
            "location_region": "Les Marches Grises",
            "location_place": "Piste forestière, loin de toute ville",
            "time_of_day": "afternoon",
            "day_number": 2,
        },
        "campaign_context": {
            "player_contract": {
                "hook": (
                    "La marchande Veyra Alenne vous a engagés à Sel-d'Ambre pour retrouver "
                    "sa cargaison disparue sur la piste des Marches Grises avant la foire."
                ),
                "known_objectives": ["Retrouver la cargaison disparue de Veyra Alenne"],
            },
            "active_chapter": {
                "opening_scene": {
                    "region": "Les Marches Grises",
                    "place": "Piste forestière, loin de toute ville",
                    "description": (
                        "La piste s'enfonce sous des pins serrés ; l'ornière est fraîche, "
                        "creusée de roues lourdes."
                    ),
                    "present_npcs": [],  # commanditaire ABSENT de la scène
                    "visible_clues": [],
                    "exits": [],
                },
            },
        },
        # Surfaçage MJ réel : la persona du commanditaire vit dans gm_private_context.
        "_gm_prompt_context": {"important_npcs": [commissioner]},
    }

    opening_brief = _build_opening_brief(game_state)
    assert "Accroche publique" in opening_brief
    assert "PNJ présents" not in opening_brief, (
        "garde : le commanditaire doit rester absent de la scène"
    )

    response = await GMAgent().open_scene(game_state=game_state, opening_brief=opening_brief)
    narration = str(getattr(response, "narration", "") or "")

    print("\n========= OUVERTURE (commanditaire ABSENT, narration LIVE) =========")
    print(narration)
    print("====================================================================\n")

    assert narration.strip(), "le LLM doit produire une ouverture jouable"
    assert narration != _FALLBACK_NARRATION, (
        "Le LLM configuré ne répond pas : les replays live doivent échouer explicitement."
    )
    narration_low = narration.lower()
    # Cœur du cas : le commanditaire absent est NOMMÉ (pas « vos employeurs »).
    assert "veyra" in narration_low, f"commanditaire absent NON nommé:\n{narration}"
    for anon in ("vos employeurs", "votre employeur", "vos patrons", "votre patron"):
        assert anon not in narration_low, f"employeur anonyme ({anon!r}):\n{narration}"
    assert "Accroche" not in narration, f"étiquette dans l'ouverture:\n{narration}"
    assert not re.search(r"Commanditaire\s*:", narration), f"étiquette commanditaire:\n{narration}"
