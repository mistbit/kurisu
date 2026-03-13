"""Integration tests for sync state and scheduler functionality.

These tests use SQLite test database with mocked Redis.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import patch

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_state import SyncStatus


@pytest.mark.asyncio
async def test_sync_state_service_basic_operations(db_session: AsyncSession, mock_redis):
    """Test SyncStateService basic create and update operations."""
    from app.services.sync_state_service import SyncStateService

    with patch('app.services.sync_state_service.redis_client', mock_redis):
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


@pytest.mark.asyncio
async def test_sync_state_service_list_operations(db_session: AsyncSession, mock_redis):
    """Test SyncStateService list and batch operations."""
    from app.services.sync_state_service import SyncStateService

    with patch('app.services.sync_state_service.redis_client', mock_redis):
        sync_service = SyncStateService(db_session)

        # Create multiple sync states
        market_ids = [10, 11, 12]
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


@pytest.mark.asyncio
async def test_sync_state_endpoints(async_client, db_session, mock_redis):
    """Test sync state API endpoints."""
    from app.services.sync_state_service import SyncStateService

    with patch('app.services.sync_state_service.redis_client', mock_redis):
        sync_service = SyncStateService(db_session)
        await sync_service.get_or_create(
            market_id=1,
            timeframe="1h",
            exchange="binance",
            symbol="API/USDT",
            is_auto_syncing=False,
        )
        await db_session.commit()

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


@pytest.mark.asyncio
async def test_health_check_with_client(async_client):
    """Test health check endpoint."""
    response = await async_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_markets_sync_filters_requested_exchanges(async_client):
    """Test market sync endpoint loops over requested exchanges only."""

    synced_counts = {
        "binance": 3,
        "bybit": 2,
    }

    class DummyExchangeService:
        def __init__(self, exchange_id: str):
            self.exchange_id = exchange_id

        async def initialize(self):
            return None

        async def close(self):
            return None

    async def fake_sync_markets(self, quote_allowlist=None, quote_denylist=None):
        assert quote_allowlist == ["USDT"]
        assert quote_denylist is None
        return synced_counts[self.exchange_service.exchange_id]

    with patch("app.main.ExchangeService", DummyExchangeService):
        with patch("app.main.MarketService.sync_markets", new=fake_sync_markets):
            response = await async_client.post(
                "/api/v1/markets/sync",
                json={
                    "exchanges": ["binance", "bybit"],
                    "quote_allowlist": ["USDT"],
                },
            )

    assert response.status_code == 200
    assert response.json() == {"synced": 5}


@pytest.mark.asyncio
async def test_markets_sync_rejects_unsupported_exchange(async_client):
    """Test market sync endpoint returns 400 for unsupported exchanges."""

    class DummyExchangeService:
        def __init__(self, exchange_id: str):
            self.exchange_id = exchange_id

        async def initialize(self):
            raise ValueError(f"Exchange {self.exchange_id} not supported by ccxt")

        async def close(self):
            return None

    with patch("app.main.ExchangeService", DummyExchangeService):
        response = await async_client.post(
            "/api/v1/markets/sync",
            json={"exchanges": ["definitely-not-real"]},
        )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Exchange definitely-not-real not supported by ccxt"
    }
