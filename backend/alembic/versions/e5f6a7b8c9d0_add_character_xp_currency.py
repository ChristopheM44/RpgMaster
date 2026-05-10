"""add character xp currency

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-10 00:00:00.000000
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "e5f6a7b8c9d0"
down_revision = "d4e5f6a7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("characters") as batch_op:
        batch_op.add_column(sa.Column("xp", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("gp", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("sp", sa.Integer(), nullable=False, server_default="0"))
        batch_op.add_column(sa.Column("cp", sa.Integer(), nullable=False, server_default="0"))


def downgrade() -> None:
    with op.batch_alter_table("characters") as batch_op:
        batch_op.drop_column("cp")
        batch_op.drop_column("sp")
        batch_op.drop_column("gp")
        batch_op.drop_column("xp")
