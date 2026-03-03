"""add data_sync_state table

Revision ID: 1d71e2698c91
Revises: 1ba6c9e2b43d
Create Date: 2026-03-03 11:39:15.984458

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1d71e2698c91'
down_revision: Union[str, Sequence[str], None] = '1ba6c9e2b43d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Create data_sync_state table for tracking sync progress
    op.create_table('data_sync_state',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('exchange', sa.String(length=50), nullable=False),
    sa.Column('symbol', sa.String(length=50), nullable=False),
    sa.Column('timeframe', sa.String(length=10), nullable=False),
    sa.Column('last_sync_time', sa.DateTime(timezone=True), nullable=True),
    sa.Column('backfill_completed_until', sa.DateTime(timezone=True), nullable=True),
    sa.Column('is_auto_syncing', sa.Boolean(), nullable=False, server_default='false'),
    sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('NOW()')),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('exchange', 'symbol', 'timeframe', name='uix_exchange_symbol_timeframe')
    )
    op.create_index('ix_data_sync_state_last_sync_time', 'data_sync_state', ['last_sync_time'])
    op.create_index('ix_data_sync_state_backfill_completed_until', 'data_sync_state', ['backfill_completed_until'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_data_sync_state_backfill_completed_until', table_name='data_sync_state')
    op.drop_index('ix_data_sync_state_last_sync_time', table_name='data_sync_state')
    op.drop_table('data_sync_state')
