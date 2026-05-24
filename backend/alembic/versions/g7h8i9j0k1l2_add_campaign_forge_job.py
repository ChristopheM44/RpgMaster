"""add campaign forge job

Revision ID: g7h8i9j0k1l2
Revises: f6a7b8c9d0e1
Create Date: 2026-05-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g7h8i9j0k1l2"
down_revision: Union[str, Sequence[str], None] = "f6a7b8c9d0e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("campaign_dossiers") as batch_op:
        batch_op.add_column(
            sa.Column(
                "forge_job",
                sa.JSON(),
                nullable=False,
                server_default=sa.text("'{}'"),
            )
        )
    with op.batch_alter_table("campaign_dossiers") as batch_op:
        batch_op.alter_column("forge_job", server_default=None)


def downgrade() -> None:
    with op.batch_alter_table("campaign_dossiers") as batch_op:
        batch_op.drop_column("forge_job")
