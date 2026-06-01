"""A3 — guard-list reconcile at session open prevents stale-mirror re-grants.

`record_granted_unique_items` writes the DB dossier immediately, but `save_state`
(which persists the in-blob mirror `campaign_context.played_canon`) can lag that
commit across a crash. On reload, `open_session` would otherwise restore a stale
blob whose mirror lacks the item — and the loot guard (`_granted_unique_items`,
which reads the mirror) would re-grant a unique item.

`SessionManager._reconcile_guard_lists_from_dossier` union-merges the append-only
guard lists DB→mirror at open, closing that window.
"""
from __future__ import annotations

import pytest

from app.game.gm_response_executor import GMResponseExecutor
from app.game.session_manager import SessionManager
from app.models.campaign import Campaign
from app.models.campaign_dossier import CampaignDossier
from app.models.character import Character
from app.models.game_state import GameState
from app.models.session import Session, SessionStatus


async def _seed_stale_session(db_session, *, db_granted: list[str], mirror_granted: list[str]):
    """Seed a DB session whose blob mirror lags the DB dossier."""
    campaign = Campaign(
        id="camp-a3",
        name="Reliques",
        description="",
        session_ids=["sess-a3"],
    )
    dossier = CampaignDossier(
        id="dossier-a3",
        campaign_id=campaign.id,
        player_contract={},
        gm_dossier={
            "items": [
                {
                    "id": "amulette_unique",
                    "template_id": "amulette_unique",
                    "name": "Amulet of the Vow",
                    "name_fr": "Amulette du Serment",
                    "category": "wondrous",
                    "item_type": "wondrous",
                    "unique": True,
                }
            ],
        },
        # Authoritative DB dossier already records the grant.
        played_canon={"granted_unique_items": db_granted},
        import_sources=[],
        forge_job={},
        active_chapter_id="chapter_1",
        generation_status="validated",
    )
    session = Session(id="sess-a3", name="A3", status=SessionStatus.EXPLORATION)
    game_state = GameState(
        session_id="sess-a3",
        # The persisted blob mirror is STALE (predates the DB commit).
        state_data={
            "campaign_context": {
                "campaign_id": campaign.id,
                "items": dossier.gm_dossier["items"],
                "played_canon": {"granted_unique_items": mirror_granted},
            },
            "characters": {},
        },
        turn_number=0,
        round_number=0,
    )
    db_session.add_all([campaign, dossier, session, game_state])
    await db_session.commit()


@pytest.mark.asyncio
async def test_open_session_reconciles_stale_granted_items(db_session):
    """The stale mirror is healed from the DB dossier at open."""
    await _seed_stale_session(db_session, db_granted=["amulette_unique"], mirror_granted=[])

    manager = SessionManager()
    try:
        active = await manager.open_session("sess-a3", db_session)
    finally:
        manager._sessions.pop("sess-a3", None)

    mirror = active.state_data["campaign_context"]["played_canon"]["granted_unique_items"]
    assert "amulette_unique" in mirror


@pytest.mark.asyncio
async def test_reconcile_blocks_double_grant_after_reload(db_session):
    """End-to-end proof: after a stale reload, a second loot_grant of the same
    unique item must NOT add it twice (guard reads the now-reconciled mirror)."""
    await _seed_stale_session(db_session, db_granted=["amulette_unique"], mirror_granted=[])

    char = Character(
        name="Pax",
        species="human",
        char_class="fighter",
        level=1,
        ability_scores={"str": 15, "dex": 10, "con": 12, "int": 10, "wis": 10, "cha": 10},
        hp_current=11,
        hp_max=11,
        session_id="sess-a3",
    )
    db_session.add(char)
    await db_session.commit()
    await db_session.refresh(char)

    manager = SessionManager()
    try:
        active = await manager.open_session("sess-a3", db_session)
    finally:
        manager._sessions.pop("sess-a3", None)
    active.state_data["characters"][char.id] = {"name": char.name, "level": 1, "hp": 11}

    executor = GMResponseExecutor(source="test")
    params = {
        "target": char.id,
        "items": [{"template_id": "amulette_unique", "quantity": 1}],
    }
    await executor.execute_action("sess-a3", "loot_grant", params, active, db=db_session)

    await db_session.refresh(char)
    # Already granted (per reconciled mirror) → the guard suppresses the re-grant.
    unique_items = [i for i in (char.equipment or []) if i.get("template_id") == "amulette_unique"]
    assert len(unique_items) == 0


@pytest.mark.asyncio
async def test_reconcile_is_union_only_never_empties(db_session):
    """A mirror entry absent from the DB dossier is preserved (union, not replace)."""
    await _seed_stale_session(
        db_session, db_granted=["amulette_unique"], mirror_granted=["relique_locale"]
    )

    manager = SessionManager()
    try:
        active = await manager.open_session("sess-a3", db_session)
    finally:
        manager._sessions.pop("sess-a3", None)

    merged = active.state_data["campaign_context"]["played_canon"]["granted_unique_items"]
    assert set(merged) == {"amulette_unique", "relique_locale"}


@pytest.mark.asyncio
async def test_reconcile_noop_without_campaign_context(db_session):
    """No campaign_context → reconcile is a silent no-op (safe on free sessions)."""
    session = Session(id="sess-free", name="Free", status=SessionStatus.EXPLORATION)
    game_state = GameState(
        session_id="sess-free",
        state_data={"characters": {}},
        turn_number=0,
        round_number=0,
    )
    db_session.add_all([session, game_state])
    await db_session.commit()

    manager = SessionManager()
    try:
        active = await manager.open_session("sess-free", db_session)
    finally:
        manager._sessions.pop("sess-free", None)

    assert "campaign_context" not in active.state_data
