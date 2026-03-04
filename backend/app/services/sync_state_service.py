"""Service for managing data synchronization state.

This module provides a high-level service interface for all operations
related to tracking and managing data synchronization states.
"""
import json
import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.redis import redis_client
from app.models.sync_state import DataSyncState, SyncStatus

logger = logging.getLogger(__name__)

# Cache TTL in seconds
CACHE_TTL = 300  # 5 minutes


def _serialize_sync_state(sync_state: DataSyncState) -> str:
    """Serialize a DataSyncState to JSON string for caching."""
    return json.dumps({
        "id": sync_state.id,
        "market_id": sync_state.market_id,
        "exchange": sync_state.exchange,
        "symbol": sync_state.symbol,
        "timeframe": sync_state.timeframe,
        "sync_status": sync_state.sync_status,
        "last_sync_time": sync_state.last_sync_time.isoformat() if sync_state.last_sync_time else None,
        "backfill_completed_until": sync_state.backfill_completed_until.isoformat() if sync_state.backfill_completed_until else None,
        "is_auto_syncing": sync_state.is_auto_syncing,
        "error_message": sync_state.error_message,
        "last_error_time": sync_state.last_error_time.isoformat() if sync_state.last_error_time else None,
        "created_at": sync_state.created_at.isoformat() if sync_state.created_at else None,
        "updated_at": sync_state.updated_at.isoformat() if sync_state.updated_at else None,
    })


class SyncStateService:
    """Service for managing data synchronization states."""

    def __init__(self, db: AsyncSession):
        """Initialize the sync state service.

        Args:
            db: Database session
        """
        self.db = db

    # ============ Query Methods ============

    async def get_by_market_timeframe(
        self,
        market_id: int,
        timeframe: str,
    ) -> Optional[DataSyncState]:
        """Get sync state by market_id and timeframe.

        Args:
            market_id: Market ID
            timeframe: Timeframe (e.g., "1h", "4h", "1d")

        Returns:
            Sync state record, or None if not found
        """
        # Try cache first
        cache_key = f"sync_state:{market_id}:{timeframe}"
        cached = await redis_client.get(cache_key)
        if cached:
            return DataSyncState.model_validate_json(cached)

        # Query database
        result = await self.db.execute(
            select(DataSyncState)
            .options(selectinload(DataSyncState.market))
            .where(
                DataSyncState.market_id == market_id,
                DataSyncState.timeframe == timeframe,
            )
        )
        sync_state = result.scalar_one_or_none()

        # Cache the result
        if sync_state:
            await redis_client.set(cache_key, _serialize_sync_state(sync_state), ex=CACHE_TTL)

        return sync_state

    async def get_by_id(self, sync_state_id: int) -> Optional[DataSyncState]:
        """Get sync state by ID.

        Args:
            sync_state_id: Sync state ID

        Returns:
            Sync state record, or None if not found
        """
        result = await self.db.execute(
            select(DataSyncState)
            .options(selectinload(DataSyncState.market))
            .where(DataSyncState.id == sync_state_id)
        )
        return result.scalar_one_or_none()

    async def list_auto_syncing(
        self,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DataSyncState]:
        """List auto-syncing states with optional status filter.

        Args:
            status: Filter by sync status (idle, syncing, error)
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of sync state records
        """
        query = select(DataSyncState).where(DataSyncState.is_auto_syncing)

        if status:
            query = query.where(DataSyncState.sync_status == status)

        query = query.order_by(DataSyncState.market_id, DataSyncState.timeframe)
        query = query.limit(limit).offset(offset)

        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def list_by_exchange(
        self,
        exchange: str,
        limit: int = 100,
        offset: int = 0,
    ) -> list[DataSyncState]:
        """List sync states by exchange.

        Args:
            exchange: Exchange identifier
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of sync state records
        """
        result = await self.db.execute(
            select(DataSyncState)
            .where(DataSyncState.exchange == exchange)
            .order_by(DataSyncState.market_id, DataSyncState.timeframe)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_error_states(
        self,
        hours_threshold: int = 24,
    ) -> list[DataSyncState]:
        """Get states with recent errors.

        Args:
            hours_threshold: Only return errors within this many hours

        Returns:
            List of sync state records with errors
        """
        threshold_time = datetime.now(timezone.utc) - timedelta(hours=hours_threshold)

        result = await self.db.execute(
            select(DataSyncState)
            .where(
                DataSyncState.sync_status == SyncStatus.ERROR,
                DataSyncState.last_error_time >= threshold_time,
            )
            .order_by(DataSyncState.last_error_time.desc())
        )
        return list(result.scalars().all())

    async def get_idle_states(
        self,
        limit: int = 100,
    ) -> list[DataSyncState]:
        """Get idle states that are ready for sync.

        Args:
            limit: Maximum number of results

        Returns:
            List of idle sync state records
        """
        result = await self.db.execute(
            select(DataSyncState)
            .where(
                DataSyncState.is_auto_syncing,
                DataSyncState.sync_status == SyncStatus.IDLE,
            )
            .order_by(DataSyncState.last_sync_time.asc().nullsfirst())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_by_status(self, status: Optional[str] = None) -> int:
        """Count sync states by status.

        Args:
            status: Filter by sync status, or None for all

        Returns:
            Count of sync states
        """
        query = select(func.count(DataSyncState.id))
        if status:
            query = query.where(DataSyncState.sync_status == status)

        result = await self.db.execute(query)
        return result.scalar()

    # ============ Create/Update Methods ============

    @asynccontextmanager
    async def _cache_invalidation(self, market_id: int, timeframe: str) -> AsyncGenerator[None, None]:
        """Context manager for cache invalidation."""
        cache_key = f"sync_state:{market_id}:{timeframe}"
        yield
        await redis_client.delete(cache_key)

    async def get_or_create(
        self,
        market_id: int,
        timeframe: str,
        exchange: str = "",
        symbol: str = "",
        **kwargs,
    ) -> DataSyncState:
        """Get existing sync state or create a new one.

        Args:
            market_id: Market ID
            timeframe: Timeframe
            exchange: Exchange identifier
            symbol: Trading pair symbol
            **kwargs: Additional fields for the sync state

        Returns:
            The sync state record (existing or newly created)
        """
        async with self._cache_invalidation(market_id, timeframe):
            result = await self.db.execute(
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
                    exchange=exchange,
                    symbol=symbol,
                    **kwargs,
                )
                self.db.add(sync_state)
                await self.db.flush()

            return sync_state

    async def update_sync_time(
        self,
        market_id: int,
        timeframe: str,
        sync_time: datetime,
    ) -> DataSyncState:
        """Update last sync time for a market/timeframe.

        Args:
            market_id: Market ID
            timeframe: Timeframe
            sync_time: New sync time

        Returns:
            The updated sync state
        """
        async with self._cache_invalidation(market_id, timeframe):
            sync_state = await self.get_or_create(market_id, timeframe)
            sync_state.last_sync_time = sync_time
            await self.db.flush()
            return sync_state

    async def set_status(
        self,
        market_id: int,
        timeframe: str,
        status: str,
        error: Optional[str] = None,
    ) -> DataSyncState:
        """Set sync status for a market/timeframe.

        Args:
            market_id: Market ID
            timeframe: Timeframe
            status: New status (idle, syncing, error)
            error: Error message (if status is error)

        Returns:
            The updated sync state
        """
        async with self._cache_invalidation(market_id, timeframe):
            sync_state = await self.get_or_create(market_id, timeframe)
            sync_state.sync_status = status

            if status == SyncStatus.ERROR:
                sync_state.error_message = error[:500] if error else None
                sync_state.last_error_time = datetime.now(timezone.utc)
            elif status == SyncStatus.IDLE:
                sync_state.error_message = None

            await self.db.flush()
            return sync_state

    async def enable_auto_sync(
        self,
        market_id: int,
        timeframe: str,
    ) -> DataSyncState:
        """Enable auto-syncing for a market/timeframe.

        Args:
            market_id: Market ID
            timeframe: Timeframe

        Returns:
            The updated sync state
        """
        async with self._cache_invalidation(market_id, timeframe):
            sync_state = await self.get_or_create(market_id, timeframe)
            sync_state.is_auto_syncing = True
            sync_state.sync_status = SyncStatus.IDLE
            sync_state.error_message = None
            await self.db.flush()
            return sync_state

    async def disable_auto_sync(
        self,
        market_id: int,
        timeframe: str,
    ) -> DataSyncState:
        """Disable auto-syncing for a market/timeframe.

        Args:
            market_id: Market ID
            timeframe: Timeframe

        Returns:
            The updated sync state
        """
        async with self._cache_invalidation(market_id, timeframe):
            sync_state = await self.get_or_create(market_id, timeframe)
            sync_state.is_auto_syncing = False
            await self.db.flush()
            return sync_state

    async def mark_backfill_completed(
        self,
        market_id: int,
        timeframe: str,
        until: datetime,
    ) -> DataSyncState:
        """Mark backfill as completed until a certain time.

        Args:
            market_id: Market ID
            timeframe: Timeframe
            until: Time until which backfill is complete

        Returns:
            The updated sync state
        """
        async with self._cache_invalidation(market_id, timeframe):
            sync_state = await self.get_or_create(market_id, timeframe)
            sync_state.backfill_completed_until = until
            await self.db.flush()
            return sync_state

    # ============ Batch Operations ============

    async def enable_auto_sync_batch(
        self,
        market_ids: list[int],
        timeframes: list[str],
    ) -> int:
        """Enable auto-syncing for multiple market/timeframe combinations.

        Args:
            market_ids: List of market IDs
            timeframes: List of timeframes

        Returns:
            Number of records updated
        """
        count = 0
        for market_id in market_ids:
            for timeframe in timeframes:
                await self.enable_auto_sync(market_id, timeframe)
                count += 1
        return count

    async def disable_auto_sync_batch(
        self,
        market_ids: list[int],
        timeframes: list[str],
    ) -> int:
        """Disable auto-syncing for multiple market/timeframe combinations.

        Args:
            market_ids: List of market IDs
            timeframes: List of timeframes

        Returns:
            Number of records updated
        """
        count = 0
        for market_id in market_ids:
            for timeframe in timeframes:
                await self.disable_auto_sync(market_id, timeframe)
                count += 1
        return count

    async def reset_error_states(self, hours_threshold: int = 24) -> int:
        """Reset error states back to idle.

        Args:
            hours_threshold: Only reset errors within this many hours

        Returns:
            Number of records updated
        """
        error_states = await self.get_error_states(hours_threshold)
        count = 0

        for sync_state in error_states:
            await self.set_status(
                sync_state.market_id,
                sync_state.timeframe,
                SyncStatus.IDLE,
            )
            count += 1

        return count

    async def get_all_sync_states(
        self,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[DataSyncState]:
        """Get all sync states with pagination.

        Args:
            limit: Maximum number of results
            offset: Pagination offset

        Returns:
            List of sync state records
        """
        result = await self.db.execute(
            select(DataSyncState)
            .options(selectinload(DataSyncState.market))
            .order_by(DataSyncState.market_id, DataSyncState.timeframe)
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())