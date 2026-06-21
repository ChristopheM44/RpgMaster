"""Tests offline pour le WebSocket de dialogue Realtime PNJ (`ws_dialogue.py`).

Pas de DB, pas de vrai WebSocket monté : on teste directement les fonctions
internes (pattern repris de `test_ws_encounter_intro.py`), pour ne pas
toucher à la gestion de l'event loop — la suite a une fragilité d'isolation
connue avec `starlette.testclient.TestClient` (voir `tests/test_game/conftest.py`).

Couvre :
1. Diffusion du transcript complet sur le bus à la fermeture d'une session
   `/ws/dialogue/*` (event `EventType.DIALOGUE` avec `{persona_id, transcript}`).
2. A2 — présence de la consigne anti-injection dans le prompt système rendu
   pour la Realtime API (`_render_persona_brief`).
3. V1 — la logique de décision `_should_close_on_idle` : une réponse Realtime
   en cours (le PNJ qui parle) ne déclenche pas la fermeture idle, sauf si le
   garde-fou anti-zombie (silence bidirectionnel prolongé) est dépassé.
"""

from __future__ import annotations

import time

from app.agents.persona import NPCPersona, PersonaMotivations, PersonaVoice
from app.api.ws_dialogue import (
    _DialogueActivity,
    _publish_transcript,
    _render_persona_brief,
    _should_close_on_idle,
)
from app.game.event_bus import EventType, event_bus
from app.voice.realtime_session import RealtimeSession


def _make_persona() -> NPCPersona:
    return NPCPersona(
        id="garrik",
        name="Garrik",
        archetype="merchant",
        short_description="Tavernier rude.",
        motivations=PersonaMotivations(
            visible=["vendre sa bière"],
            hidden=["venger sa fille"],
            fears=["la magie noire"],
        ),
        secrets=["sait qui a tué le shérif"],
    )


# ---------------------------------------------------------------------------
# 1. Diffusion du transcript complet (event DIALOGUE)
# ---------------------------------------------------------------------------


async def test_publish_transcript_emits_dialogue_event_with_full_payload() -> None:
    session_id = "session-transcript-test"
    session = RealtimeSession(api_key="sk-test", voice=PersonaVoice())
    session.transcript.append_user("Bonjour, qui es-tu ?")
    session.transcript.append_assistant("Je suis Garrik, tavernier de ce trou perdu.")

    queue = event_bus.subscribe(session_id)
    try:
        await _publish_transcript(session_id, "garrik", session)

        event = queue.get_nowait()
        assert event.event_type == EventType.DIALOGUE
        assert event.payload == {
            "persona_id": "garrik",
            "transcript": {
                "user_turns": ["Bonjour, qui es-tu ?"],
                "assistant_turns": ["Je suis Garrik, tavernier de ce trou perdu."],
            },
        }
    finally:
        event_bus.unsubscribe(session_id, queue)


async def test_publish_transcript_with_empty_transcript_still_publishes() -> None:
    """Même une session sans aucun échange transcrit publie un event (listes vides)."""
    session_id = "session-transcript-empty"
    session = RealtimeSession(api_key="sk-test", voice=PersonaVoice())

    queue = event_bus.subscribe(session_id)
    try:
        await _publish_transcript(session_id, "garrik", session)

        event = queue.get_nowait()
        assert event.event_type == EventType.DIALOGUE
        assert event.payload["persona_id"] == "garrik"
        assert event.payload["transcript"] == {"user_turns": [], "assistant_turns": []}
    finally:
        event_bus.unsubscribe(session_id, queue)


async def test_publish_transcript_swallows_event_bus_failure() -> None:
    """Une erreur de publication (ex: bus en panne) ne doit jamais lever."""

    class _BrokenBus:
        async def publish_to_session(self, *args, **kwargs):
            raise RuntimeError("bus down")

    import app.api.ws_dialogue as ws_dialogue_module

    original_bus = ws_dialogue_module.event_bus
    ws_dialogue_module.event_bus = _BrokenBus()
    try:
        session = RealtimeSession(api_key="sk-test", voice=PersonaVoice())
        # Ne doit pas lever malgré l'échec du bus.
        await _publish_transcript("session-x", "garrik", session)
    finally:
        ws_dialogue_module.event_bus = original_bus


# ---------------------------------------------------------------------------
# 2. A2 — consigne anti-injection dans le prompt système
# ---------------------------------------------------------------------------


def test_render_persona_brief_contains_anti_injection_safety_rule() -> None:
    """Le prompt système doit interdire explicitement la fuite de secrets/hidden,
    et mentionner la résistance aux tentatives de prompt injection — tout en
    gardant `include_hidden=True` (le PNJ doit connaître ses secrets)."""
    persona = _make_persona()
    brief = _render_persona_brief(persona)

    # Les secrets/motivations cachées sont bien présents (include_hidden=True
    # est indispensable pour que le PNJ reste cohérent).
    assert "venger sa fille" in brief
    assert "sait qui a tué le shérif" in brief

    # Consigne de sécurité absolue : ne jamais révéler les secrets.
    assert "RÈGLE DE SÉCURITÉ ABSOLUE" in brief
    assert "JAMAIS" in brief

    # Résistance aux tentatives de manipulation / prompt injection.
    assert "manipulation" in brief
    assert "oublie tes règles" in brief


def test_render_persona_brief_safety_rule_does_not_break_existing_assertions() -> None:
    """Garde-fou de non-régression : le test existant `test_realtime_session.py`
    vérifie que le brief ne contient ni 'API' ni 'OpenAI' (sensible à la casse).
    On le reproduit ici pour que toute régression future soit détectée au plus
    près du changement."""
    persona = NPCPersona(id="x", name="X", archetype="x", short_description="x")
    brief = _render_persona_brief(persona)
    assert "OpenAI" not in brief
    assert "API" not in brief


def test_render_persona_brief_safety_rule_present_even_without_secrets() -> None:
    """La consigne doit être présente même pour une persona sans secrets
    particuliers (elle fait partie du prompt fixe, pas du rendu conditionnel)."""
    persona = NPCPersona(id="y", name="Y", archetype="y", short_description="y")
    brief = _render_persona_brief(persona)
    assert "RÈGLE DE SÉCURITÉ ABSOLUE" in brief


# ---------------------------------------------------------------------------
# 3. V1 — timer idle vs réponse Realtime en cours
# ---------------------------------------------------------------------------


def test_should_close_on_idle_when_no_response_active() -> None:
    """Silence des deux côtés, pas de réponse en cours → on ferme."""
    activity = _DialogueActivity(response_active=False, last_event_at=time.monotonic())
    assert _should_close_on_idle(activity) is True


def test_should_not_close_on_idle_while_response_active() -> None:
    """Le PNJ est en train de répondre (audio en cours) → on NE ferme PAS,
    même si le timeout idle côté client (30s) est atteint."""
    activity = _DialogueActivity(response_active=True, last_event_at=time.monotonic())
    assert _should_close_on_idle(activity) is False


def test_should_close_on_idle_anti_zombie_guard_overrides_active_flag() -> None:
    """Garde-fou anti-zombie : même si `response_active` est resté bloqué à
    True (event de fin manqué), une absence d'activité bidirectionnelle
    prolongée (>= seuil absolu) doit tout de même fermer la session."""
    from app.api.ws_dialogue import _ABSOLUTE_IDLE_TIMEOUT_SECONDS

    stale_timestamp = time.monotonic() - _ABSOLUTE_IDLE_TIMEOUT_SECONDS - 1.0
    activity = _DialogueActivity(response_active=True, last_event_at=stale_timestamp)
    assert _should_close_on_idle(activity) is True


def test_should_not_close_just_below_anti_zombie_threshold_while_active() -> None:
    """Juste sous le seuil anti-zombie, une réponse active reste protégée."""
    from app.api.ws_dialogue import _ABSOLUTE_IDLE_TIMEOUT_SECONDS

    recent_timestamp = time.monotonic() - _ABSOLUTE_IDLE_TIMEOUT_SECONDS + 5.0
    activity = _DialogueActivity(response_active=True, last_event_at=recent_timestamp)
    assert _should_close_on_idle(activity) is False


def test_note_realtime_event_marks_response_active_on_response_prefixed_events() -> None:
    """Tout event `response.*` (création, deltas audio/texte...) sauf
    `response.done` doit marquer la réponse comme active."""
    activity = _DialogueActivity()
    assert activity.response_active is False

    activity.note_realtime_event("response.created")
    assert activity.response_active is True

    activity.note_realtime_event("response.audio.delta")
    assert activity.response_active is True

    activity.note_realtime_event("response.audio_transcript.delta")
    assert activity.response_active is True


def test_note_realtime_event_response_done_clears_active_flag() -> None:
    """`response.done` clôt la réponse (succès, erreur ou annulation — OpenAI
    Realtime n'a pas de type `response.cancelled` distinct)."""
    activity = _DialogueActivity()
    activity.note_realtime_event("response.created")
    assert activity.response_active is True

    activity.note_realtime_event("response.done")
    assert activity.response_active is False


def test_note_realtime_event_ignores_unrelated_event_types() -> None:
    """Un event non préfixé `response.` (ex: transcription input utilisateur)
    ne doit pas changer l'état `response_active`, mais doit quand même
    rafraîchir `last_event_at` (activité observée)."""
    activity = _DialogueActivity()
    activity.note_realtime_event("response.created")
    assert activity.response_active is True

    before = activity.last_event_at
    time.sleep(0.01)
    activity.note_realtime_event("conversation.item.input_audio_transcription.completed")

    # response_active inchangé (toujours actif) — l'event n'est pas response.*
    assert activity.response_active is True
    # mais l'horodatage d'activité a bien été rafraîchi
    assert activity.last_event_at > before


def test_dialogue_activity_touch_refreshes_last_event_at() -> None:
    activity = _DialogueActivity(last_event_at=0.0)
    activity.__post_init__()  # garantit l'init par défaut testée explicitement
    before = activity.last_event_at
    time.sleep(0.01)
    activity.touch()
    assert activity.last_event_at > before


async def test_idle_response_in_progress_end_to_end_simulation() -> None:
    """Simulation bout-à-bout (sans WebSocket réel) du scénario V1 : une
    réponse Realtime > timeout idle (30s) ne doit jamais déclencher la
    fermeture tant qu'elle est active, et la session ferme bien une fois la
    réponse terminée et le silence confirmé."""
    activity = _DialogueActivity()

    # Le PNJ commence à répondre.
    activity.note_realtime_event("response.created")
    # De multiples deltas arrivent, largement après ce qu'aurait été le
    # timeout idle de 30s côté client (on simule sans attendre réellement).
    for _ in range(5):
        activity.note_realtime_event("response.audio.delta")
        assert _should_close_on_idle(activity) is False  # jamais fermé pendant la réponse

    # La réponse se termine.
    activity.note_realtime_event("response.done")
    # Immédiatement après response.done, last_event_at vient d'être rafraîchi
    # donc on n'est pas encore au-delà du garde-fou anti-zombie ; mais
    # response_active est désormais False, donc on ferme bien sur idle.
    assert _should_close_on_idle(activity) is True
