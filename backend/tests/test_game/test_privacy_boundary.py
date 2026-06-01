"""A2 — single invariant guarding the two public views.

No GM-only secret may cross into either public-facing projection of state_data:
the AI companion view (``companion_visible_game_state``) or the human player
payload (``build_session_state_payload``). One test, planted markers, so any
future key that leaks a secret is caught here regardless of which boundary.
"""
from __future__ import annotations

import json

from app.api.ws_payloads import build_session_state_payload
from app.game.companion_visibility import companion_visible_game_state
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus

# Unique markers planted only inside GM-private locations of state_data.
TWIST_SECRET = "MARKER_TWIST_SECRET_zzz"
GM_SCENE_NOTE = "MARKER_GM_SCENE_NOTE_zzz"
HIDDEN_HOOK = "MARKER_HIDDEN_HOOK_zzz"
DOSSIER_SECRET = "MARKER_DOSSIER_SECRET_zzz"
ALL_MARKERS = (TWIST_SECRET, GM_SCENE_NOTE, HIDDEN_HOOK, DOSSIER_SECRET)


def _state_with_secrets() -> dict:
    return {
        "phase": "exploration",
        "current_scene": {
            "cols": 12,
            "rows": 12,
            "pois": [{"id": "npc_a", "name": "Aldric", "kind": "npc", "known_to_party": True}],
            "exits": [],
        },
        "npc_states": {"npc_a": {"name": "Aldric", "known_to_party": True}},
        "quests": [{"title": "Objectif public"}],
        "chronicle": [],
        # GM-private — must never surface in either public view:
        "_gm_prompt_context": {"global_secrets": [TWIST_SECRET], "fronts": ["front secret"]},
        "gm_scene_state": {"current": {"notes": [GM_SCENE_NOTE], "goal": "objectif caché"}},
        "campaign_context": {
            "player_contract": {"hook": HIDDEN_HOOK, "known_objectives": ["mission publique"]},
            "gm_dossier": {"secrets": [DOSSIER_SECRET]},
            "played_canon": {
                "established_facts": ["fait public déjà joué"],
                "revealed_secrets": ["secret déjà révélé en jeu"],
                "rolling_summary": "résumé public",
            },
        },
    }


def _assert_no_marker(blob: dict, label: str) -> None:
    serialized = json.dumps(blob, ensure_ascii=False)
    for marker in ALL_MARKERS:
        assert marker not in serialized, f"{label} a laissé fuir un secret: {marker}"


def test_companion_view_leaks_no_secret() -> None:
    visible = companion_visible_game_state(_state_with_secrets())
    _assert_no_marker(visible, "companion_visible_game_state")
    assert "_gm_prompt_context" not in visible
    assert "gm_scene_state" not in visible
    # campaign_context, if present, is reduced to its played_canon subset only.
    if "campaign_context" in visible:
        assert set(visible["campaign_context"].keys()) == {"played_canon"}


def test_player_payload_leaks_no_secret() -> None:
    active = ActiveSession(
        session_id="s1",
        phase=SessionStatus.EXPLORATION,
        state_data=_state_with_secrets(),
    )
    payload = build_session_state_payload("s1", active)
    _assert_no_marker(payload, "build_session_state_payload")
    for forbidden in ("_gm_prompt_context", "gm_scene_state", "campaign_context", "npc_states"):
        assert forbidden not in payload


def test_public_facts_still_reach_companion() -> None:
    """Sanity: the boundary filters secrets without starving the companion of
    legitimately played canon (otherwise the test could pass by leaking nothing
    *and* showing nothing)."""
    visible = companion_visible_game_state(_state_with_secrets())
    canon = visible.get("campaign_context", {}).get("played_canon", {})
    assert "fait public déjà joué" in canon.get("established_facts", [])
