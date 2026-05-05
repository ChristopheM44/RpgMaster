"""Prompt helpers for clearly delimiting untrusted player input."""
from __future__ import annotations

USER_INPUT_START = "<<<USER_INPUT_START>>>"
USER_INPUT_END = "<<<USER_INPUT_END>>>"


def delimit_user_input(text: str | None) -> str:
    """Wrap player-provided text so prompts treat it as data, not instructions."""
    clean = (text or "").strip()
    if not clean:
        return ""
    return f"{USER_INPUT_START}\n{clean}\n{USER_INPUT_END}"
