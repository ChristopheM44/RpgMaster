from __future__ import annotations

import base64
from unittest.mock import AsyncMock

from app.api import routes_admin
from app.llm.voxtral_client import TtsRouter


async def test_tts_settings_apply_voice_defaults(async_client, monkeypatch) -> None:
    monkeypatch.setattr(
        routes_admin.tts_router,
        "_runtime",
        {"tts_enabled": True, "tts_backend": "kokoro"},
    )

    response = await async_client.get("/api/admin/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["npc_voice_enabled"] is True
    assert data["gm_voice"] == {
        "preset_id": "ff_siwis",
        "voice_id_local": "ff_siwis",
        "lang": "fr-fr",
        "speed": 0.9,
    }


async def test_tts_settings_update_voice_config(async_client, monkeypatch) -> None:
    monkeypatch.setattr(routes_admin.tts_router, "_runtime", {})
    monkeypatch.setattr(routes_admin.tts_router, "_save_runtime", lambda: None)

    response = await async_client.put(
        "/api/admin/settings",
        json={
            "tts_enabled": True,
            "tts_backend": "kokoro",
            "npc_voice_enabled": False,
            "gm_voice": {
                "preset_id": "am_michael",
                "voice_id_local": "am_michael",
                "lang": "fr-fr",
                "speed": 0.85,
            },
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["tts_enabled"] is True
    assert data["npc_voice_enabled"] is False
    assert data["gm_voice"]["voice_id_local"] == "am_michael"
    assert data["gm_voice"]["speed"] == 0.85


async def test_tts_settings_reject_invalid_speed(async_client) -> None:
    response = await async_client.put(
        "/api/admin/settings",
        json={
            "gm_voice": {
                "preset_id": "ff_siwis",
                "voice_id_local": "ff_siwis",
                "lang": "fr-fr",
                "speed": 2.0,
            },
        },
    )

    assert response.status_code == 422


async def test_tts_preview_returns_audio_base64(async_client, monkeypatch) -> None:
    preview = AsyncMock(return_value=b"WAV_BYTES")
    monkeypatch.setattr(routes_admin.tts_router, "preview", preview)

    response = await async_client.post(
        "/api/admin/tts/preview",
        json={
            "text": "Bonjour.",
            "gm_voice": {
                "preset_id": "ff_siwis",
                "voice_id_local": "ff_siwis",
                "lang": "fr-fr",
                "speed": 0.9,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["audio_b64"] == base64.b64encode(b"WAV_BYTES").decode("ascii")
    preview.assert_awaited_once()


async def test_tts_router_publishes_generation_status(monkeypatch) -> None:
    published: list[tuple[str, dict]] = []

    async def publish_audio(session_id: str, payload: dict) -> None:
        published.append((session_id, payload))

    router = TtsRouter(publish_audio=publish_audio)
    monkeypatch.setattr(
        router,
        "_runtime",
        {"tts_enabled": True, "tts_backend": "kokoro"},
    )
    monkeypatch.setattr(router, "synthesize_bytes", AsyncMock(return_value=b"WAV_BYTES"))

    await router.synthesize_and_broadcast(
        "Bonjour.",
        "session-1",
        "narration-1",
        voice="ff_siwis",
        lang="fr-fr",
        speed=0.9,
        speaker="Maire Valerius",
        speaker_kind="npc",
    )

    assert published == [
        (
            "session-1",
            {
                "narration_id": "narration-1",
                "status": "generating",
                "speaker": "Maire Valerius",
                "speaker_kind": "npc",
            },
        ),
        (
            "session-1",
            {
                "narration_id": "narration-1",
                "status": "ready",
                "speaker": "Maire Valerius",
                "speaker_kind": "npc",
                "audio_b64": base64.b64encode(b"WAV_BYTES").decode("ascii"),
            },
        ),
    ]
