"""add_campaign_dossiers

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-04-26 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "b2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "campaign_dossiers",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("campaign_id", sa.String(length=36), nullable=False),
        sa.Column("player_contract", sa.JSON(), nullable=False),
        sa.Column("gm_dossier", sa.JSON(), nullable=False),
        sa.Column("played_canon", sa.JSON(), nullable=False),
        sa.Column("import_sources", sa.JSON(), nullable=False),
        sa.Column("active_chapter_id", sa.String(length=80), nullable=False, server_default=""),
        sa.Column("generation_status", sa.String(length=20), nullable=False, server_default="empty"),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["campaign_id"], ["campaigns.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("campaign_id"),
    )
    with op.batch_alter_table("campaign_dossiers", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_campaign_dossiers_campaign_id"),
            ["campaign_id"],
            unique=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("campaign_dossiers", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_campaign_dossiers_campaign_id"))
    op.drop_table("campaign_dossiers")
