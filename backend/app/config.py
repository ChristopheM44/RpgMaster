from __future__ import annotations

import json
from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama (Text LLM)
    ollama_base_url: str = "http://localhost:11434"
    gm_model: str = "mistral:7b"
    player_model: str = "mistral:7b"

    # TTS — backends disponibles : "kokoro" (local ONNX) ou "vllm" (vLLM-Omni)
    tts_backend: str = "kokoro"
    voxtral_base_url: str = "http://localhost:8091"
    voxtral_model: str = "mistralai/Voxtral-4B-TTS-2603"
    voxtral_enabled: bool = False

    # Database
    database_url: str = "sqlite+aiosqlite:///./rpgmaster.db"

    # Application
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = True
    log_level: str = "info"

    # Game
    default_language: str = "fr"
    max_context_messages: int = 20
    tts_async: bool = True
    llm_budget_mode: str = "sober"
    ollama_max_concurrent_requests: int = 1

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()

# ---------------------------------------------------------------------------
# Runtime LLM overrides (survivent aux redémarrages via llm_runtime.json)
# Surchargent les valeurs .env sans nécessiter de redémarrage du serveur.
# ---------------------------------------------------------------------------

_RUNTIME_LLM_FILE = Path(__file__).parent.parent / "llm_runtime.json"
_runtime_llm: dict = {}


def _load_runtime_llm() -> None:
    global _runtime_llm
    if _RUNTIME_LLM_FILE.exists():
        try:
            _runtime_llm = json.loads(_RUNTIME_LLM_FILE.read_text(encoding="utf-8"))
        except Exception:
            _runtime_llm = {}


def _save_runtime_llm() -> None:
    _RUNTIME_LLM_FILE.write_text(json.dumps(_runtime_llm), encoding="utf-8")


def update_llm_settings(
    ollama_base_url: str | None = None,
    gm_model: str | None = None,
    player_model: str | None = None,
    llm_budget_mode: str | None = None,
    llm_provider: str | None = None,
    openai_base_url: str | None = None,
    openai_api_key: str | None = None,
    ollama_api_key: str | None = None,
) -> None:
    """Met à jour le(s) setting(s) LLM en mémoire et persiste."""
    if ollama_base_url is not None:
        _runtime_llm["ollama_base_url"] = ollama_base_url
    if gm_model is not None:
        _runtime_llm["gm_model"] = gm_model
    if player_model is not None:
        _runtime_llm["player_model"] = player_model
    if llm_budget_mode is not None:
        _runtime_llm["llm_budget_mode"] = llm_budget_mode
    if llm_provider is not None:
        _runtime_llm["llm_provider"] = llm_provider
    if openai_base_url is not None:
        _runtime_llm["openai_base_url"] = openai_base_url
    if openai_api_key is not None:
        if openai_api_key == "":
            _runtime_llm.pop("openai_api_key", None)
        else:
            _runtime_llm["openai_api_key"] = openai_api_key
    if ollama_api_key is not None:
        if ollama_api_key == "":
            _runtime_llm.pop("ollama_api_key", None)
        else:
            _runtime_llm["ollama_api_key"] = ollama_api_key
    _save_runtime_llm()


def get_ollama_url() -> str:
    return _runtime_llm.get("ollama_base_url", settings.ollama_base_url)


def get_gm_model() -> str:
    return _runtime_llm.get("gm_model", settings.gm_model)


def get_player_model() -> str:
    return _runtime_llm.get("player_model", settings.player_model)


def get_llm_budget_mode() -> str:
    return _runtime_llm.get("llm_budget_mode", settings.llm_budget_mode)


def get_ollama_max_concurrent_requests() -> int:
    raw = _runtime_llm.get(
        "ollama_max_concurrent_requests",
        settings.ollama_max_concurrent_requests,
    )
    try:
        return max(1, int(raw))
    except (TypeError, ValueError):
        return 1


def get_ollama_api_key() -> str:
    return _runtime_llm.get("ollama_api_key", "")


def is_ollama_api_key_set() -> bool:
    return bool(get_ollama_api_key())


def get_llm_provider() -> str:
    return _runtime_llm.get("llm_provider", "ollama")


def get_openai_base_url() -> str:
    return _runtime_llm.get("openai_base_url", "")


def get_openai_api_key() -> str:
    return _runtime_llm.get("openai_api_key", "")


def is_openai_api_key_set() -> bool:
    return bool(get_openai_api_key())


_load_runtime_llm()
