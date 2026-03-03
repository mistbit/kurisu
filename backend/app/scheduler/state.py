"""Scheduler state management utilities.

This module provides utilities for tracking scheduler job states and
managing synchronization state from scheduler jobs.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.sync_state import DataSyncState, SyncStatus
from app.models.market import Market

logger = logging.getLogger(__name__)


async def get_or_create_sync_state(
    market_id: int,
    timeframe: str,
    db: AsyncSession,
) -> DataSyncState:
    """Get an existing sync state or create a new one.

    Args:
        market_id: Market ID from the markets table
        timeframe: Timeframe (e.g., "1h", "4h", "1d")
        db: Database session

    Returns:
        The sync state record (existing or newly created)
    """
    result = await db.execute(
        select(DataSyncState).where(
            DataSyncState.market_id == market_id,
            DataSyncState.timeframe == timeframe,
        )
    )
    sync_state = result.scalar_one_or_none()

    if sync_state is None:
        sync_state = DataSyncState(
            market_id=market_id,
            timeframe=timeframe,
            exchange="",  # Will be populated from market
            symbol="",   # Will be populated from market
        )
        db.add(sync_state)
        await db.flush()

    return sync_state


async def get_or_create_sync_state_by_symbol(
    exchange: str,
    symbol: str,
    timeframe: str,
    db: AsyncSession,
) -> Optional[DataSyncState]:
    """Get or create sync state using exchange/symbol (for backward compatibility).

    Args:
        exchange: Exchange identifier (e.g., "binance")
        symbol: Trading pair symbol (e.g., "BTC/USDT")
        timeframe: Timeframe (e.g., "1h", "4h", "1d")
        db: Database session

    Returns:
        The sync state record (existing or newly created), or None if market not found
    """
    # Get market_id first
    market_result = await db.execute(
        select(Market).where(
            Market.exchange == exchange,
            Market.symbol == symbol,
        )
    )
    market = market_result.scalar_one_or_none()
    if not market:
        return None

    sync_state_result = await db.execute(
        select(DataSyncState).where(
            DataSyncState.market_id == market.id,
            DataSyncState.timeframe == timeframe,
        )
    )
    sync_state = sync_state_result.scalar_one_or_none()

    if sync_state is None:
        sync_state = DataSyncState(
            market_id=market.id,
            exchange=exchange,
            symbol=symbol,
            timeframe=timeframe,
        )
        db.add(sync_state)
        await db.flush()

    return sync_state


async def update_sync_state_by_market_id(
    market_id: int,
    timeframe: str,
    last_sync_time: Optional[datetime] = None,
    backfill_completed_until: Optional[datetime] = None,
    is_auto_syncing: Optional[bool] = None,
    sync_status: Optional[str] = None,
    error_message: Optional[str] = None,
) -> Optional[DataSyncState]:
    """Update a sync state record by market_id.

    Args:
        market_id: Market ID
        timeframe: Timeframe
        last_sync_time: New last sync time (optional)
        backfill_completed_until: New backfill completion time (optional)
        is_auto_syncing: New auto-syncing flag (optional)
        sync_status: New sync status (optional)
        error_message: New error message (optional)

    Returns:
        The updated sync state, or None if not found
    """
    async with SessionLocal() as db:
        result = await db.execute(
            select(DataSyncState).where(
                DataSyncState.market_id == market_id,
                DataSyncState.timeframe == timeframe,
            )
        )
        sync_state = result.scalar_one_or_none()

        if sync_state is None:
            return None

        if last_sync_time is not None:
            sync_state.last_sync_time = last_sync_time
        if backfill_completed_until is not None:
            sync_state.backfill_completed_until = backfill_completed_until
        if is_auto_syncing is not None:
            sync_state.is_auto_syncing = is_auto_syncing
        if sync_status is not None:
            sync_state.sync_status = sync_status
        if error_message is not None:
            sync_state.error_message = error_message

        await db.commit()
        await db.refresh(sync_state)

        return sync_state


async def set_auto_syncing_by_market_id(
    market_id: int,
    timeframe: str,
    enabled: bool,
) -> Optional[DataSyncState]:
    """Enable or disable auto-syncing for a market.

    Args:
        market_id: Market ID
        timeframe: Timeframe
        enabled: Whether to enable auto-syncing

    Returns:
        The updated sync state, or None if not found
    """
    return await update_sync_state_by_market_id(
        market_id, timeframe, is_auto_syncing=enabled
    )


async def get_pending_backfills(
    hours_threshold: int = 1,
) -> list[DataSyncState]:
    """Get sync states that need backfilling.

    Args:
        hours_threshold: Hours threshold for considering data stale

    Returns:
        List of sync states that need backfilling
    """
    threshold_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)

    async with SessionLocal() as db:
        result = await db.execute(
            select(DataSyncState).where(
                DataSyncState.last_sync_time.is_(None) |
                (DataSyncState.last_sync_time < threshold_time)
            )
        )
        return list(result.scalars().all())


async def get_auto_syncing_states() -> list[DataSyncState]:
    """Get all sync states with auto-syncing enabled and idle status.

    Returns:
        List of sync states with auto-syncing enabled
    """
    async with SessionLocal() as db:
        result = await db.execute(
            select(DataSyncState).where(
                DataSyncState.is_auto_syncing,
                DataSyncState.sync_status == SyncStatus.IDLE,
            )
        )
        return list(result.scalars().all())


async def get_market_by_id(
    market_id: int,
    db: AsyncSession,
) -> Optional[Market]:
    """Get the market by ID.

    Args:
        market_id: Market ID
        db: Database session

    Returns:
        The market, or None if not found
    """
    result = await db.execute(
        select(Market).where(Market.id == market_id)
    )
    return result.scalar_one_or_none()