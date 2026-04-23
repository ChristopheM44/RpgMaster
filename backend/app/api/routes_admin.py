"""Routes d'administration — configuration TTS runtime + état LLM.

Endpoints :
    GET  /api/admin/settings          → paramètres TTS courants
    PUT  /api/admin/settings          → mise à jour partielle TTS
    GET  /api/admin/tts/health        → disponibilité de chaque backend TTS
    GET  /api/admin/llm/health        → état Ollama (disponibilité + modèles)
    GET  /api/admin/llm/settings      → paramètres LLM courants (provider inclus)
    PUT  /api/admin/llm/settings      → mise à jour provider/URL/modèles/clé API (runtime)
"""
from __future__ import annotations

from typing import List, Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator

from app.config import (
    get_gm_model,
    get_llm_provider,
    get_ollama_url,
    get_openai_base_url,
    get_player_model,
    is_ollama_api_key_set,
    is_openai_api_key_set,
    update_llm_settings,
)
from app.llm.voxtral_client import tts_router

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class TtsSettingsResponse(BaseModel):
    tts_enabled: bool
    tts_backend: str
    tts_async: bool
    voxtral_base_url: str
    voxtral_model: str


class TtsSettingsUpdate(BaseModel):
    tts_enabled: Optional[bool] = None
    tts_backend: Optional[str] = None

    @field_validator("tts_backend")
    @classmethod
    def validate_backend(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("kokoro", "vllm"):
            raise ValueError("tts_backend doit être 'kokoro' ou 'vllm'")
        return v


class TtsHealthResponse(BaseModel):
    kokoro: bool
    vllm: bool


class OllamaHealthResponse(BaseModel):
    available: bool
    models: List[str]
    gm_model: str
    player_model: str


class LlmSettingsResponse(BaseModel):
    ollama_base_url: str
    gm_model: str
    player_model: str
    llm_provider: str
    openai_base_url: str
    api_key_set: bool
    ollama_api_key_set: bool


class LlmSettingsUpdate(BaseModel):
    ollama_base_url: Optional[str] = None
    gm_model: Optional[str] = None
    player_model: Optional[str] = None
    llm_provider: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    ollama_api_key: Optional[str] = None

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("ollama", "openai_compatible"):
            raise ValueError("llm_provider doit être 'ollama' ou 'openai_compatible'")
        return v


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/settings", response_model=TtsSettingsResponse)
async def get_settings() -> TtsSettingsResponse:
    """Retourne les paramètres TTS courants (en mémoire + runtime_settings.json)."""
    return TtsSettingsResponse(**tts_router.get_settings())


@router.put("/settings", response_model=TtsSettingsResponse)
async def update_settings(body: TtsSettingsUpdate) -> TtsSettingsResponse:
    """Met à jour les paramètres TTS en mémoire et les persiste."""
    try:
        tts_router.configure(
            enabled=body.tts_enabled,
            backend=body.tts_backend,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return TtsSettingsResponse(**tts_router.get_settings())


@router.get("/tts/health", response_model=TtsHealthResponse)
async def get_tts_health() -> TtsHealthResponse:
    """Vérifie la disponibilité de chaque backend TTS."""
    result = await tts_router.health()
    return TtsHealthResponse(**result)


@router.get("/llm/health", response_model=OllamaHealthResponse)
async def get_llm_health() -> OllamaHealthResponse:
    """Vérifie la disponibilité d'Ollama et retourne la liste des modèles installés."""
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{get_ollama_url()}/api/tags")
            resp.raise_for_status()
            data = resp.json()
            models = [m["name"] for m in data.get("models", [])]
        return OllamaHealthResponse(
            available=True,
            models=models,
            gm_model=get_gm_model(),
            player_model=get_player_model(),
        )
    except Exception:
        return OllamaHealthResponse(
            available=False,
            models=[],
            gm_model=get_gm_model(),
            player_model=get_player_model(),
        )


@router.get("/llm/settings", response_model=LlmSettingsResponse)
async def get_llm_settings() -> LlmSettingsResponse:
    """Retourne les paramètres LLM courants (runtime ou .env)."""
    return LlmSettingsResponse(
        ollama_base_url=get_ollama_url(),
        gm_model=get_gm_model(),
        player_model=get_player_model(),
        llm_provider=get_llm_provider(),
        openai_base_url=get_openai_base_url(),
        api_key_set=is_openai_api_key_set(),
        ollama_api_key_set=is_ollama_api_key_set(),
    )


@router.put("/llm/settings", response_model=LlmSettingsResponse)
async def update_llm_settings_endpoint(body: LlmSettingsUpdate) -> LlmSettingsResponse:
    """Met à jour le provider et/ou les paramètres LLM à chaud, sans redémarrage."""
    update_llm_settings(
        ollama_base_url=body.ollama_base_url,
        gm_model=body.gm_model,
        player_model=body.player_model,
        llm_provider=body.llm_provider,
        openai_base_url=body.openai_base_url,
        openai_api_key=body.openai_api_key,
        ollama_api_key=body.ollama_api_key,
    )
    return LlmSettingsResponse(
        ollama_base_url=get_ollama_url(),
        gm_model=get_gm_model(),
        player_model=get_player_model(),
        llm_provider=get_llm_provider(),
        openai_base_url=get_openai_base_url(),
        api_key_set=is_openai_api_key_set(),
        ollama_api_key_set=is_ollama_api_key_set(),
    )
