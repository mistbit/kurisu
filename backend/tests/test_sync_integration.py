"""Integration tests for sync state and scheduler functionality.

These tests use the actual database (SQLite) but are isolated from exchange operations.
"""
import pytest
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_state import DataSyncState, SyncStatus


@pytest.mark.asyncio
async def test_sync_state_service_basic_operations(db_session: AsyncSession):
    """Test SyncStateService basic create and update operations."""
    from app.services.sync_state_service import SyncStateService

    sync_service = SyncStateService(db_session)

    # Test get_or_create
    sync_state = await sync_service.get_or_create(
        market_id=1,
        timeframe="1h",
        exchange="binance",
        symbol="TEST/USDT",
    )
    await db_session.commit()

    assert sync_state.market_id == 1
    assert sync_state.timeframe == "1h"

    # Test update_sync_time
    test_time = datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc)
    await sync_service.update_sync_time(1, "1h", test_time)
    await db_session.commit()

    result = await sync_service.get_by_market_timeframe(1, "1h")
    assert result.last_sync_time == test_time

    # Test enable_auto_sync
    await sync_service.enable_auto_sync(1, "1h")
    await db_session.commit()

    result = await sync_service.get_by_market_timeframe(1, "1h")
    assert result.is_auto_syncing is True
    assert result.sync_status == SyncStatus.IDLE

    # Test set_status transitions
    await sync_service.set_status(1, "1h", SyncStatus.SYNCING)
    await db_session.commit()

    result = await sync_service.get_by_market_timeframe(1, "1h")
    assert result.sync_status == SyncStatus.SYNCING

    # Set to error
    await sync_service.set_status(1, "1h", SyncStatus.ERROR, error="Test error")
    await db_session.commit()

    result = await sync_service.get_by_market_timeframe(1, "1h")
    assert result.sync_status == SyncStatus.ERROR
    assert result.error_message == "Test error"
    assert result.last_error_time is not None

    # Reset error states
    count = await sync_service.reset_error_states(hours_threshold=24)
    assert count >= 1

    result = await sync_service.get_by_market_timeframe(1, "1h")
    assert result.sync_status == SyncStatus.IDLE
    assert result.error_message is None


@pytest.mark.asyncio
async def test_sync_state_service_list_operations(db_session: AsyncSession):
    """Test SyncStateService list and batch operations."""
    from app.services.sync_state_service import SyncStateService

    sync_service = SyncStateService(db_session)

    # Create multiple sync states
    market_ids = [1, 2, 3]
    timeframes = ["1h", "4h", "1d"]

    for market_id in market_ids:
        for timeframe in timeframes:
            await sync_service.get_or_create(
                market_id=market_id,
                timeframe=timeframe,
                exchange="binance",
                symbol=f"TEST{market_id}/USDT",
            )
    await db_session.commit()

    # Test list_auto_syncing (none yet enabled)
    auto_syncing = await sync_service.list_auto_syncing(limit=10)
    assert len(auto_syncing) == 0

    # Enable auto-sync for all
    await sync_service.enable_auto_sync_batch(market_ids, timeframes)
    await db_session.commit()

    # Check auto-syncing states
    auto_syncing = await sync_service.list_auto_syncing(limit=10)
    assert len(auto_syncing) == len(market_ids) * len(timeframes)
    assert all(s.is_auto_syncing for s in auto_syncing)

    # Test get_idle_states
    idle_states = await sync_service.get_idle_states(limit=10)
    assert len(idle_states) >= len(market_ids) * len(timeframes)

    # Test disable_auto_sync_batch
    count = await sync_service.disable_auto_sync_batch(market_ids, ["1h"])
    assert count == len(market_ids)

    await db_session.commit()

    # Verify only 1h is disabled
    states_1h = await sync_service.list_auto_syncing(limit=100)
    assert all(s.timeframe != "1h" for s in states_1h)


@pytest.mark.asyncio
async def test_auto_sync_job_no_states(db_session: AsyncSession):
    """Test auto_sync job when no states exist."""
    from app.scheduler import auto_sync_ohlcv

    # This should not raise any errors
    await auto_sync_ohlcv()


@pytest.mark.asyncio
async def test_auto_sync_job_with_idle_state(db_session: AsyncSession):
    """Test auto_sync job with an idle but invalid state."""
    from app.scheduler import auto_sync_ohlcv
    from app.services.sync_state_service import SyncStateService

    sync_service = SyncStateService(db_session)

    # Create a state with invalid market_id
    await sync_service.get_or_create(
        market_id=99999,  # Invalid ID
        timeframe="1h",
        exchange="binance",
        symbol="INVALID/USDT",
        is_auto_syncing=True,
    )
    await db_session.commit()

    # Run the job - should handle the error gracefully
    await auto_sync_ohlcv()

    # Check that the error was recorded
    result = await db_session.execute(
        select(DataSyncState).where(DataSyncState.market_id == 99999)
    )
    state = result.scalar_one()
    assert state.sync_status == SyncStatus.ERROR
    assert state.error_message is not None


@pytest.mark.asyncio
async def test_job_stats_tracking():
    """Test that job statistics are properly tracked."""
    from app.scheduler import auto_sync_ohlcv, get_job_stats, get_all_job_stats

    # Run a job to generate stats
    await auto_sync_ohlcv()

    # Get job stats
    stats = await get_job_stats("auto_sync_ohlcv")
    assert stats is not None
    assert "total_runs" in stats
    assert stats["total_runs"] >= 1

    # Get all job stats
    all_stats = await get_all_job_stats()
    assert "auto_sync_ohlcv" in all_stats


@pytest.mark.asyncio
async def test_scheduler_status_endpoint(async_client):
    """Test the scheduler status endpoint."""
    from app.scheduler import start_scheduler

    # Start scheduler
    start_scheduler()

    # Test the endpoint
    response = await async_client.get("/api/v1/scheduler/status")
    assert response.status_code == 200

    data = response.json()
    assert "running" in data
    assert "jobs" in data
    assert "active_connections" in data

    # Verify job list
    job_ids = [job["id"] for job in data["jobs"]]
    assert "auto_sync_ohlcv" in job_ids


@pytest.mark.asyncio
async def test_sync_state_endpoints(async_client):
    """Test sync state API endpoints."""
    # Create a sync state first
    from app.services.sync_state_service import SyncStateService
    from app.core.database import SessionLocal

    async with SessionLocal() as db:
        sync_service = SyncStateService(db)
        await sync_service.get_or_create(
            market_id=1,
            timeframe="1h",
            exchange="binance",
            symbol="API/USDT",
            is_auto_syncing=False,
        )
        await db.commit()

    # Test list sync states
    response = await async_client.get("/api/v1/data/sync_state")
    assert response.status_code == 200

    data = response.json()
    assert "items" in data
    assert "total" in data

    # Test get specific sync state (will fail since it doesn't exist)
    response = await async_client.get("/api/v1/data/sync_state/99999")
    assert response.status_code == 404

    # Test enable auto-sync
    response = await async_client.post(
        "/api/v1/data/auto_sync",
        json={
            "market_id": 1,
            "timeframes": ["1h", "4h"],
            "enabled": True,
        },
    )
    assert response.status_code == 200

    data = response.json()
    assert "updated" in data
    assert data["updated"] == 2

    # Test backfill endpoint
    response = await async_client.post(
        "/api/v1/data/backfill",
        json={
            "market_ids": [1],
            "timeframes": ["1h"],
            "start_time": "2026-01-01T00:00:00Z",
            "end_time": "2026-03-01T00:00:00Z",
        },
    )
    assert response.status_code == 200

    data = response.json()
    assert "task_id" in data
    assert "status" in data


@pytest.mark.asyncio
async def test_health_check_with_scheduler(async_client):
    """Test health check endpoint with scheduler running."""
    response = await async_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"