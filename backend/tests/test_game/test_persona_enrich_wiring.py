"""C2 — enrichissement « stub-then-enrich » des PNJ introduits live.

Prouve le câblage de bout en bout : un PNJ sans persona persistée déclenche la
création d'un stub (persisté immédiatement → idempotence) puis un enrichissement
LLM en tâche de fond qui re-persiste une persona ``standard`` SOUS le bon
``npc_id`` — y compris quand le LLM renvoie un id différent (garde d'ID).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.agents.persona import NPCPersona
from app.config import settings
from app.game.action_resolver import ActionResolver
from app.models.campaign import Campaign
from app.services import campaign_dossier_service


@pytest_asyncio.fixture
async def session_factory(db_engine):
    """Factory de session sur le MÊME engine que ``db_session`` (DB in-memory partagée)."""
    return async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)


@pytest.mark.asyncio
async def test_new_npc_stubbed_then_enriched_under_npc_id(db_session, session_factory, monkeypatch):
    # Réactive l'enrichissement live (désactivé par défaut dans la suite — cf. conftest).
    monkeypatch.setattr(settings, "live_persona_enrichment", True)

    session_id = "sess-c2"
    npc_id = "garrn_le_forgeron"

    # Campagne réelle liée à la session → ``campaign_for_session`` la retrouve.
    db_session.add(Campaign(id="camp-c2", name="C2", session_ids=[session_id]))
    await db_session.commit()

    # Le LLM renvoie une persona "standard" AVEC SON PROPRE id → prouve que la garde
    # force bien ``npc_id`` (sinon l'enrichi atterrirait sous la mauvaise clé et le
    # lookup échouerait à jamais).
    enriched = NPCPersona(
        id="id_du_llm_a_ignorer",
        name="Garrn",
        archetype="forgeron",
        short_description="Un forgeron bourru au grand cœur.",
        importance="standard",
    )

    captured: dict = {}

    def _capture(coro, name):
        # Capture la coroutine d'enrichissement sans la planifier → on l'exécute
        # explicitement plus bas (ordonnancement déterministe : stub d'abord).
        captured["coro"] = coro

    resolver = ActionResolver()
    with (
        patch("app.game.action_resolver.create_logged_task", _capture),
        patch(
            "app.game.persona_factory.PersonaFactory.enrich_npc_persona",
            new=AsyncMock(return_value=enriched),
        ),
    ):
        result = await resolver._resolve_npc_persona_or_hint(
            session_id=session_id,
            npc_id=npc_id,
            npc={"name": "Garrn", "personality_hint": "bourru"},
            db=db_session,
            session_factory=session_factory,
        )

        # Réplique courante : on récupère le stub light (pas le hint string legacy).
        # Assertions synchrones (pas d'await) → la tâche de fond n'a pas encore tourné.
        assert isinstance(result, NPCPersona)
        assert result.id == npc_id
        assert result.importance == "light"

        # Exécuter l'enrichissement de fond (coro capturée) jusqu'au bout.
        await captured["coro"]

    # Relecture depuis une session FRAÎCHE (pas de cache d'identité parasite) :
    # persona "standard" persistée SOUS npc_id — preuve de la garde d'ID + persist.
    async with session_factory() as check:
        persisted = await campaign_dossier_service.get_npc_persona("camp-c2", npc_id, check)
    assert persisted is not None
    assert persisted.importance == "standard"
    assert persisted.id == npc_id


@pytest.mark.asyncio
async def test_new_npc_without_factory_persists_stub_and_skips_enrich(db_session):
    """Sans ``session_factory`` (dégradation gracieuse) : stub persisté, pas d'enrich."""
    session_id = "sess-c2b"
    npc_id = "vendeur_anonyme"
    db_session.add(Campaign(id="camp-c2b", name="C2b", session_ids=[session_id]))
    await db_session.commit()

    resolver = ActionResolver()
    with patch("app.game.action_resolver.create_logged_task") as logged_task:
        result = await resolver._resolve_npc_persona_or_hint(
            session_id=session_id,
            npc_id=npc_id,
            npc={"name": "Vendeur", "personality_hint": "pressé"},
            db=db_session,
            session_factory=None,
        )

    # Stub retourné, AUCUNE tâche d'enrichissement lancée.
    assert isinstance(result, NPCPersona)
    assert result.id == npc_id
    assert result.importance == "light"
    logged_task.assert_not_called()

    # Le stub est persisté SYNCHRONIQUEMENT (idempotence) sous le bon id : une
    # relecture le trouve → les répliques suivantes ne re-déclenchent pas la branche.
    persisted = await campaign_dossier_service.get_npc_persona("camp-c2b", npc_id, db_session)
    assert persisted is not None
    assert persisted.importance == "light"
    assert persisted.id == npc_id
