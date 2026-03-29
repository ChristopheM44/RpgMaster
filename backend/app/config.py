from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Ollama (Text LLM)
    ollama_base_url: str = "http://localhost:11434"
    gm_model: str = "mistral:7b"
    player_model: str = "mistral:7b"

    # Voxtral TTS (vLLM-Omni)
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

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
