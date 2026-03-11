"""Tests for backfill task functionality."""
import json
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_state import DataSyncState
from app.api.v1.sync import (
    _run_backfill_task,
)


@pytest.mark.asyncio
async def test_backfill_endpoint(async_client: AsyncClient, db_session: AsyncSession):
    """Test the backfill endpoint creates a task."""
    # Create a sync state first
    sync_state = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        market_id=1,
        is_auto_syncing=False,
    )
    db_session.add(sync_state)
    await db_session.commit()

    # Trigger backfill
    response = await async_client.post(
        "/api/v1/data/backfill",
        json={
            "market_ids": [1],
            "timeframes": ["1h"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert "task_id" in data
    assert data["status"] == "queued"
    assert data["estimated_timeframes"] >= 1


@pytest.mark.asyncio
async def test_backfill_endpoint_no_markets(async_client: AsyncClient):
    """Test backfill endpoint with non-existent markets."""
    response = await async_client.post(
        "/api/v1/data/backfill",
        json={
            "market_ids": [99999],
            "timeframes": ["1h"],
        },
    )

    assert response.status_code == 400
    assert "No matching markets" in response.json()["detail"]


@pytest.mark.asyncio
async def test_backfill_endpoint_symbol_pattern(async_client: AsyncClient, db_session: AsyncSession):
    """Test backfill endpoint with symbol pattern."""
    # Create multiple sync states
    for i, symbol in enumerate(["BTC/USDT", "ETH/USDT", "SOL/USDT"]):
        sync_state = DataSyncState(
            exchange="binance",
            symbol=symbol,
            timeframe="1h",
            market_id=i + 100,
            is_auto_syncing=False,
        )
        db_session.add(sync_state)
    await db_session.commit()

    # Trigger backfill with pattern
    response = await async_client.post(
        "/api/v1/data/backfill",
        json={
            "symbol_pattern": "BTC",
            "timeframes": ["1h"],
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "queued"


@pytest.mark.asyncio
async def test_backfill_task_status_not_found(async_client: AsyncClient):
    """Test getting status of non-existent task."""
    response = await async_client.get("/api/v1/data/backfill/nonexistent_task")

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_backfill_task_execution(db_session: AsyncSession, mock_redis):
    """Test backfill task execution."""
    task_id = "test_backfill_001"
    backfill_items = [
        {
            "market_id": 1,
            "symbol": "BTC/USDT",
            "exchange": "binance",
            "timeframe": "1h",
        }
    ]

    # Mock the exchange service and market data service
    with patch("app.api.v1.sync._get_exchange_service") as mock_get_service:
        mock_exchange_service = AsyncMock()
        mock_get_service.return_value = mock_exchange_service

        with patch("app.api.v1.sync.MarketDataService") as mock_mds_class:
            mock_mds = MagicMock()
            mock_mds.fetch_ohlcv_history = AsyncMock(return_value=100)
            mock_mds_class.return_value = mock_mds

            with patch("app.core.database.SessionLocal") as mock_session_local:
                # Create an async context manager for the session
                async def get_session():
                    yield db_session

                mock_session_local.return_value.__aenter__ = AsyncMock(return_value=db_session)
                mock_session_local.return_value.__aexit__ = AsyncMock(return_value=None)

                with patch("app.api.v1.sync.redis_client", mock_redis):
                    # Run the task
                    await _run_backfill_task(
                        task_id,
                        backfill_items,
                        start_time=datetime.now(timezone.utc) - timedelta(days=7),
                        end_time=datetime.now(timezone.utc),
                    )

    # Verify the task was processed (check mock calls)
    assert mock_redis.setex.called


@pytest.mark.asyncio
async def test_backfill_invalid_timeframe(async_client: AsyncClient):
    """Test backfill with invalid timeframe."""
    response = await async_client.post(
        "/api/v1/data/backfill",
        json={
            "market_ids": [1],
            "timeframes": ["invalid_tf"],
        },
    )

    assert response.status_code == 422  # Validation error


@pytest.mark.asyncio
async def test_backfill_task_status_endpoint(async_client: AsyncClient, mock_redis):
    """Test the backfill task status endpoint."""
    # Create a task status in Redis
    task_id = "test_status_001"
    task_status = {
        "task_id": task_id,
        "status": "running",
        "total_combinations": 10,
        "completed_combinations": 5,
        "failed_combinations": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
    }
    mock_redis.get = AsyncMock(return_value=json.dumps(task_status))

    # Get the status
    response = await async_client.get(f"/api/v1/data/backfill/{task_id}")

    assert response.status_code == 200
    data = response.json()
    assert data["task_id"] == task_id
    assert data["status"] == "running"
    assert data["total_combinations"] == 10
    assert data["completed_combinations"] == 5