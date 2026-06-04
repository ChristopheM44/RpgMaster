"""Régression : persistance des résultats de jets (ROLL_RESULT).

Avant le correctif, les jets étaient publiés sur l'event bus (affichage live)
mais jamais persistés → ils disparaissaient au rechargement de session. Ces
tests verrouillent les deux moitiés du contrat :
- un jet persisté est relisible avec sa metadata complète (round-trip), c'est
  elle qui permet au frontend de reconstruire la carte de jet ;
- les jets restent exclus de la fenêtre de contexte LLM (load_recent_messages),
  pour ne pas changer le budget de contexte du MJ.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.message import Message, MessageType
from app.services.message_service import (
    load_recent_messages,
    persist_narration,
    persist_roll_result,
)

SESSION_ID = "sess-roll-persist"

ROLL_PAYLOAD = {
    "dice_notation": "1d20",
    "rolls": [12],
    "d20": 12,
    "modifier": 3,
    "total": 15,
    "dc": 14,
    "success": True,
    "label": "Jet de Médecine",
    "breakdown": "1d20 (12) + 3 = 15",
    "character_id": "thorvald",
    "character_name": "Thorvald",
}


@pytest.mark.asyncio
async def test_persist_roll_result_round_trips_with_metadata(db_session) -> None:
    await persist_roll_result(SESSION_ID, ROLL_PAYLOAD, db_session)

    rows = (
        (await db_session.execute(select(Message).where(Message.session_id == SESSION_ID)))
        .scalars()
        .all()
    )

    assert len(rows) == 1
    msg = rows[0]
    assert msg.message_type == MessageType.ROLL_RESULT
    assert msg.content == "Jet de Médecine"
    assert msg.speaker == "Thorvald"
    # La metadata complète round-trip : DD, succès et détail doivent survivre.
    assert msg.metadata_["dice_notation"] == "1d20"
    assert msg.metadata_["dc"] == 14
    assert msg.metadata_["success"] is True
    assert msg.metadata_["breakdown"] == "1d20 (12) + 3 = 15"
    assert msg.metadata_["total"] == 15


@pytest.mark.asyncio
async def test_persist_roll_result_noops_without_db() -> None:
    # Fire-and-forget : ne doit jamais lever si db est None ou payload vide.
    await persist_roll_result(SESSION_ID, ROLL_PAYLOAD, None)
    await persist_roll_result(SESSION_ID, {}, None)


@pytest.mark.asyncio
async def test_roll_results_excluded_from_llm_context(db_session) -> None:
    await persist_narration(
        SESSION_ID, "Le sable crisse sous vos pas.", "Maître du Jeu", db_session
    )
    await persist_roll_result(SESSION_ID, ROLL_PAYLOAD, db_session)

    context = await load_recent_messages(SESSION_ID, db_session)

    # La narration alimente le contexte du MJ ; le jet en est exclu.
    assert len(context) == 1
    assert "sable crisse" in context[0].content
    assert all(m.content != "Jet de Médecine" for m in context)
