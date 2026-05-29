"""remove orphan sessions

Revision ID: h8i9j0k1l2m3
Revises: g7h8i9j0k1l2
Create Date: 2026-05-29 00:00:00.000000

"""
from __future__ import annotations

import json
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "h8i9j0k1l2m3"
down_revision: Union[str, Sequence[str], None] = "g7h8i9j0k1l2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    campaigns = bind.execute(sa.text("SELECT session_ids FROM campaigns")).fetchall()

    referenced_session_ids: set[str] = set()
    for row in campaigns:
        raw = row[0]
        try:
            ids = json.loads(raw) if isinstance(raw, str) else raw
        except (TypeError, json.JSONDecodeError):
            ids = []
        if isinstance(ids, list):
            referenced_session_ids.update(str(session_id) for session_id in ids if session_id)

    all_sessions = bind.execute(sa.text("SELECT id FROM sessions")).fetchall()
    orphan_ids = [row[0] for row in all_sessions if row[0] not in referenced_session_ids]
    if not orphan_ids:
        return

    delete_ids = [{"session_id": session_id} for session_id in orphan_ids]
    for table in ("messages", "save_slots", "game_states", "characters"):
        bind.execute(sa.text(f"DELETE FROM {table} WHERE session_id = :session_id"), delete_ids)
    bind.execute(sa.text("DELETE FROM sessions WHERE id = :session_id"), delete_ids)


def downgrade() -> None:
    # Deleted standalone sessions cannot be reconstructed.
    pass
