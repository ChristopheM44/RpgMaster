from __future__ import annotations

import json

from app import config


def test_update_llm_settings_normalizes_ollama_runtime_values(
    monkeypatch,
    tmp_path,
) -> None:
    runtime_file = tmp_path / "llm_runtime.json"

    monkeypatch.setattr(config, "_RUNTIME_LLM_FILE", runtime_file, raising=False)
    monkeypatch.setattr(config, "_runtime_llm", {}, raising=False)
    monkeypatch.setattr(config.settings, "ollama_base_url", "http://localhost:11434")

    config.update_llm_settings(
        ollama_base_url=" https://ollama.com/api/ ",
        ollama_api_key="  secret-key  ",
    )

    assert config.get_ollama_url() == "https://ollama.com"
    assert config.get_ollama_api_key() == "secret-key"
    assert config.get_ollama_auth_headers() == {
        "Authorization": "Bearer secret-key"
    }

    saved = json.loads(runtime_file.read_text(encoding="utf-8"))
    assert saved["ollama_base_url"] == "https://ollama.com"
    assert saved["ollama_api_key"] == "secret-key"


def test_get_ollama_url_ignores_blank_runtime_override(monkeypatch) -> None:
    monkeypatch.setattr(
        config,
        "_runtime_llm",
        {"ollama_base_url": "   "},
        raising=False,
    )
    monkeypatch.setattr(config.settings, "ollama_base_url", "http://localhost:11434")

    assert config.get_ollama_url() == "http://localhost:11434"
