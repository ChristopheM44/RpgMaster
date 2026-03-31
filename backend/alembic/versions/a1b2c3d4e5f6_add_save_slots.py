"""add_save_slots

Revision ID: a1b2c3d4e5f6
Revises: e62af9c53a42
Create Date: 2026-03-31 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'e62af9c53a42'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'save_slots',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('session_id', sa.String(length=36), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('phase', sa.String(length=50), nullable=False),
        sa.Column('turn_number', sa.Integer(), nullable=False),
        sa.Column('round_number', sa.Integer(), nullable=False),
        sa.Column('state_data', sa.JSON(), nullable=False),
        sa.Column('characters_snapshot', sa.JSON(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['session_id'], ['sessions.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('save_slots', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_save_slots_session_id'), ['session_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('save_slots', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_save_slots_session_id'))

    op.drop_table('save_slots')
