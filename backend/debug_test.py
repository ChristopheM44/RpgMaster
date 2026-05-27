import os
import sys
import logging
import asyncio

# Configure logging to see everything
logging.basicConfig(level=logging.DEBUG)

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool
from starlette.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock

import app.models
from app.db.database import Base, get_db
from app.main import create_app
from app.agents.schemas import AgentResponse
from app.game.action_resolver import ActionResolver
from app.api import ws_game

def run_debug():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    import contextlib
    @contextlib.asynccontextmanager
    async def test_lifespan(_app):
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
        # Create session
        resp = client.post("/api/sessions/", json={"name": "Debug Session"})
        print("Create session status:", resp.status_code)
        session_id = resp.json()["id"]
        print("Session ID:", session_id)

        # Setup mock GM
        mock_response = AgentResponse(content="Le sort fuse de vos doigts !", actions=[])
        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        print("Connecting to websocket...")
        try:
            with client.websocket_connect(f"/ws/game/{session_id}") as ws:
                print("Connected! Receiving initial session state...")
                state = ws.receive_json()
                print("Received state type:", state.get("event_type"))

                print("Sending cast_spell action...")
                ws.send_json({
                    "type": "action",
                    "action_type": "cast_spell",
                    "content": "Projectile magique",
                })

                print("Receiving events...")
                for i in range(5):
                    try:
                        evt = ws.receive_json()
                        print(f"Event {i}: {evt}")
                    except Exception as e:
                        print(f"Failed to receive event {i}: {type(e).__name__}: {e}")
                        break
        except Exception as e:
            print("Websocket exception:", type(e).__name__, e)
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    run_debug()
