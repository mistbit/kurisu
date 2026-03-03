"""Data synchronization state tracking model.

This module defines the DataSyncState model for tracking the progress
of market data synchronization across exchanges, symbols, and timeframes.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Index, UniqueConstraint
from sqlalchemy import func

from app.core.database import Base


class SyncStatus:
    """Synchronization status constants."""
    IDLE = "idle"
    SYNCING = "syncing"
    ERROR = "error"


class DataSyncState(Base):
    """Data synchronization state tracking for market data backfill and auto-sync.

    Records synchronization progress for each market/timeframe combination,
    enabling incremental updates and avoiding full re-runs.
    """
    __tablename__ = "data_sync_state"

    id = Column(Integer, primary_key=True, index=True)
    exchange = Column(String(50), nullable=False)
    symbol = Column(String(50), nullable=False)
    timeframe = Column(String(10), nullable=False)

    # Foreign key to markets table for efficient joins
    market_id = Column(Integer, ForeignKey("markets.id"), nullable=True)

    # Synchronization status tracking
    sync_status = Column(String(20), default=SyncStatus.IDLE, nullable=False, index=True)
    error_message = Column(String(500), nullable=True)
    last_error_time = Column(DateTime(timezone=True), nullable=True)

    # The last timestamp that was successfully synced from the exchange API
    last_sync_time = Column(DateTime(timezone=True), nullable=True, index=True)

    # The timestamp until which historical backfill has been completed
    # This can be earlier than last_sync_time if we only backfill a limited range
    backfill_completed_until = Column(DateTime(timezone=True), nullable=True, index=True)

    # Whether automatic syncing is enabled for this combination
    is_auto_syncing = Column(Boolean, default=False, nullable=False, index=True)

    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Unique constraint ensures one record per market/timeframe combination
    __table_args__ = (
        UniqueConstraint('exchange', 'symbol', 'timeframe', name='uix_exchange_symbol_timeframe'),
        Index('ix_data_sync_state_market_id', 'market_id'),
        Index('ix_data_sync_state_sync_status', 'sync_status'),
    )
