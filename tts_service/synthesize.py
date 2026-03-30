"""Script CLI Kokoro-ONNX TTS pour RpgMaster.

Usage:
    python synthesize.py --text "Texte à synthétiser"

Output:
    Bytes WAV sur stdout (format WAV standard).
    Logs de diagnostic sur stderr.

Modèles téléchargés automatiquement à la première exécution :
    - kokoro-v1.0.onnx  (~310 Mo)
    - voices-v1.0.bin   (~3 Mo)
"""
from __future__ import annotations

import argparse
import io
import os
import sys
import urllib.request
from pathlib import Path

# Répertoire des modèles : tts_service/models/
_MODELS_DIR = Path(__file__).parent / "models"
_MODEL_PATH = _MODELS_DIR / "kokoro-v1.0.onnx"
_VOICES_PATH = _MODELS_DIR / "voices-v1.0.bin"

_MODEL_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/kokoro-v1.0.onnx"
)
_VOICES_URL = (
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/"
    "model-files-v1.0/voices-v1.0.bin"
)

# Paramètres vocaux pour le français
_VOICE = "ff_siwis"
_LANG = "fr-fr"
_SPEED = 1.0


def _ensure_models() -> None:
    """Télécharge les modèles si absents."""
    _MODELS_DIR.mkdir(exist_ok=True)

    if not _MODEL_PATH.exists():
        print(f"[TTS] Téléchargement du modèle ONNX ({_MODEL_PATH.name})...", file=sys.stderr)
        urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
        print("[TTS] Modèle téléchargé.", file=sys.stderr)

    if not _VOICES_PATH.exists():
        print(f"[TTS] Téléchargement des voix ({_VOICES_PATH.name})...", file=sys.stderr)
        urllib.request.urlretrieve(_VOICES_URL, _VOICES_PATH)
        print("[TTS] Voix téléchargées.", file=sys.stderr)


def synthesize(text: str) -> bytes:
    """Génère un fichier WAV à partir du texte.

    Returns:
        Bytes du fichier WAV (24000 Hz, mono).
    """
    from kokoro_onnx import Kokoro
    import soundfile as sf

    _ensure_models()

    kokoro = Kokoro(str(_MODEL_PATH), str(_VOICES_PATH))
    samples, sample_rate = kokoro.create(text, voice=_VOICE, speed=_SPEED, lang=_LANG)

    buf = io.BytesIO()
    sf.write(buf, samples, sample_rate, format="WAV")
    buf.seek(0)
    return buf.read()


def main() -> None:
    parser = argparse.ArgumentParser(description="Kokoro TTS CLI")
    parser.add_argument("--text", required=True, help="Texte à synthétiser")
    args = parser.parse_args()

    text = args.text.strip()
    if not text:
        print("[TTS] Texte vide, rien à synthétiser.", file=sys.stderr)
        sys.exit(1)

    print(f"[TTS] Synthèse : {text[:60]}{'...' if len(text) > 60 else ''}", file=sys.stderr)

    try:
        wav_bytes = synthesize(text)
        # Écriture des bytes WAV sur stdout (mode binaire)
        sys.stdout.buffer.write(wav_bytes)
        print(f"[TTS] OK — {len(wav_bytes)} bytes générés.", file=sys.stderr)
    except Exception as exc:
        print(f"[TTS] Erreur : {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
