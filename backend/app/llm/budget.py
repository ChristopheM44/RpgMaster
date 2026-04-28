from __future__ import annotations

import logging
from contextvars import ContextVar
from dataclasses import dataclass, field
from typing import Any, Optional

from app.config import get_llm_budget_mode

logger = logging.getLogger(__name__)

SOBER_MODE = "sober"
_SIMPLE_COMBAT_ACTIONS = {
    "attack",
    "cast_spell",
    "death_save",
    "stabilize",
    "dodge",
    "dash",
    "disengage",
    "hide",
    "wait",
}
_LLM_COMBAT_ACTIONS = {"free_text", "talk", "parley", "negotiate", "intimidate", "persuade"}
_COMPANION_SOCIAL_MARKERS = (
    "que pensez",
    "qu'en pensez",
    "vous en pensez",
    "votre avis",
    "vos avis",
    "compagnon",
    "compagnons",
    "on fait quoi",
    "que fait-on",
    "vous proposez",
)


@dataclass
class LLMBudgetScope:
    session_id: str
    reason: str
    counts: dict[str, int] = field(
        default_factory=lambda: {"gm": 0, "player": 0, "party": 0, "other": 0}
    )


_current_scope: ContextVar[Optional[LLMBudgetScope]] = ContextVar(
    "llm_budget_scope",
    default=None,
)


def is_sober_mode() -> bool:
    return get_llm_budget_mode().strip().lower() == SOBER_MODE


def begin_llm_call_scope(session_id: str, reason: str) -> tuple[Any, LLMBudgetScope]:
    scope = LLMBudgetScope(session_id=session_id, reason=reason)
    token = _current_scope.set(scope)
    return token, scope


def end_llm_call_scope(token: Any, scope: LLMBudgetScope) -> None:
    logger.info(
        "LLM budget: session=%s reason=%s counts=%s mode=%s",
        scope.session_id,
        scope.reason,
        dict(scope.counts),
        get_llm_budget_mode(),
    )
    _current_scope.reset(token)


def record_llm_call(kind: str) -> None:
    normalized = kind if kind in {"gm", "player", "party"} else "other"
    scope = _current_scope.get()
    if scope is None:
        logger.debug("LLM call outside action scope: kind=%s", normalized)
        return
    scope.counts[normalized] = scope.counts.get(normalized, 0) + 1


def is_companion_social_prompt(content: Optional[str]) -> bool:
    text = (content or "").strip().lower()
    return any(marker in text for marker in _COMPANION_SOCIAL_MARKERS)


def should_use_gm_for_action(
    *,
    phase: str,
    action_type: str,
    actor_kind: str,
    content: Optional[str],
    roll_results: Optional[dict[str, Any]],
) -> bool:
    """Return whether the action needs a GM LLM narration under the current budget."""
    del action_type, actor_kind, roll_results
    if not is_sober_mode():
        return True

    phase_upper = phase.upper()
    if phase_upper == "COMBAT":
        return True

    if is_companion_social_prompt(content):
        return False
    return True
