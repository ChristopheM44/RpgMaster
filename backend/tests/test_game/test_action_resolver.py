"""Tests unitaires pour ActionResolver.

Couvre les deux corrections :
1. Persistance de l'action joueur + peuplement de AgentContext.messages depuis la DB.
2. Handler ``state_transition`` qui pose le drapeau ``pending_phase_transition``
   uniquement si un ``pending_encounter`` est défini.

Le GMAgent est mocké (on n'appelle jamais le vrai LLM).
"""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

import app.models  # noqa: F401 — enregistre les tables
from app.agents.schemas import AgentContext, AgentResponse, GMAction, GMResponse
from app.db.database import Base
from app.game.action_resolver import ActionResolver
from app.game.session_manager import ActiveSession
from app.models.session import SessionStatus


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def db_session():
    """Session SQLite in-memory avec tables créées."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def session_row(db_session):
    """Crée une ligne Session en DB pour satisfaire la FK de Message.session_id."""
    from app.models.session import Session

    row = Session(id="sess-test-1", name="Test", status=SessionStatus.EXPLORATION)
    db_session.add(row)
    await db_session.commit()
    return row.id


@pytest.fixture
def active_session(session_row):
    """ActiveSession en mémoire, phase EXPLORATION, un héros nommé 'Thorvald'."""
    return ActiveSession(
        session_id=session_row,
        phase=SessionStatus.EXPLORATION,
        state_data={
            "characters": {
                "hero-1": {"name": "Thorvald", "level": 1, "hp": 10, "hp_max": 10},
            },
        },
    )


def _mock_resolver(narration: str, actions: list = None) -> ActionResolver:
    """Crée un ActionResolver avec un GMAgent mocké retournant une réponse fixe."""
    mock_gm = MagicMock()
    mock_gm.think = AsyncMock(return_value=AgentResponse(content=narration, actions=actions or []))
    return ActionResolver(gm_agent=mock_gm)


def _capturing_resolver() -> tuple[ActionResolver, list[AgentContext]]:
    """Crée un ActionResolver qui capture chaque AgentContext reçu par think()."""
    captured: list[AgentContext] = []

    async def capture(ctx: AgentContext) -> AgentResponse:
        captured.append(ctx)
        return AgentResponse(content="Narration du MJ.", actions=[])

    mock_gm = MagicMock()
    mock_gm.think = AsyncMock(side_effect=capture)
    return ActionResolver(gm_agent=mock_gm), captured


# ---------------------------------------------------------------------------
# Fix 1 — Historique conversationnel
# ---------------------------------------------------------------------------


class TestConversationHistory:
    async def test_player_action_is_persisted_before_gm_call(
        self, db_session, active_session
    ) -> None:
        """L'action joueur doit être en DB avec role=player/type=action avant l'appel LLM."""
        resolver = _mock_resolver("OK")

        await resolver.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Je cherche des traces.",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        from sqlalchemy import select
        from app.models.message import Message, MessageRole, MessageType

        rows = (
            await db_session.execute(
                select(Message)
                .where(Message.session_id == active_session.session_id)
                .order_by(Message.created_at.asc())
            )
        ).scalars().all()

        player_msgs = [m for m in rows if m.role == MessageRole.PLAYER]
        assert len(player_msgs) == 1
        pm = player_msgs[0]
        assert pm.speaker == "Thorvald"
        assert "traces" in pm.content
        assert pm.message_type == MessageType.ACTION
        assert (pm.metadata_ or {}).get("action_type") == "free_text"

    async def test_second_resolve_sees_first_exchange_in_context(
        self, db_session, active_session
    ) -> None:
        """Le deuxième appel à resolve() doit recevoir l'action + narration du premier."""
        # Premier tour : narration "salle circulaire"
        first_resolver = _mock_resolver("Une salle circulaire s'ouvre devant vous.")
        await first_resolver.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="J'écoute ce qui se dit.",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        # Deuxième tour : on capture le AgentContext reçu par le MJ.
        second_resolver, captured = _capturing_resolver()
        await second_resolver.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="J'avance doucement.",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        assert len(captured) == 1
        ctx = captured[0]
        assert len(ctx.messages) >= 3, f"attendu ≥3 messages, reçu {len(ctx.messages)}"

        roles = [m.role for m in ctx.messages]
        speakers = [m.speaker for m in ctx.messages]
        contents = " | ".join(m.content for m in ctx.messages)

        assert "player" in roles, "l'action du joueur précédent doit être présente"
        assert "gm" in roles, "la narration précédente du MJ doit être présente"
        assert "Thorvald" in speakers
        assert "salle circulaire" in contents
        assert "J'écoute" in contents

    async def test_messages_are_in_chronological_order(
        self, db_session, active_session
    ) -> None:
        """L'ordre des messages dans AgentContext doit être chronologique."""
        resolver1 = _mock_resolver("Narration 1.")
        await resolver1.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Action 1",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        resolver2 = _mock_resolver("Narration 2.")
        await resolver2.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Action 2",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        resolver3, captured = _capturing_resolver()
        await resolver3.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Action 3",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        contents = [m.content for m in captured[0].messages]
        # On doit voir Action 1 avant Narration 1, avant Action 2, avant Narration 2,
        # avant Action 3.
        i1a = next(i for i, c in enumerate(contents) if "Action 1" in c)
        i1n = next(i for i, c in enumerate(contents) if "Narration 1" in c)
        i2a = next(i for i, c in enumerate(contents) if "Action 2" in c)
        i2n = next(i for i, c in enumerate(contents) if "Narration 2" in c)
        i3a = next(i for i, c in enumerate(contents) if "Action 3" in c)
        assert i1a < i1n < i2a < i2n < i3a


# ---------------------------------------------------------------------------
# Flux narratif fluide — roll_request interne, narration unique après jet
# ---------------------------------------------------------------------------


class TestFluidNarrativeFlow:
    async def test_roll_request_publishes_only_outcome_narration(
        self, db_session, active_session
    ) -> None:
        """roll_request : le jet est visible, puis une seule narration MJ finale."""
        from sqlalchemy import select

        from app.game.event_bus import EventType
        from app.models.message import Message, MessageRole

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=AgentResponse(
            content="Thorvald se penche sur les traces.",
            actions=[
                GMAction(
                    type="roll_request",
                    target="hero-1",
                    params={"ability": "wis", "type": "check", "dc": 10},
                )
            ],
        ))
        mock_gm.narrate_outcome_response = AsyncMock(return_value=GMResponse(
            narration="La boue révèle seulement des passages confus, impossibles à dater.",
            actions=[],
        ))
        resolver = ActionResolver(gm_agent=mock_gm)
        published: list[tuple[str, dict]] = []

        async def publish(session_id, event_type, payload, source=None):
            published.append((event_type, payload))

        with patch("app.game.action_resolver.event_bus.publish_to_session", new=publish), patch(
            "app.game.action_resolver.tts_router.synthesize_and_broadcast",
            new=AsyncMock(),
        ):
            await resolver.resolve(
                session_id=active_session.session_id,
                action_type="free_text",
                content="J'inspecte les traces.",
                character_id="hero-1",
                target_id=None,
                active=active_session,
                db=db_session,
            )

        visible_events = [
            event_type
            for event_type, _payload in published
            if event_type in {EventType.ROLL_RESULT, EventType.NARRATION}
        ]
        assert visible_events == [EventType.ROLL_RESULT, EventType.NARRATION]

        narrations = [
            payload["text"]
            for event_type, payload in published
            if event_type == EventType.NARRATION
        ]
        assert narrations == [
            "La boue révèle seulement des passages confus, impossibles à dater."
        ]
        assert all("se penche" not in text for text in narrations)

        rows = (
            await db_session.execute(
                select(Message)
                .where(Message.session_id == active_session.session_id)
                .order_by(Message.created_at.asc())
            )
        ).scalars().all()
        gm_messages = [row.content for row in rows if row.role == MessageRole.GM]
        assert gm_messages == [
            "La boue révèle seulement des passages confus, impossibles à dater."
        ]

    async def test_action_without_roll_request_keeps_initial_narration(
        self, db_session, active_session
    ) -> None:
        """Sans roll_request, le comportement existant reste une narration directe."""
        from app.game.event_bus import EventType

        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=AgentResponse(
            content="Le sentier descend vers les ruines.",
            actions=[],
        ))
        mock_gm.narrate_outcome_response = AsyncMock()
        resolver = ActionResolver(gm_agent=mock_gm)
        published: list[tuple[str, dict]] = []

        async def publish(session_id, event_type, payload, source=None):
            published.append((event_type, payload))

        with patch("app.game.action_resolver.event_bus.publish_to_session", new=publish), patch(
            "app.game.action_resolver.tts_router.synthesize_and_broadcast",
            new=AsyncMock(),
        ):
            await resolver.resolve(
                session_id=active_session.session_id,
                action_type="free_text",
                content="J'avance vers les ruines.",
                character_id="hero-1",
                target_id=None,
                active=active_session,
                db=db_session,
            )

        narrations = [
            payload["text"]
            for event_type, payload in published
            if event_type == EventType.NARRATION
        ]
        assert narrations == ["Le sentier descend vers les ruines."]
        mock_gm.narrate_outcome_response.assert_not_called()


# ---------------------------------------------------------------------------
# Fix 2 — state_transition pose le drapeau pour l'auto-combat
# ---------------------------------------------------------------------------


class TestStateTransition:
    async def test_hostile_narration_without_actions_primes_combat(
        self, db_session, active_session
    ) -> None:
        """Une embuscade hostile racontée sans JSON mécanique démarre quand même."""
        resolver = _mock_resolver(
            "Une douzaine de bandits surgissent des buissons, lames au clair."
        )

        await resolver.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Nous avançons vers le camp.",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        assert active_session.state_data.get("pending_phase_transition") == "COMBAT"
        pending = active_session.state_data.get("pending_encounter")
        assert pending is not None
        assert pending["monster_ids"] == ["bandit"] * 12

    async def test_hostile_roll_outcome_without_actions_primes_combat(
        self, db_session, active_session
    ) -> None:
        """Une embuscade révélée par l'issue d'un jet déclenche aussi le combat."""
        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=AgentResponse(
            content="Le passage semble dangereusement silencieux.",
            actions=[
                GMAction(
                    type="roll_request",
                    target="hero-1",
                    params={"ability": "wis", "type": "check", "dc": 13},
                )
            ],
        ))
        mock_gm.narrate_outcome = AsyncMock(return_value=(
            "Des flèches pleuvent depuis les rochers ; trois bandits surgissent, "
            "lames au clair."
        ))
        resolver = ActionResolver(gm_agent=mock_gm)

        await resolver.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Je cherche des signes de danger.",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        assert active_session.state_data.get("pending_phase_transition") == "COMBAT"
        pending = active_session.state_data.get("pending_encounter")
        assert pending is not None
        assert pending["monster_ids"] == ["bandit", "bandit", "bandit"]

    async def test_state_transition_combat_sets_flag_with_encounter_setup(
        self, db_session, active_session
    ) -> None:
        """GM émet encounter_setup + state_transition COMBAT → flag posé."""
        actions = [
            GMAction(type="encounter_setup", params={"monster_ids": ["goblin", "goblin"]}),
            GMAction(type="state_transition", params={"to": "COMBAT"}),
        ]
        resolver = _mock_resolver("Trois gobelins surgissent !", actions=actions)

        await resolver.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Je me prépare.",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        assert active_session.state_data.get("pending_phase_transition") == "COMBAT"
        pending = active_session.state_data.get("pending_encounter")
        assert pending is not None
        assert pending["monster_ids"] == ["goblin", "goblin"]

    async def test_state_transition_combat_without_encounter_is_ignored(
        self, db_session, active_session, caplog
    ) -> None:
        """GM émet state_transition COMBAT sans encounter_setup → flag NON posé."""
        import logging

        actions = [GMAction(type="state_transition", params={"to": "COMBAT"})]
        resolver = _mock_resolver("Des ombres rôdent.", actions=actions)

        with caplog.at_level(logging.WARNING, logger="app.game.action_resolver"):
            await resolver.resolve(
                session_id=active_session.session_id,
                action_type="free_text",
                content="Je regarde.",
                character_id="hero-1",
                target_id=None,
                active=active_session,
                db=db_session,
            )

        assert "pending_phase_transition" not in active_session.state_data
        assert any("pending_encounter" in rec.message for rec in caplog.records)


class TestCombatStateActions:
    async def test_roll_outcome_can_mark_npc_surrendered(
        self, db_session, session_row
    ) -> None:
        """Une issue de jet social peut retirer un PNJ hostile via combatant_status."""
        active = ActiveSession(
            session_id=session_row,
            phase=SessionStatus.COMBAT,
            state_data={
                "characters": {
                    "hero-1": {
                        "name": "Thorvald",
                        "level": 1,
                        "hp": 10,
                        "hp_max": 10,
                        "ability_scores": {"cha": 16},
                    },
                },
                "combatants": {
                    "hero-1": {"name": "Thorvald", "hp": 10, "is_player": True},
                    "bandit_1": {
                        "name": "Bandit 1",
                        "hp": 7,
                        "is_player": False,
                        "status": "active",
                    },
                },
            },
        )
        mock_gm = MagicMock()
        mock_gm.think = AsyncMock(return_value=AgentResponse(
            content="Le bandit hésite.",
            actions=[
                GMAction(
                    type="roll_request",
                    target="hero-1",
                    params={"ability": "cha", "type": "check", "dc": 1},
                )
            ],
        ))
        mock_gm.narrate_outcome_response = AsyncMock(return_value=GMResponse(
            narration="Le bandit laisse tomber son arme et se rend.",
            actions=[
                GMAction(
                    type="combatant_status",
                    target="bandit_1",
                    params={"status": "surrendered", "reason": "reddition"},
                )
            ],
        ))

        resolver = ActionResolver(gm_agent=mock_gm)
        await resolver.resolve(
            session_id=session_row,
            action_type="free_text",
            content="Rends-toi ou meurs.",
            character_id="hero-1",
            target_id=None,
            active=active,
            db=db_session,
        )

        assert active.state_data["combatants"]["bandit_1"]["status"] == "surrendered"

    async def test_condition_actions_mutate_state_data(
        self, db_session, active_session
    ) -> None:
        """condition_add/remove doit modifier state_data, pas seulement publier un event."""
        active_session.phase = SessionStatus.COMBAT
        active_session.state_data["combatants"] = {
            "hero-1": {
                "name": "Thorvald",
                "hp": 10,
                "is_player": True,
                "conditions": [],
            },
        }
        actions = [
            GMAction(type="condition_add", target="hero-1", params={"condition": "prone"}),
        ]
        resolver = _mock_resolver("Thorvald tombe au sol.", actions=actions)

        await resolver.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Je glisse.",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        assert active_session.state_data["combatants"]["hero-1"]["conditions"] == ["prone"]

        remove_resolver = _mock_resolver(
            "Thorvald se relève.",
            actions=[
                GMAction(
                    type="condition_remove",
                    target="hero-1",
                    params={"condition": "prone"},
                )
            ],
        )
        await remove_resolver.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Je me relève.",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        assert active_session.state_data["combatants"]["hero-1"]["conditions"] == []

    async def test_state_transition_accepts_phase_and_target_keys(
        self, db_session, active_session
    ) -> None:
        """Le handler doit tolérer les variantes ``params.phase`` et ``params.target``."""
        actions = [
            GMAction(type="encounter_setup", params={"monster_ids": ["kobold"]}),
            GMAction(type="state_transition", params={"phase": "combat"}),  # minuscules + clé alt
        ]
        resolver = _mock_resolver("Un kobold apparaît !", actions=actions)

        await resolver.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Attention !",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        assert active_session.state_data.get("pending_phase_transition") == "COMBAT"

    async def test_non_combat_state_transition_is_logged_only(
        self, db_session, active_session
    ) -> None:
        """state_transition vers une autre phase ne pose aucun drapeau."""
        actions = [GMAction(type="state_transition", params={"to": "REST"})]
        resolver = _mock_resolver("Vous vous reposez.", actions=actions)

        await resolver.resolve(
            session_id=active_session.session_id,
            action_type="free_text",
            content="Je dors.",
            character_id="hero-1",
            target_id=None,
            active=active_session,
            db=db_session,
        )

        assert "pending_phase_transition" not in active_session.state_data


class TestNpcDialogueRouting:
    async def test_resolve_npc_dialogue_ignores_non_npc_poi(self, session_row) -> None:
        active = ActiveSession(
            session_id=session_row,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {"hero-1": {"name": "Thorvald"}},
                "npc_states": {},
                "current_scene": {
                    "pois": [
                        {
                            "id": "locked_door",
                            "name": "Porte verrouillée",
                            "kind": "clue",
                            "icon": "door",
                        }
                    ]
                },
            },
        )
        mock_gm = MagicMock()
        mock_gm.run_npc_dialogue = AsyncMock()
        resolver = ActionResolver(gm_agent=mock_gm)

        await resolver.resolve_npc_dialogue(
            session_id=session_row,
            content="J'examine la porte verrouillée.",
            character_id="hero-1",
            target_id="locked_door",
            active=active,
            db=None,
        )

        mock_gm.run_npc_dialogue.assert_not_called()

    async def test_npc_dialogue_social_outcome_updates_state_and_canon(
        self,
        db_session,
        session_row,
    ) -> None:
        from app.game.event_bus import event_bus

        active = ActiveSession(
            session_id=session_row,
            phase=SessionStatus.EXPLORATION,
            state_data={
                "characters": {"hero-1": {"name": "Thorvald"}},
                "npc_states": {
                    "azaka": {
                        "name": "Azaka",
                        "attitude": "indifferent",
                    }
                },
            },
        )
        mock_gm = MagicMock()
        mock_gm.run_npc_dialogue = AsyncMock(return_value=GMResponse(
            narration="Azaka hoche la tête. « D'accord, je vous guiderai. »",
            actions=[
                GMAction(
                    type="social_outcome",
                    params={
                        "npc_id": "azaka",
                        "attitude_shift": "friendly",
                        "note": "Azaka accepte de guider le groupe.",
                        "new_quest": {
                            "id": "guide_azaka",
                            "category": "secondaire",
                            "title": "Engager Azaka",
                            "summary": "Azaka accepte de servir de guide.",
                            "status": "active",
                        },
                    },
                )
            ],
        ))
        resolver = ActionResolver(gm_agent=mock_gm)

        with patch.object(event_bus, "publish_to_session", new=AsyncMock()), patch(
            "app.services.campaign_dossier_service.synthesize_canon_for_session",
            new=AsyncMock(),
        ) as synth:
            await resolver.resolve_npc_dialogue(
                session_id=session_row,
                content="Je demande à Azaka d'être notre guide.",
                character_id="hero-1",
                target_id="azaka",
                active=active,
                db=db_session,
                roll_results={"type": "skill_check", "success": True},
            )

        mock_gm.run_npc_dialogue.assert_awaited_once()
        assert mock_gm.run_npc_dialogue.await_args.kwargs["roll_results"] == {
            "type": "skill_check",
            "success": True,
        }
        assert active.state_data["npc_states"]["azaka"]["attitude"] == "friendly"
        assert active.state_data["npc_states"]["azaka"]["notes"] == [
            "Azaka accepte de guider le groupe."
        ]
        assert active.state_data["quests"][0]["id"] == "guide_azaka"
        synth.assert_awaited_once()
