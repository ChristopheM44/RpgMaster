from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes_admin import router as admin_router
from app.api.routes_campaign import router as campaign_router
from app.api.routes_character import router as character_router
from app.api.routes_encounters import router as encounters_router
from app.api.routes_game import router as game_router
from app.api.routes_pregen import router as pregen_router
from app.api.routes_session import router as session_router
from app.api.routes_srd import router as srd_router
from app.api.ws_game import router as ws_router
from app.config import get_cors_origins
from app.llm.voxtral_client import tts_router
from app.security import (
    access_token_required,
    request_has_valid_access_token,
    validate_access_token_configuration,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: charger les paramètres TTS persistés
    tts_router._runtime = tts_router._load_runtime()
    yield
    # Shutdown: cleanup


def create_app() -> FastAPI:
    validate_access_token_configuration()

    app = FastAPI(
        title="RpgMaster",
        description="AI-powered D&D 5.2 Game Master",
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=get_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-RpgMaster-Token"],
    )

    @app.middleware("http")
    async def require_local_access_token(request: Request, call_next):
        if (
            access_token_required()
            and request.url.path.startswith("/api/")
            and request.method != "OPTIONS"
            and not request_has_valid_access_token(request)
        ):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or missing access token."},
            )
        return await call_next(request)

    app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
    app.include_router(campaign_router, prefix="/api/campaigns", tags=["campaigns"])
    app.include_router(session_router, prefix="/api/sessions", tags=["sessions"])
    app.include_router(pregen_router, prefix="/api/characters", tags=["characters"])
    app.include_router(character_router, prefix="/api/characters", tags=["characters"])
    app.include_router(encounters_router, prefix="/api/encounters", tags=["encounters"])
    app.include_router(game_router, prefix="/api/game", tags=["game"])
    app.include_router(srd_router, prefix="/api/srd", tags=["srd"])
    app.include_router(ws_router, tags=["websocket"])

    return app


app = create_app()
