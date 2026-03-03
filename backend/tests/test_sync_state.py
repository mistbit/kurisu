"""Tests for DataSyncState model."""
import pytest
from datetime import datetime, timezone

from app.models.sync_state import DataSyncState, SyncStatus
from sqlalchemy import select


@pytest.mark.asyncio
async def test_create_sync_state(db_session):
    """Test creating a new sync state record."""
    sync_state = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        market_id=1,
        last_sync_time=datetime(2026, 3, 3, 10, 0, tzinfo=timezone.utc),
        backfill_completed_until=datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc),
        is_auto_syncing=True,
    )

    db_session.add(sync_state)
    await db_session.commit()
    await db_session.refresh(sync_state)

    assert sync_state.id is not None
    assert sync_state.exchange == "binance"
    assert sync_state.symbol == "BTC/USDT"
    assert sync_state.timeframe == "1h"
    assert sync_state.market_id == 1
    assert sync_state.sync_status == SyncStatus.IDLE
    assert sync_state.is_auto_syncing is True
    assert sync_state.created_at is not None
    assert sync_state.updated_at is not None


@pytest.mark.asyncio
async def test_sync_status_transitions(db_session):
    """Test sync status transitions."""
    sync_state = DataSyncState(
        exchange="binance",
        symbol="ETH/USDT",
        timeframe="4h",
        market_id=2,
        sync_status=SyncStatus.IDLE,
    )

    db_session.add(sync_state)
    await db_session.commit()

    # Transition to syncing
    await db_session.refresh(sync_state)
    sync_state.sync_status = SyncStatus.SYNCING
    await db_session.commit()
    await db_session.refresh(sync_state)
    assert sync_state.sync_status == SyncStatus.SYNCING

    # Transition to error
    sync_state.sync_status = SyncStatus.ERROR
    sync_state.error_message = "API rate limit exceeded"
    await db_session.commit()
    await db_session.refresh(sync_state)
    assert sync_state.sync_status == SyncStatus.ERROR
    assert sync_state.error_message == "API rate limit exceeded"


@pytest.mark.asyncio
async def test_update_last_sync_time(db_session):
    """Test updating last_sync_time."""
    sync_state = DataSyncState(
        exchange="binance",
        symbol="SOL/USDT",
        timeframe="1d",
        market_id=3,
        last_sync_time=datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc),
    )

    db_session.add(sync_state)
    await db_session.commit()

    await db_session.refresh(sync_state)
    sync_state.last_sync_time = datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc)
    await db_session.commit()
    await db_session.refresh(sync_state)

    assert sync_state.last_sync_time.replace(tzinfo=timezone.utc) == datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc)


@pytest.mark.asyncio
async def test_query_by_sync_status(db_session):
    """Test querying sync states by sync status."""
    db_session.add(DataSyncState(exchange="binance", symbol="XRP/USDT", timeframe="1h", market_id=4, sync_status=SyncStatus.IDLE, is_auto_syncing=True))
    db_session.add(DataSyncState(exchange="binance", symbol="ADA/USDT", timeframe="1h", market_id=5, sync_status=SyncStatus.ERROR, is_auto_syncing=True))
    db_session.add(DataSyncState(exchange="binance", symbol="DOGE/USDT", timeframe="1h", market_id=6, sync_status=SyncStatus.IDLE, is_auto_syncing=True))
    await db_session.commit()

    result = await db_session.execute(
        select(DataSyncState).where(DataSyncState.sync_status == SyncStatus.IDLE)
    )
    idle_states = result.scalars().all()

    assert len(idle_states) == 2
    assert all(state.sync_status == SyncStatus.IDLE for state in idle_states)