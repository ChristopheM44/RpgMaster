"""Client TTS dual-backend : Kokoro-ONNX (local) et vLLM-Omni (Voxtral).

Backends disponibles :
    "kokoro" — Kokoro-ONNX v1.0 via subprocess isolé (Python 3.11+, tts_service/)
    "vllm"   — Voxtral-4B via vLLM-Omni, endpoint OpenAI-compatible POST /v1/audio/speech

Le TtsRouter ne bloque jamais le game loop : synthesize_and_broadcast() est
conçu pour être lancé en fire-and-forget via asyncio.create_task().
"""
from __future__ import annotations

import asyncio
import base64
import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Chemins du micro-service Kokoro
# ---------------------------------------------------------------------------

# Racine du projet (backend/app/llm/ → ../../.. → projet root)
_PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
_TTS_SERVICE_DIR = _PROJECT_ROOT / "tts_service"
_SYNTHESIZE_SCRIPT = _TTS_SERVICE_DIR / "synthesize.py"
_KOKORO_VENV_PYTHON = _TTS_SERVICE_DIR / ".venv" / "bin" / "python"

# Fichiers modèles (téléchargés automatiquement par synthesize.py)
_KOKORO_MODEL = _TTS_SERVICE_DIR / "models" / "kokoro-v1.0.onnx"
_KOKORO_VOICES = _TTS_SERVICE_DIR / "models" / "voices-v1.0.bin"

# ---------------------------------------------------------------------------
# Retry config (vLLM-Omni seulement)
# ---------------------------------------------------------------------------

_MAX_RETRIES = 3
_BASE_DELAY = 1.0


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class VoxtralError(Exception):
    """Erreur de génération TTS (tous backends)."""


AudioPublisher = Callable[[str, dict[str, Any]], Awaitable[None]]

DEFAULT_GM_VOICE: dict[str, Any] = {
    "preset_id": "ff_siwis",
    "voice_id_local": "ff_siwis",
    "lang": "fr-fr",
    "speed": 0.9,
}
DEFAULT_NPC_VOICE_ENABLED = True
MIN_TTS_SPEED = 0.5
MAX_TTS_SPEED = 1.5


async def _noop_audio_publisher(session_id: str, payload: dict[str, Any]) -> None:
    return None


def _bounded_speed(value: Any, default: float = DEFAULT_GM_VOICE["speed"]) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        parsed = default
    return min(MAX_TTS_SPEED, max(MIN_TTS_SPEED, parsed))


def normalize_voice_settings(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Return a complete, safe local voice config from runtime/user input."""
    merged = dict(DEFAULT_GM_VOICE)
    if isinstance(raw, dict):
        merged.update(raw)

    voice_id = str(merged.get("voice_id_local") or DEFAULT_GM_VOICE["voice_id_local"]).strip()
    lang = str(merged.get("lang") or DEFAULT_GM_VOICE["lang"]).strip().lower()
    preset_id = str(merged.get("preset_id") or voice_id).strip()

    if not voice_id:
        voice_id = DEFAULT_GM_VOICE["voice_id_local"]
    if not lang:
        lang = DEFAULT_GM_VOICE["lang"]
    if not preset_id:
        preset_id = voice_id

    return {
        "preset_id": preset_id,
        "voice_id_local": voice_id,
        "lang": lang,
        "speed": _bounded_speed(merged.get("speed")),
    }


# ---------------------------------------------------------------------------
# KokoroClient — subprocess isolé Python 3.11
# ---------------------------------------------------------------------------


class KokoroClient:
    """Client TTS Kokoro-ONNX via subprocess isolé.

    Le backend principal tourne en Python 3.9 (incompatible kokoro-onnx).
    Ce client délègue la synthèse au venv Python 3.11 de tts_service/.
    """

    # Semaphore pour éviter des appels ONNX concurrents (thread-safety)
    _sem: asyncio.Semaphore = asyncio.Semaphore(1)
    _timeout: float = 60.0  # secondes

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        lang: str | None = None,
        speed: float | None = None,
    ) -> bytes:
        """Synthétise *text* et retourne les bytes WAV.

        Args:
            text: Texte à synthétiser.
            voice: ID de voix Kokoro (ex: 'ff_siwis', 'am_michael'). Default: ff_siwis.
            lang: Langue ('fr-fr', 'en-us'...). Default: fr-fr.
            speed: Facteur de vitesse 0.5-2.0. Default: 1.0.

        Returns:
            Bytes du fichier WAV.

        Raises:
            VoxtralError: Si le subprocess échoue ou retourne des bytes vides.
        """
        if not _SYNTHESIZE_SCRIPT.exists():
            raise VoxtralError(
                f"Script synthesize.py introuvable : {_SYNTHESIZE_SCRIPT}"
            )
        if not _KOKORO_VENV_PYTHON.exists():
            raise VoxtralError(
                f"Python Kokoro introuvable : {_KOKORO_VENV_PYTHON}. "
                "Créez le venv dans tts_service/ avec Python 3.11."
            )

        cmd = [
            str(_KOKORO_VENV_PYTHON),
            str(_SYNTHESIZE_SCRIPT),
            "--text", text,
        ]
        if voice:
            cmd.extend(["--voice", voice])
        if lang:
            cmd.extend(["--lang", lang])
        if speed is not None:
            cmd.extend(["--speed", str(speed)])

        async with self._sem:
            try:
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
                try:
                    wav_bytes, stderr_bytes = await asyncio.wait_for(
                        proc.communicate(), timeout=self._timeout
                    )
                except TimeoutError:
                    proc.kill()
                    raise VoxtralError(
                        f"Kokoro subprocess timeout ({self._timeout}s)"
                    )

                if proc.returncode != 0:
                    err = stderr_bytes.decode(errors="replace")
                    raise VoxtralError(
                        f"Kokoro subprocess code={proc.returncode} : {err[:200]}"
                    )

                if not wav_bytes:
                    raise VoxtralError("Kokoro a retourné 0 bytes audio.")

                logger.debug(
                    "Kokoro TTS : %d bytes générés pour '%s...'",
                    len(wav_bytes),
                    text[:40],
                )
                return wav_bytes

            except VoxtralError:
                raise
            except Exception as exc:
                raise VoxtralError(f"Erreur subprocess Kokoro : {exc}") from exc

    async def is_available(self) -> bool:
        """Vérifie que le script et le venv Kokoro sont présents."""
        return _SYNTHESIZE_SCRIPT.exists() and _KOKORO_VENV_PYTHON.exists()


# ---------------------------------------------------------------------------
# VLLMVoxtralClient — HTTP vers vLLM-Omni
# ---------------------------------------------------------------------------


class VLLMVoxtralClient:
    """Client HTTP pour le serveur vLLM-Omni (endpoint OpenAI-compatible TTS).

    Endpoint : POST /v1/audio/speech
    Body : { model, input, voice?, response_format }
    Response : bytes audio (WAV ou MP3 selon response_format).
    """

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
    ) -> None:
        self.base_url = (base_url or settings.voxtral_base_url).rstrip("/")
        self.model = model or settings.voxtral_model

    async def synthesize(
        self,
        text: str,
        voice: str | None = None,
        lang: str | None = None,
        speed: float | None = None,
    ) -> bytes:
        """Synthétise *text* via vLLM-Omni et retourne les bytes WAV.

        Raises:
            VoxtralError: Si le serveur est injoignable ou retourne une erreur.
        """
        _ = (lang, speed)
        payload = {
            "model": self.model,
            "input": text,
            "response_format": "wav",
        }
        if voice:
            payload["voice"] = voice

        delay = _BASE_DELAY
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.base_url}/v1/audio/speech",
                        json=payload,
                    )
                    response.raise_for_status()
                    return response.content
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as exc:
                last_exc = exc
                if attempt == _MAX_RETRIES:
                    break
                logger.warning(
                    "vLLM-Omni tentative %d/%d échouée : %s — retry dans %.1fs",
                    attempt, _MAX_RETRIES, exc, delay,
                )
                await asyncio.sleep(delay)
                delay *= 2

        raise VoxtralError(
            f"vLLM-Omni injoignable après {_MAX_RETRIES} tentatives : {last_exc}"
        ) from last_exc

    async def is_available(self) -> bool:
        """Vérifie que le serveur vLLM-Omni répond."""
        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False


# ---------------------------------------------------------------------------
# TtsRouter — orchestrateur + fire-and-forget
# ---------------------------------------------------------------------------


class TtsRouter:
    """Orchestre le choix de backend TTS et la diffusion audio.

    Configuration runtime (modifiable sans redémarrage) :
        tts_router.configure(enabled=True, backend="kokoro")

    Usage fire-and-forget :
        asyncio.create_task(
            tts_router.synthesize_and_broadcast(text, session_id, narration_id)
        )
    """

    _RUNTIME_FILE = Path(__file__).parent.parent.parent / "runtime_settings.json"

    def __init__(self, publish_audio: AudioPublisher | None = None) -> None:
        self._kokoro = KokoroClient()
        self._vllm = VLLMVoxtralClient()
        # Runtime overrides chargés depuis le fichier de persistance
        self._runtime: dict = self._load_runtime()
        self._publish_audio: AudioPublisher = publish_audio or _noop_audio_publisher

    def configure_audio_publisher(self, publish_audio: AudioPublisher | None) -> None:
        self._publish_audio = publish_audio or _noop_audio_publisher

    # ------------------------------------------------------------------
    # Configuration runtime
    # ------------------------------------------------------------------

    def _load_runtime(self) -> dict:
        """Charge les paramètres runtime persistés (si le fichier existe)."""
        if self._RUNTIME_FILE.exists():
            try:
                with self._RUNTIME_FILE.open(encoding="utf-8") as f:
                    return json.load(f)
            except Exception as exc:
                logger.warning("Impossible de lire runtime_settings.json : %s", exc)
        return {}

    def _save_runtime(self) -> None:
        """Persiste les paramètres runtime dans un fichier JSON."""
        try:
            with self._RUNTIME_FILE.open("w", encoding="utf-8") as f:
                json.dump(self._runtime, f, indent=2)
        except Exception as exc:
            logger.warning("Impossible d'écrire runtime_settings.json : %s", exc)

    def configure(
        self,
        enabled: bool | None = None,
        backend: str | None = None,
        gm_voice: dict[str, Any] | None = None,
        npc_voice_enabled: bool | None = None,
    ) -> None:
        """Met à jour la configuration TTS en mémoire et la persiste."""
        if enabled is not None:
            self._runtime["tts_enabled"] = enabled
        if backend is not None:
            if backend not in ("kokoro", "vllm"):
                raise ValueError(f"Backend inconnu : {backend!r}. Valeurs : 'kokoro', 'vllm'")
            self._runtime["tts_backend"] = backend
        if gm_voice is not None:
            self._runtime["gm_voice"] = normalize_voice_settings(gm_voice)
        if npc_voice_enabled is not None:
            self._runtime["npc_voice_enabled"] = bool(npc_voice_enabled)
        self._save_runtime()

    @property
    def tts_enabled(self) -> bool:
        return self._runtime.get("tts_enabled", settings.voxtral_enabled)

    @property
    def tts_backend(self) -> str:
        return self._runtime.get("tts_backend", settings.tts_backend)

    @property
    def gm_voice(self) -> dict[str, Any]:
        return normalize_voice_settings(self._runtime.get("gm_voice"))

    @property
    def npc_voice_enabled(self) -> bool:
        return bool(self._runtime.get("npc_voice_enabled", DEFAULT_NPC_VOICE_ENABLED))

    def get_settings(self) -> dict:
        """Retourne l'état courant des paramètres TTS (pour l'API admin)."""
        return {
            "tts_enabled": self.tts_enabled,
            "tts_backend": self.tts_backend,
            "tts_async": settings.tts_async,
            "voxtral_base_url": settings.voxtral_base_url,
            "voxtral_model": settings.voxtral_model,
            "gm_voice": self.gm_voice,
            "npc_voice_enabled": self.npc_voice_enabled,
        }

    def _get_client(self):
        """Retourne le client actif selon le backend configuré."""
        if self.tts_backend == "kokoro":
            return self._kokoro
        return self._vllm

    async def synthesize_bytes(
        self,
        text: str,
        *,
        voice: str | None = None,
        lang: str | None = None,
        speed: float | None = None,
    ) -> bytes:
        """Synthétise *text* via le backend actif et retourne les bytes WAV."""
        client = self._get_client()
        return await client.synthesize(text, voice=voice, lang=lang, speed=speed)

    async def preview(
        self,
        text: str,
        *,
        gm_voice: dict[str, Any] | None = None,
    ) -> bytes:
        """Generate preview audio without requiring TTS to be enabled globally."""
        voice_settings = normalize_voice_settings(gm_voice) if gm_voice else self.gm_voice
        return await self.synthesize_bytes(
            text,
            voice=voice_settings["voice_id_local"],
            lang=voice_settings["lang"],
            speed=voice_settings["speed"],
        )

    # ------------------------------------------------------------------
    # Synthèse fire-and-forget
    # ------------------------------------------------------------------

    async def synthesize_and_broadcast(
        self,
        text: str,
        session_id: str,
        narration_id: str | None = None,
        voice: str | None = None,
        lang: str | None = None,
        speed: float | None = None,
    ) -> None:
        """Synthétise *text* et publie un événement AUDIO sur le bus.

        Conçu pour être lancé en fire-and-forget :
            asyncio.create_task(tts_router.synthesize_and_broadcast(...))

        Ne lève jamais d'exception — les erreurs sont loguées silencieusement.
        """
        if not self.tts_enabled:
            return

        narration_id = narration_id or str(uuid.uuid4())
        try:
            wav_bytes = await self.synthesize_bytes(
                text,
                voice=voice,
                lang=lang,
                speed=speed,
            )
            audio_b64 = base64.b64encode(wav_bytes).decode("ascii")

            await self._publish_audio(
                session_id,
                {
                    "audio_b64": audio_b64,
                    "narration_id": narration_id,
                },
            )
            logger.debug(
                "TTS audio broadcast : session=%s narration=%s backend=%s bytes=%d",
                session_id, narration_id, self.tts_backend, len(wav_bytes),
            )

        except VoxtralError as exc:
            logger.warning(
                "TTS échec (session=%s backend=%s) : %s — jeu continue sans audio.",
                session_id, self.tts_backend, exc,
            )
        except Exception as exc:
            logger.error(
                "TTS erreur inattendue (session=%s) : %s", session_id, exc
            )

    async def health(self) -> dict:
        """Vérifie la disponibilité de chaque backend."""
        kokoro_ok, vllm_ok = await asyncio.gather(
            self._kokoro.is_available(),
            self._vllm.is_available(),
        )
        return {"kokoro": kokoro_ok, "vllm": vllm_ok}


# ---------------------------------------------------------------------------
# Singleton module-level
# ---------------------------------------------------------------------------

tts_router = TtsRouter()
