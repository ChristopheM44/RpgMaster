"""Fixtures spécifiques aux tests du module game/.

Le TestClient de Starlette possède son propre event loop interne, incompatible
avec les fixtures async du conftest global pour les WebSockets.

Stratégie :
- `ws_client` crée sa propre DB in-memory via StaticPool (une seule connexion).
- Le lifespan de l'app est remplacé pour créer les tables dans l'event loop
  du TestClient (car `on_event("startup")` est ignoré quand un `lifespan` est déjà défini).
- Chaque test WS crée ses données via l'API HTTP du même TestClient.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import app.models  # noqa: F401
from app.db.database import Base, get_db
from app.main import create_app

# Réponse JSON canned, valide à la fois pour ``GMResponse`` (clé ``narration``)
# et ``PlayerActionChoice`` (clés ``action_type`` / ``action_description`` /
# ``roleplay_text``) — cf. app/agents/schemas.py. Les champs surnuméraires sont
# ignorés par Pydantic, donc un même payload sert au MJ comme aux joueurs IA.
_CANNED_LLM_JSON = json.dumps(
    {
        "narration": "La scène se poursuit, calme et attentive.",
        "actions": [],
        "mood": "neutral",
        "action_type": "wait",
        "action_description": "observe la scène",
        "roleplay_text": "(observe la scène, attentif)",
        "inner_reasoning": "Réponse de test déterministe.",
    },
    ensure_ascii=False,
)


@pytest.fixture(autouse=True)
def _stub_real_llm_calls():
    """Neutralise tout appel LLM réseau réel dans la suite ``game/``.

    Conforme à la philosophie de test (CLAUDE.md) : seuls les tests
    ``tests/test_e2e_live`` (marqueur ``live_llm``) appellent un vrai LLM. Les
    tests ``game/`` qui n'injectent pas leur propre mock d'agent retombaient
    sinon sur de vrais appels Ollama Cloud — lents (réseau) et surtout source de
    tâches de fond orphelines liées à des event loops fermés (« Event loop is
    closed » puis ``CancelledError`` au teardown du ``TestClient``, flake
    d'isolation à victime variable).

    On patche ``OllamaClient.chat`` / ``generate`` au niveau classe : MJ,
    joueurs IA et services passent tous par là. Les tests qui patchent un client
    ou un agent au niveau instance gardent la priorité (l'attribut d'instance
    masque celui de classe).
    """
    from app.llm.ollama_client import OllamaClient

    with (
        patch.object(OllamaClient, "chat", new=AsyncMock(return_value=_CANNED_LLM_JSON)),
        patch.object(OllamaClient, "generate", new=AsyncMock(return_value=_CANNED_LLM_JSON)),
        patch.object(OllamaClient, "is_available", new=AsyncMock(return_value=True)),
    ):
        yield


@pytest.fixture
def ws_client():
    """TestClient synchrone avec DB in-memory partagée (StaticPool).

    Le lifespan est remplacé pour que les tables soient créées dans l'event loop
    interne du TestClient.

    Créer les sessions de test via HTTP avant de tester les WebSockets :

        resp = ws_client.post("/api/sessions/", json={"name": "Test"})
        session_id = resp.json()["id"]
        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ...
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    # Remplace le lifespan de l'app pour créer les tables dans l'event loop du TestClient.
    # On ne peut pas utiliser on_event("startup") car create_app() déclare déjà un lifespan.
    @asynccontextmanager
    async def test_lifespan(_app: FastAPI) -> AsyncIterator[None]:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()

    application = create_app()
    application.state.db_session_factory = session_factory
    application.router.lifespan_context = test_lifespan
    application.dependency_overrides[get_db] = override_get_db

    with TestClient(application, raise_server_exceptions=True) as client:
        yield client

    application.dependency_overrides.clear()
