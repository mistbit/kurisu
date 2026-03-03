"""enhance data_sync_state with market_id and sync_status

Revision ID: 4f94579b9e14
Revises: 1d71e2698c91
Create Date: 2026-03-03 15:23:22.966919

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4f94579b9e14'
down_revision: Union[str, Sequence[str], None] = '1d71e2698c91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add new columns to data_sync_state table
    op.add_column('data_sync_state', sa.Column('market_id', sa.Integer(), nullable=True))
    op.add_column('data_sync_state', sa.Column('sync_status', sa.String(length=20), server_default='idle', nullable=False))
    op.add_column('data_sync_state', sa.Column('error_message', sa.String(length=500), nullable=True))
    op.add_column('data_sync_state', sa.Column('last_error_time', sa.DateTime(timezone=True), nullable=True))

    # Create indexes
    op.create_index('ix_data_sync_state_market_id', 'data_sync_state', ['market_id'])
    op.create_index('ix_data_sync_state_sync_status', 'data_sync_state', ['sync_status'])

    # Add foreign key constraint
    op.create_foreign_key(
        'fk_data_sync_state_market_id',
        'data_sync_state',
        'markets',
        ['market_id'],
        ['id']
    )

    # Populate market_id from existing exchange/symbol pairs
    op.execute("""
        UPDATE data_sync_state
        SET market_id = m.id
        FROM markets m
        WHERE data_sync_state.exchange = m.exchange
          AND data_sync_state.symbol = m.symbol
    """)


def downgrade() -> None:
    """Downgrade schema."""
    # Drop foreign key constraint
    op.drop_constraint('fk_data_sync_state_market_id', 'data_sync_state', type_='foreignkey')

    # Drop indexes
    op.drop_index('ix_data_sync_state_sync_status', table_name='data_sync_state')
    op.drop_index('ix_data_sync_state_market_id', table_name='data_sync_state')

    # Drop columns
    op.drop_column('data_sync_state', 'last_error_time')
    op.drop_column('data_sync_state', 'error_message')
    op.drop_column('data_sync_state', 'sync_status')
    op.drop_column('data_sync_state', 'market_id')
