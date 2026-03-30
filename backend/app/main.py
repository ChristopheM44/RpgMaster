from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_admin import router as admin_router
from app.api.routes_session import router as session_router
from app.api.routes_character import router as character_router
from app.api.routes_game import router as game_router
from app.api.routes_srd import router as srd_router
from app.api.ws_game import router as ws_router
from app.llm.voxtral_client import tts_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: charger les paramètres TTS persistés
    tts_router._runtime = tts_router._load_runtime()
    yield
    # Shutdown: cleanup


def create_app() -> FastAPI:
    app = FastAPI(
        title="RpgMaster",
        description="AI-powered D&D 5.2 Game Master",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
    app.include_router(session_router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(character_router, prefix="/api/characters", tags=["characters"])
    app.include_router(game_router, prefix="/api/game", tags=["game"])
    app.include_router(srd_router, prefix="/api/srd", tags=["srd"])
    app.include_router(ws_router, tags=["websocket"])

    return app


app = create_app()
