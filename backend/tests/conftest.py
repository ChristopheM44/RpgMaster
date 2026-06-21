from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.database import Base, get_db
from app.main import create_app

# Base de données SQLite en mémoire pour les tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_engine():
    """Crée un moteur SQLite in-memory avec toutes les tables."""
    # Import des modèles pour enregistrer les métadonnées
    import app.models  # noqa: F401

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine):
    """Session de test isolée par test."""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session


@pytest_asyncio.fixture
async def async_client(db_engine):
    """Client HTTP de test avec override de la dépendance DB."""
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app = create_app()
    app.state.db_session_factory = session_factory
    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _disable_live_persona_enrichment():
    """Désactive l'enrichissement LLM live des PNJ dans toute la suite de tests.

    L'enrichissement « stub-then-enrich » (ActionResolver) spawne une tâche de fond
    DB fire-and-forget : inoffensif en prod, mais dans les tests WS une telle tâche
    peut survivre à la boucle du test et corrompre le teardown d'un test ultérieur
    (connexion DB orpheline). Les tests qui vérifient l'enrichissement le réactivent
    explicitement (cf. tests/test_game/test_persona_enrich_wiring.py).
    """
    from app.config import settings

    original = settings.live_persona_enrichment
    settings.live_persona_enrichment = False
    yield
    settings.live_persona_enrichment = original
