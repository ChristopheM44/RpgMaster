from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile

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
    cors_origins: str = "http://localhost:5173"
    app_access_token: str = ""
    runtime_dir: str = ".runtime"

    # Game
    default_language: str = "fr"
    max_context_messages: int = 20
    max_player_action_chars: int = 4000
    ws_event_queue_size: int = 256
    tts_async: bool = True
    llm_budget_mode: str = "sober"
    ollama_max_concurrent_requests: int = 1

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()


def get_cors_origins() -> list[str]:
    """Return configured CORS origins from comma-separated or JSON env input."""
    raw = settings.cors_origins.strip()
    if not raw:
        return []
    if raw.startswith("["):
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return [raw]
        return [str(item).strip() for item in data if str(item).strip()]
    return [item.strip() for item in raw.split(",") if item.strip()]


def get_runtime_dir() -> Path:
    """Runtime storage directory for local mutable settings and secrets."""
    path = Path(settings.runtime_dir).expanduser()
    if not path.is_absolute():
        path = Path(__file__).parent.parent / path
    return path

# ---------------------------------------------------------------------------
# Runtime LLM overrides (survivent aux redémarrages via llm_runtime.json)
# Surchargent les valeurs .env sans nécessiter de redémarrage du serveur.
# ---------------------------------------------------------------------------

_LEGACY_RUNTIME_LLM_FILE = Path(__file__).parent.parent / "llm_runtime.json"
_RUNTIME_LLM_FILE = get_runtime_dir() / "llm_runtime.json"
_runtime_llm: dict = {}


def _load_runtime_llm() -> None:
    global _runtime_llm
    runtime_file = _RUNTIME_LLM_FILE if _RUNTIME_LLM_FILE.exists() else _LEGACY_RUNTIME_LLM_FILE
    if runtime_file.exists():
        try:
            _runtime_llm = json.loads(runtime_file.read_text(encoding="utf-8"))
        except Exception:
            _runtime_llm = {}


def _save_runtime_llm() -> None:
    _RUNTIME_LLM_FILE.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(_RUNTIME_LLM_FILE.parent, 0o700)
    except OSError:
        pass
    payload = json.dumps(_runtime_llm, ensure_ascii=False)
    with NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=str(_RUNTIME_LLM_FILE.parent),
        delete=False,
    ) as tmp:
        tmp.write(payload)
        tmp_path = Path(tmp.name)
    os.chmod(tmp_path, 0o600)
    os.replace(tmp_path, _RUNTIME_LLM_FILE)


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
