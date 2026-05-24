"""Deterministic bounds for durable NPC social outcomes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

ATTITUDE_ORDER = ["hostile", "unfriendly", "indifferent", "friendly", "helpful"]
_ATTITUDE_INDEX = {name: index for index, name in enumerate(ATTITUDE_ORDER)}


@dataclass(frozen=True)
class SocialRollContext:
    target_id: str
    success: bool


class SocialResolution:
    """Apply deterministic attitude bounds after an engine-resolved social roll."""

    @staticmethod
    def roll_context(roll_results: Optional[dict[str, Any]]) -> Optional[SocialRollContext]:
        if not isinstance(roll_results, dict):
            return None
        roll_type = roll_results.get("type")
        if roll_type not in (None, "skill_check"):
            return None
        target_id = str(
            roll_results.get("social_target_id")
            or roll_results.get("target_id")
            or ""
        ).strip()
        if not target_id or not isinstance(roll_results.get("success"), bool):
            return None
        return SocialRollContext(target_id=target_id, success=bool(roll_results["success"]))

    @staticmethod
    def normalize_attitude(value: Any) -> str:
        text = str(value or "").strip().lower()
        return text if text in _ATTITUDE_INDEX else "indifferent"

    @classmethod
    def bounded_attitude(
        cls,
        previous_attitude: Any,
        proposed_attitude: Optional[str],
        *,
        success: bool,
    ) -> tuple[str, bool]:
        previous = cls.normalize_attitude(previous_attitude)
        previous_index = _ATTITUDE_INDEX[previous]

        if (
            proposed_attitude is None
            or str(proposed_attitude).strip().lower() not in _ATTITUDE_INDEX
        ):
            proposed = previous
            invalid = proposed_attitude is not None
        else:
            proposed = str(proposed_attitude).strip().lower()
            invalid = False

        proposed_index = _ATTITUDE_INDEX[proposed]
        if success:
            low = previous_index
            high = min(previous_index + 1, len(ATTITUDE_ORDER) - 1)
        else:
            low = max(previous_index - 1, 0)
            high = previous_index

        bounded_index = max(low, min(proposed_index, high))
        bounded = ATTITUDE_ORDER[bounded_index]
        return bounded, invalid or bounded != proposed

    @classmethod
    def default_attitude(cls, previous_attitude: Any, *, success: bool) -> str:
        previous = cls.normalize_attitude(previous_attitude)
        if not success:
            return previous
        index = min(_ATTITUDE_INDEX[previous] + 1, len(ATTITUDE_ORDER) - 1)
        return ATTITUDE_ORDER[index]

    @classmethod
    def outcome_payload(
        cls,
        *,
        npc_id: str,
        previous_attitude: Any,
        attitude: str,
        note: str = "",
        roll_context: Optional[SocialRollContext] = None,
        clamped: bool = False,
        source: str,
        new_quest: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "npc_id": npc_id,
            "attitude": attitude,
            "previous_attitude": cls.normalize_attitude(previous_attitude),
            "note": note,
            "clamped": clamped,
            "source": source,
        }
        if roll_context is not None:
            payload["roll_success"] = roll_context.success
        if isinstance(new_quest, dict):
            payload["new_quest"] = new_quest
        return payload
