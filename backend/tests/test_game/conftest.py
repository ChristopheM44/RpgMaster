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

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import pytest
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient

import app.models  # noqa: F401
from app.db.database import Base, get_db
from app.main import create_app


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
