"""Tests d'intégration bout-en-bout : action joueur → moteur → GM → broadcast.

Le GMAgent est mocké (Ollama non disponible en CI).
On vérifie que le pipeline complet produit les bons événements WebSocket.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from app.agents.schemas import AgentResponse, GMAction, GMResponse


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_session(ws_client, name: str = "Integration Session") -> str:
    resp = ws_client.post("/api/sessions/", json={"name": name})
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _mock_gm_response(narration: str = "Le MJ narre l'action.", actions: list = None) -> AgentResponse:
    return AgentResponse(content=narration, actions=actions or [])


def _collect_all(ws, count: int) -> list:
    """Reçoit *count* messages JSON depuis le WebSocket."""
    return [ws.receive_json() for _ in range(count)]


def _without_ai_thinking(events: list[dict]) -> list[dict]:
    """Filtre les événements de progression LLM, publics mais non métier."""
    return [e for e in events if e["event_type"] != "ai_thinking"]


def _event(events: list[dict], event_type: str) -> dict:
    return next(e for e in events if e["event_type"] == event_type)


def _event_types(events: list[dict]) -> list[str]:
    return [e["event_type"] for e in events]


def _assert_gm_thinking_pair(events: list[dict]) -> None:
    thinking = [
        e["payload"]["thinking"]
        for e in events
        if e["event_type"] == "ai_thinking" and e["payload"].get("agent_kind") == "gm"
    ]
    assert thinking == [True, False]


# ---------------------------------------------------------------------------
# Tests free_text : narration simple sans résolution mécanique
# ---------------------------------------------------------------------------


class TestFreeTextAction:
    def test_free_text_produces_narration_and_turn_end(self, ws_client) -> None:
        """Action free_text → narration, pas de turn_end hors combat ni roll_result."""
        session_id = _create_session(ws_client)

        mock_response = _mock_gm_response("Vous scrutez les ombres avec attention.")

        with patch(
            "app.api.ws_game.action_resolver._gm",
            new_callable=lambda: type(
                "MockGM", (), {"think": AsyncMock(return_value=mock_response)}
            ),
        ):
            # Re-instancier le resolver avec le GM mocké pour ce test
            with patch(
                "app.game.action_resolver.GMAgent",
            ) as MockGMAgent:
                mock_instance = MagicMock()
                mock_instance.think = AsyncMock(return_value=mock_response)
                MockGMAgent.return_value = mock_instance

                from app.game.action_resolver import ActionResolver
                from app.api import ws_game
                ws_game.action_resolver = ActionResolver(gm_agent=mock_instance)

                with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
                    ws.receive_json()  # session_state

                    ws.send_json({
                        "type": "action",
                        "action_type": "free_text",
                        "content": "Je cherche des pièges dans la salle",
                    })

                    raw_events = _collect_all(ws, 3)
                    events = _without_ai_thinking(raw_events)

                _assert_gm_thinking_pair(raw_events)
                narration = _event(events, "narration")
                assert narration["payload"]["speaker"] == "Maître du Jeu"
                assert "scrutez" in narration["payload"]["text"]

                assert not any(e["event_type"] == "turn_end" for e in events)

    def test_free_text_no_roll_result_event(self, ws_client) -> None:
        """Un free_text ne doit pas produire d'événement roll_result."""
        session_id = _create_session(ws_client)
        mock_response = _mock_gm_response("Rien de suspect.")

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            ws.send_json({
                "type": "action",
                "action_type": "free_text",
                "content": "Je regarde autour de moi",
            })

            raw_events = _collect_all(ws, 3)
            events = _without_ai_thinking(raw_events)

        _assert_gm_thinking_pair(raw_events)
        event_types = set(_event_types(events))
        assert "roll_result" not in event_types
        assert "narration" in event_types
        assert "turn_end" not in event_types


# ---------------------------------------------------------------------------
# Tests attack : résolution mécanique + narration
# ---------------------------------------------------------------------------


class TestAttackAction:
    def test_attack_produces_roll_result_narration(self, ws_client) -> None:
        """Action attack → roll_result + narration, pas turn_end hors combat."""
        session_id = _create_session(ws_client)
        mock_response = _mock_gm_response("Votre épée tranche l'air !")

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            ws.send_json({
                "type": "action",
                "action_type": "attack",
                "content": "J'attaque le gobelin",
                "character_id": "hero-1",
                "target_id": "goblin-1",
            })

            raw_events = _collect_all(ws, 4)
            msgs = _without_ai_thinking(raw_events)

        _assert_gm_thinking_pair(raw_events)
        event_types = _event_types(msgs)
        assert "roll_result" in event_types
        assert "narration" in event_types
        assert "turn_end" not in event_types

    def test_attack_roll_result_has_expected_fields(self, ws_client) -> None:
        """Le roll_result d'une attaque contient les champs mécaniques nécessaires."""
        session_id = _create_session(ws_client)
        mock_response = _mock_gm_response("Un coup puissant !")

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            ws.send_json({
                "type": "action",
                "action_type": "attack",
                "content": "Attaque à la hache",
            })

            raw_events = _collect_all(ws, 4)
            msgs = _without_ai_thinking(raw_events)

        roll_event = next(m for m in msgs if m["event_type"] == "roll_result")
        p = roll_event["payload"]

        assert p["dice_notation"] == "1d20"
        assert isinstance(p["rolls"], list)
        assert len(p["rolls"]) == 1
        assert 1 <= p["rolls"][0] <= 20
        assert isinstance(p["total"], int)
        assert isinstance(p["modifier"], int)
        assert isinstance(p["success"], bool)
        assert "label" in p

    def test_attack_roll_result_is_normalized_for_frontend(self, ws_client) -> None:
        """Le roll_result exposé au frontend reste dans son contrat normalisé."""
        session_id = _create_session(ws_client)
        mock_response = _mock_gm_response("L'ennemi est blessé !")

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            ws.send_json({
                "type": "action",
                "action_type": "attack",
                "content": "Frappe fatale",
            })

            raw_events = _collect_all(ws, 4)
            msgs = _without_ai_thinking(raw_events)

        roll_event = next(m for m in msgs if m["event_type"] == "roll_result")
        p = roll_event["payload"]
        assert set(p) >= {"dice_notation", "rolls", "total", "modifier", "label"}
        assert p["dice_notation"] == "1d20"


# ---------------------------------------------------------------------------
# Tests cast_spell : roll générique + narration
# ---------------------------------------------------------------------------


class TestCastSpellAction:
    def test_cast_spell_produces_roll_result(self, ws_client) -> None:
        """cast_spell → roll_result (d20 générique) + narration, pas turn_end hors combat."""
        session_id = _create_session(ws_client)
        mock_response = _mock_gm_response("Le sort fuse de vos doigts !")

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            ws.send_json({
                "type": "action",
                "action_type": "cast_spell",
                "content": "Projectile magique",
            })

            raw_events = _collect_all(ws, 3)
            msgs = _without_ai_thinking(raw_events)

        _assert_gm_thinking_pair(raw_events)
        event_types = _event_types(msgs)
        assert "roll_result" in event_types

        roll_event = next(m for m in msgs if m["event_type"] == "roll_result")
        assert roll_event["payload"]["dice_notation"] == "d20"
        assert isinstance(roll_event["payload"]["rolls"], list)


# ---------------------------------------------------------------------------
# Tests GM actions : damage_apply → hp_changed
# ---------------------------------------------------------------------------


class TestGMActions:
    def test_damage_apply_publishes_hp_changed(self, ws_client) -> None:
        """Quand le GM demande damage_apply sur un combattant connu, hp_changed est émis."""
        session_id = _create_session(ws_client)

        # GM response avec une action damage_apply
        gm_action = GMAction(type="damage_apply", target="goblin-1", params={"amount": 5})
        mock_response = AgentResponse(
            content="Le gobelin encaisse le coup !",
            actions=[gm_action],
        )

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            # Injecter un combattant dans state_data via le session_manager du module ws_game
            active = ws_game.session_manager.get_session(session_id)
            if active is not None:
                active.state_data["combatants"] = {"goblin-1": {"hp": 10, "ac": 12}}

            ws.send_json({
                "type": "action",
                "action_type": "free_text",
                "content": "Le gobelin encaisse le coup",
            })

            raw_events = _collect_all(ws, 4)
            msgs = _without_ai_thinking(raw_events)

        _assert_gm_thinking_pair(raw_events)
        event_types = _event_types(msgs)
        assert "hp_changed" in event_types

        hp_event = next(m for m in msgs if m["event_type"] == "hp_changed")
        assert hp_event["payload"]["combatant_id"] == "goblin-1"
        assert hp_event["payload"]["delta"] == -5


# ---------------------------------------------------------------------------
# Tests multi-actions : turn_number incrémenté correctement
# ---------------------------------------------------------------------------


class TestTurnProgression:
    def test_multiple_actions_increment_turn_number(self, ws_client) -> None:
        """Chaque action incrémente le turn_number de 1."""
        session_id = _create_session(ws_client)
        mock_response = _mock_gm_response("Le tour avance.")

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            for i in range(1, 4):
                ws.send_json({
                    "type": "action",
                    "action_type": "free_text",
                    "content": f"Action {i}",
                })
                events = _without_ai_thinking(_collect_all(ws, 3))
                active = ws_game.session_manager.get_session(session_id)
                assert active is not None
                assert active.turn_number == i

    def test_gm_called_once_per_action(self, ws_client) -> None:
        """Le GMAgent est appelé exactement une fois par action joueur."""
        session_id = _create_session(ws_client)
        mock_response = _mock_gm_response("Réponse du MJ.")

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            for _ in range(3):
                ws.send_json({"type": "action", "action_type": "free_text", "content": "Agir"})
                _collect_all(ws, 3)

        assert mock_gm.think.call_count == 3


# ---------------------------------------------------------------------------
# Tests robustesse : LLM indisponible → narration de fallback
# ---------------------------------------------------------------------------


class TestResilienceGMFailure:
    def test_gm_failure_still_sends_narration(self, ws_client) -> None:
        """Si le GMAgent lève une exception, une narration de fallback est envoyée."""
        session_id = _create_session(ws_client)

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(side_effect=RuntimeError("Ollama indisponible"))
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            ws.send_json({"type": "action", "action_type": "free_text", "content": "Agir"})

            raw_events = _collect_all(ws, 3)
            events = _without_ai_thinking(raw_events)

        _assert_gm_thinking_pair(raw_events)
        narration = _event(events, "narration")
        assert narration["event_type"] == "narration"
        # Le fallback ne doit pas être vide
        assert len(narration["payload"]["text"]) > 0
        assert not any(e["event_type"] == "turn_end" for e in events)


# ---------------------------------------------------------------------------
# Tests auto-combat : GM narre une rencontre → combat démarre sans clic
# ---------------------------------------------------------------------------


class TestAutoCombatTrigger:
    def test_hostile_narration_without_actions_triggers_combat_automatically(
        self, ws_client
    ) -> None:
        """Même sans actions JSON, une embuscade hostile narrée démarre le combat."""
        session_id = _create_session(ws_client)

        mock_response = AgentResponse(
            content="Deux bandits surgissent des fourrés, lames au clair !",
            actions=[],
        )

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game
        from app.models.session import SessionStatus

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        mock_gm.run_combat_turn = AsyncMock(return_value=GMResponse(narration="Le bandit frappe."))
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state initial

            active = ws_game.session_manager.get_session(session_id)
            assert active is not None
            active.state_data["characters"] = {
                "hero-1": {
                    "name": "Thorvald",
                    "level": 1,
                    "hp": 10,
                    "hp_max": 10,
                    "dex": 100,
                    "is_ai": False,
                    "equipment": [],
                }
            }

            ws.send_json({
                "type": "action",
                "action_type": "free_text",
                "content": "Nous avançons prudemment.",
            })

            raw_events = _collect_all(ws, 8)
            events = _without_ai_thinking(raw_events)

        _assert_gm_thinking_pair(raw_events)
        event_types = _event_types(events)
        assert "phase_change" in event_types
        assert "combat_start" in event_types

        combat_start = next(e for e in events if e["event_type"] == "combat_start")
        monsters = [
            c for c in combat_start["payload"]["combatants"] if c["kind"] == "monster"
        ]
        assert len(monsters) == 2
        assert all(m["name"].startswith("Bandit") for m in monsters)

        active = ws_game.session_manager.get_session(session_id)
        assert active is not None
        assert active.phase == SessionStatus.COMBAT

    def test_explicit_attack_text_in_exploration_starts_combat(
        self, ws_client
    ) -> None:
        """Si le joueur écrit « j'attaque le bandit », on entre en combat."""
        session_id = _create_session(ws_client)

        from app.api import ws_game
        from app.agents.schemas import GMResponse as _GMResponse
        from app.models.session import SessionStatus

        from app.game.action_resolver import ActionResolver

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=_mock_gm_response("Le combat commence."))
        mock_gm.run_combat_turn = AsyncMock(
            return_value=_GMResponse(narration="Le bandit riposte.")
        )
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state initial

            active = ws_game.session_manager.get_session(session_id)
            assert active is not None
            active.phase = SessionStatus.EXPLORATION
            active.state_data["characters"] = {
                "hero-1": {
                    "name": "Thorvald",
                    "level": 1,
                    "hp": 10,
                    "hp_max": 10,
                    "dex": 100,
                    "is_ai": False,
                    "equipment": [],
                }
            }

            ws.send_json({
                "type": "action",
                "action_type": "free_text",
                "content": "J'attaque le bandit le plus proche.",
                "character_id": "hero-1",
            })

            events = _collect_all(ws, 5)

        event_types = [e["event_type"] for e in events]
        assert "phase_change" in event_types
        assert "combat_start" in event_types

        active = ws_game.session_manager.get_session(session_id)
        assert active is not None
        assert active.phase == SessionStatus.COMBAT

    def test_hostile_narration_triggers_combat_automatically(self, ws_client) -> None:
        """GM émet encounter_setup + state_transition COMBAT → phase devient COMBAT
        et combat_start est diffusé, sans action manuelle 'start_combat'.

        Séquence d'événements attendue après l'envoi du free_text :
          1. narration        (GM : « Trois gobelins surgissent... »)
          2. phase_change     (EXPLORATION → COMBAT)
          3. combat_start     (liste des combattants + grille)
          4. session_state    (snapshot post-init)
          5. narration        (intro d'encounter)
          6. turn_start       (premier combattant selon l'initiative)
        """
        session_id = _create_session(ws_client)

        mock_response = AgentResponse(
            content="Trois gobelins embusqués surgissent des fourrés !",
            actions=[
                GMAction(type="encounter_setup", params={"monster_ids": ["goblin"]}),
                GMAction(type="state_transition", params={"to": "COMBAT"}),
            ],
        )

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game
        from app.models.session import SessionStatus

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state initial

            # Injecter un héros pour que _handle_start_combat ait au moins
            # un combattant joueur — sinon l'initiative ne contient que le
            # goblin (IA), et `_handle_ai_turns` boucle indéfiniment puisque
            # next_turn() wrappe sur le seul combattant restant (qui reste IA).
            active = ws_game.session_manager.get_session(session_id)
            assert active is not None
            active.state_data["characters"] = {
                "hero-1": {
                    "name": "Thorvald",
                    "level": 1,
                    "hp": 10,
                    "hp_max": 10,
                    "dex": 100,
                    "is_ai": False,
                    "equipment": [],
                }
            }

            ws.send_json({
                "type": "action",
                "action_type": "free_text",
                "content": "J'avance prudemment.",
            })

            # Starlette's WebSocketTestSession.receive_json n'accepte PAS `timeout`.
            # On reçoit un nombre connu d'événements. Si le flag d'auto-combat
            # n'avait pas été posé, on recevrait uniquement narration + turn_end
            # (2 events) et le test expirerait — c'est justement ce qu'on veut
            # détecter en cas de régression.
            # NB : l'ordre exact des 5e/6e événements (intro narration vs
            # turn_start) dépend de qui a la meilleure initiative (joueur ou
            # goblin). On collecte simplement les 6 events puis on vérifie la
            # présence des types attendus — sans contraindre l'ordre après
            # session_state.
            raw_events = _collect_all(ws, 8)
            events = _without_ai_thinking(raw_events)

        _assert_gm_thinking_pair(raw_events)
        event_types = _event_types(events)
        assert event_types[0] == "narration", event_types
        assert "combat_start" in event_types, (
            f"combat_start attendu, reçu : {event_types}"
        )
        assert "phase_change" in event_types
        # turn_start est émis soit directement (joueur first), soit par
        # _handle_ai_turns (monstre first) — dans les deux cas il doit apparaître.
        assert "turn_start" in event_types

        # La phase de la session doit être COMBAT après traitement.
        active = ws_game.session_manager.get_session(session_id)
        assert active is not None
        assert active.phase == SessionStatus.COMBAT
        # Le flag a bien été consommé (pas de résidu).
        assert "pending_phase_transition" not in active.state_data
        # Le pending_encounter a aussi été consommé par _handle_start_combat.
        assert "pending_encounter" not in active.state_data

    def test_state_transition_without_encounter_does_not_start_combat(
        self, ws_client
    ) -> None:
        """Sans encounter_setup, state_transition COMBAT est ignoré : phase inchangée."""
        session_id = _create_session(ws_client)

        mock_response = AgentResponse(
            content="Une ombre passe au loin.",
            actions=[GMAction(type="state_transition", params={"to": "COMBAT"})],
        )

        from app.game.action_resolver import ActionResolver
        from app.api import ws_game
        from app.models.session import SessionStatus

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=mock_response)
        ws_game.action_resolver = ActionResolver(gm_agent=mock_gm)

        with ws_client.websocket_connect(f"/ws/game/{session_id}") as ws:
            ws.receive_json()  # session_state

            ws.send_json({
                "type": "action",
                "action_type": "free_text",
                "content": "Je scrute.",
            })

            raw_events = _collect_all(ws, 3)
            events = _without_ai_thinking(raw_events)

        _assert_gm_thinking_pair(raw_events)
        event_types = _event_types(events)
        assert "combat_start" not in event_types
        assert "narration" in event_types
        assert "turn_end" not in event_types

        active = ws_game.session_manager.get_session(session_id)
        assert active is not None
        assert active.phase != SessionStatus.COMBAT
