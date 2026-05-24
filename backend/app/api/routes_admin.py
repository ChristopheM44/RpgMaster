"""Routes d'administration — configuration TTS runtime + état LLM.

Endpoints :
    GET  /api/admin/settings          → paramètres TTS courants
    PUT  /api/admin/settings          → mise à jour partielle TTS
    GET  /api/admin/tts/health        → disponibilité de chaque backend TTS
    GET  /api/admin/llm/health        → état Ollama (disponibilité + modèles)
    GET  /api/admin/llm/settings      → paramètres LLM courants (provider inclus)
    PUT  /api/admin/llm/settings      → mise à jour provider/URL/modèles/clé API (runtime)
    GET  /api/admin/llm/model-info    → caractéristiques Ollama du modèle sélectionné
    POST /api/admin/llm/ping          → test rapide d'un appel LLM (provider courant)
"""
from __future__ import annotations

import logging
import re
import time
from typing import Any, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field, field_validator

from app.api.rate_limit import FixedWindowRateLimiter, client_ip
from app.config import (
    get_gm_model,
    get_llm_provider,
    get_ollama_auth_headers,
    get_ollama_url,
    get_openai_base_url,
    get_player_model,
    get_source_max_chars,
    is_ollama_api_key_set,
    is_openai_api_key_set,
    update_llm_settings,
)
from app.llm.model_router import router as llm_router
from app.llm.voxtral_client import tts_router

logger = logging.getLogger(__name__)

router = APIRouter()
llm_ping_limiter = FixedWindowRateLimiter(max_requests=5, window_seconds=60.0)


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
    models: list[str]
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
    source_max_chars: int


class OllamaModelInfoResponse(BaseModel):
    model: str
    family: Optional[str] = None
    families: list[str] = Field(default_factory=list)
    parameter_size: Optional[str] = None
    quantization_level: Optional[str] = None
    format: Optional[str] = None
    context_length: Optional[int] = None
    num_ctx: Optional[int] = None


class LlmPingResponse(BaseModel):
    ok: bool
    provider: str
    model: str
    latency_ms: Optional[int] = None
    sample_response: Optional[str] = None
    error: Optional[str] = None


class LlmSettingsUpdate(BaseModel):
    ollama_base_url: Optional[str] = None
    gm_model: Optional[str] = None
    player_model: Optional[str] = None
    llm_provider: Optional[str] = None
    openai_base_url: Optional[str] = None
    openai_api_key: Optional[str] = None
    ollama_api_key: Optional[str] = None
    source_max_chars: Optional[int] = Field(default=None, ge=1_000, le=2_000_000)

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ("ollama", "openai_compatible"):
            raise ValueError("llm_provider doit être 'ollama' ou 'openai_compatible'")
        return v


def _to_positive_int(value: Any) -> Optional[int]:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None


def _model_info_context_length(model_info: Any) -> Optional[int]:
    if not isinstance(model_info, dict):
        return None
    values = []
    for key, value in model_info.items():
        normalized_key = str(key).lower()
        if normalized_key == "context_length" or normalized_key.endswith(".context_length"):
            parsed = _to_positive_int(value)
            if parsed is not None:
                values.append(parsed)
    return max(values) if values else None


def _model_info_num_ctx(*texts: Any) -> Optional[int]:
    for text in texts:
        if not isinstance(text, str):
            continue
        match = re.search(r"(?im)^\s*(?:PARAMETER\s+)?num_ctx\s+(\d+)\s*$", text)
        if match:
            return _to_positive_int(match.group(1))
    return None


def _ollama_model_info_response(model: str, payload: dict[str, Any]) -> OllamaModelInfoResponse:
    details = payload.get("details") if isinstance(payload.get("details"), dict) else {}
    families = details.get("families")
    return OllamaModelInfoResponse(
        model=model,
        family=details.get("family"),
        families=[str(item) for item in families] if isinstance(families, list) else [],
        parameter_size=details.get("parameter_size"),
        quantization_level=details.get("quantization_level"),
        format=details.get("format"),
        context_length=_model_info_context_length(payload.get("model_info")),
        num_ctx=_model_info_num_ctx(payload.get("parameters"), payload.get("modelfile")),
    )


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
        async with httpx.AsyncClient(
            timeout=5.0,
            headers=get_ollama_auth_headers(),
        ) as client:
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
        source_max_chars=get_source_max_chars(),
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
        source_max_chars=body.source_max_chars,
    )
    return LlmSettingsResponse(
        ollama_base_url=get_ollama_url(),
        gm_model=get_gm_model(),
        player_model=get_player_model(),
        llm_provider=get_llm_provider(),
        openai_base_url=get_openai_base_url(),
        api_key_set=is_openai_api_key_set(),
        ollama_api_key_set=is_ollama_api_key_set(),
        source_max_chars=get_source_max_chars(),
    )


@router.get("/llm/model-info", response_model=OllamaModelInfoResponse)
async def get_llm_model_info(model: str = Query(..., min_length=1)) -> OllamaModelInfoResponse:
    """Retourne les caractéristiques déclarées par Ollama pour un modèle."""
    model_name = model.strip()
    if not model_name:
        raise HTTPException(status_code=422, detail="model is required")
    try:
        async with httpx.AsyncClient(
            timeout=5.0,
            headers=get_ollama_auth_headers(),
        ) as client:
            resp = await client.post(f"{get_ollama_url()}/api/show", json={"model": model_name})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Infos modèle Ollama indisponibles: {type(exc).__name__}: {exc}",
        )
    return _ollama_model_info_response(model_name, data)


@router.post("/llm/ping", response_model=LlmPingResponse)
async def ping_llm(request: Request) -> LlmPingResponse:
    """Envoie un prompt trivial au provider LLM actif pour vérifier la configuration.

    Utile pour diagnostiquer rapidement un provider cloud mal configuré
    (URL/clé/modèle incorrects) qui ferait taire silencieusement les
    compagnons IA (fallback `wait`).
    """
    llm_ping_limiter.check(f"llm_ping:{client_ip(request)}")
    provider = get_llm_provider()
    model = get_player_model()
    client = llm_router.get_player_client()
    start = time.perf_counter()
    try:
        raw = await client.chat(
            messages=[
                {"role": "system", "content": "Réponds simplement 'pong'."},
                {"role": "user", "content": "ping"},
            ],
            temperature=0.0,
            max_tokens=16,
        )
    except Exception as exc:
        latency_ms = int((time.perf_counter() - start) * 1000)
        logger.warning("ping_llm: provider=%s model=%s failed: %s", provider, model, exc)
        return LlmPingResponse(
            ok=False,
            provider=provider,
            model=model,
            latency_ms=latency_ms,
            error=f"{type(exc).__name__}: {exc}",
        )
    latency_ms = int((time.perf_counter() - start) * 1000)
    sample = (raw or "").strip()[:200]
    return LlmPingResponse(
        ok=True,
        provider=provider,
        model=model,
        latency_ms=latency_ms,
        sample_response=sample,
    )
