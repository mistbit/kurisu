"""Tests for gap detection and auto-backfill functionality."""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch, MagicMock

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.sync_state import DataSyncState
from app.models.market import OHLCV
from app.scheduler.jobs import _detect_gaps, _trigger_gap_backfill


@pytest.mark.asyncio
async def test_detect_gaps_no_data(db_session: AsyncSession):
    """Test gap detection with no OHLCV data."""
    # Create a sync state
    sync_state = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        market_id=1,
        is_auto_syncing=True,
    )
    db_session.add(sync_state)
    await db_session.commit()

    # Detect gaps - should return empty list
    gaps = await _detect_gaps(db_session, sync_state)
    assert gaps == []


@pytest.mark.asyncio
async def test_detect_gaps_single_candle(db_session: AsyncSession):
    """Test gap detection with only one candle."""
    # Create sync state
    sync_state = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        market_id=1,
        is_auto_syncing=True,
    )
    db_session.add(sync_state)

    # Create single candle
    candle = OHLCV(
        time=datetime(2026, 3, 3, 10, 0, tzinfo=timezone.utc),
        market_id=1,
        timeframe="1h",
        open=50000.0,
        high=51000.0,
        low=49500.0,
        close=50800.0,
        volume=1000.0,
    )
    db_session.add(candle)
    await db_session.commit()

    # Detect gaps - should return empty (need at least 2 candles)
    gaps = await _detect_gaps(db_session, sync_state)
    assert gaps == []


@pytest.mark.asyncio
async def test_detect_gaps_continuous_data(db_session: AsyncSession):
    """Test gap detection with continuous data (no gaps)."""
    # Create sync state
    sync_state = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        market_id=1,
        is_auto_syncing=True,
    )
    db_session.add(sync_state)

    # Create continuous hourly candles (each with unique timestamp)
    base_time = datetime(2026, 3, 3, 10, 0, tzinfo=timezone.utc)
    for i in range(5):
        candle = OHLCV(
            time=base_time - timedelta(hours=i),
            market_id=1,
            timeframe="1h",
            open=50000.0 + i * 100,
            high=51000.0 + i * 100,
            low=49500.0 + i * 100,
            close=50800.0 + i * 100,
            volume=1000.0,
        )
        db_session.add(candle)
        await db_session.flush()  # Flush each to avoid batch issues
    await db_session.commit()

    # Detect gaps - should return empty
    gaps = await _detect_gaps(db_session, sync_state)
    assert gaps == []


@pytest.mark.asyncio
async def test_detect_gaps_with_missing_candles(db_session: AsyncSession):
    """Test gap detection with missing candles."""
    # Create sync state
    sync_state = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        market_id=1,
        is_auto_syncing=True,
    )
    db_session.add(sync_state)

    # Create candles with a 3-hour gap
    base_time = datetime(2026, 3, 3, 10, 0, tzinfo=timezone.utc)
    # Candle at 10:00
    db_session.add(OHLCV(
        time=base_time,
        market_id=1,
        timeframe="1h",
        open=50000.0,
        high=51000.0,
        low=49500.0,
        close=50800.0,
        volume=1000.0,
    ))
    await db_session.flush()
    # Candle at 6:00 (3-hour gap, missing 7:00, 8:00, 9:00)
    db_session.add(OHLCV(
        time=base_time - timedelta(hours=4),
        market_id=1,
        timeframe="1h",
        open=48000.0,
        high=49000.0,
        low=47500.0,
        close=48800.0,
        volume=1000.0,
    ))
    await db_session.commit()

    # Detect gaps
    gaps = await _detect_gaps(db_session, sync_state)

    assert len(gaps) == 1
    assert gaps[0]["missing_candles"] == 3


@pytest.mark.asyncio
async def test_detect_gaps_multiple_gaps(db_session: AsyncSession):
    """Test gap detection with multiple gaps."""
    # Create sync state
    sync_state = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        market_id=1,
        is_auto_syncing=True,
    )
    db_session.add(sync_state)

    base_time = datetime(2026, 3, 3, 10, 0, tzinfo=timezone.utc)

    # Candle at 10:00
    db_session.add(OHLCV(
        time=base_time,
        market_id=1,
        timeframe="1h",
        open=50000.0, high=51000.0, low=49500.0, close=50800.0, volume=1000.0,
    ))
    await db_session.flush()
    # Candle at 8:00 (1-hour gap)
    db_session.add(OHLCV(
        time=base_time - timedelta(hours=2),
        market_id=1,
        timeframe="1h",
        open=49000.0, high=50000.0, low=48500.0, close=49800.0, volume=1000.0,
    ))
    await db_session.flush()
    # Candle at 4:00 (3-hour gap)
    db_session.add(OHLCV(
        time=base_time - timedelta(hours=6),
        market_id=1,
        timeframe="1h",
        open=47000.0, high=48000.0, low=46500.0, close=47800.0, volume=1000.0,
    ))
    await db_session.commit()

    # Detect gaps
    gaps = await _detect_gaps(db_session, sync_state)

    assert len(gaps) == 2
    # First gap: 8:00 to 10:00 (missing 9:00 = 1 candle)
    # Second gap: 4:00 to 8:00 (missing 5:00, 6:00, 7:00 = 3 candles)
    missing_counts = [g["missing_candles"] for g in gaps]
    assert 1 in missing_counts
    assert 3 in missing_counts


@pytest.mark.asyncio
async def test_detect_gaps_different_timeframes(db_session: AsyncSession):
    """Test gap detection with different timeframes."""
    # Test 4h timeframe
    sync_state_4h = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="4h",
        market_id=1,
        is_auto_syncing=True,
    )
    db_session.add(sync_state_4h)

    base_time = datetime(2026, 3, 3, 12, 0, tzinfo=timezone.utc)

    # Candle at 12:00
    db_session.add(OHLCV(
        time=base_time,
        market_id=1,
        timeframe="4h",
        open=50000.0, high=51000.0, low=49500.0, close=50800.0, volume=1000.0,
    ))
    await db_session.flush()
    # Candle at 0:00 (8-hour gap = 1 missing 4h candle)
    db_session.add(OHLCV(
        time=base_time - timedelta(hours=12),
        market_id=1,
        timeframe="4h",
        open=48000.0, high=49000.0, low=47500.0, close=48800.0, volume=1000.0,
    ))
    await db_session.commit()

    gaps = await _detect_gaps(db_session, sync_state_4h)
    assert len(gaps) == 1
    # 12 hours / 4 hours = 3 intervals, minus 1 for the existing = 2 missing
    # Actually: 12 hours gap means 12/4 = 3 intervals, we have 2 candles
    # So missing = 3 - 1 = 2 candles (4:00, 8:00)
    assert gaps[0]["missing_candles"] == 2


@pytest.mark.asyncio
async def test_trigger_gap_backfill_small_gap(db_session: AsyncSession):
    """Test triggering backfill for small gaps."""
    sync_state = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        market_id=1,
        is_auto_syncing=True,
    )
    db_session.add(sync_state)
    await db_session.commit()

    gaps = [
        {"start": datetime(2026, 3, 3, 8, 0, tzinfo=timezone.utc),
         "end": datetime(2026, 3, 3, 10, 0, tzinfo=timezone.utc),
         "missing_candles": 1}
    ]

    # Mock the exchange service
    with patch("app.scheduler.jobs._get_exchange_service") as mock_get_service:
        mock_service = AsyncMock()
        mock_get_service.return_value = mock_service

        with patch("app.scheduler.jobs.MarketDataService") as mock_mds:
            mock_mds_instance = MagicMock()
            mock_mds_instance.fetch_ohlcv_history = AsyncMock(return_value=100)
            mock_mds.return_value = mock_mds_instance

            result = await _trigger_gap_backfill(db_session, sync_state, gaps)

            # Should have backfilled
            assert result == 1
            mock_mds_instance.fetch_ohlcv_history.assert_called_once()


@pytest.mark.asyncio
async def test_trigger_gap_backfill_large_gap(db_session: AsyncSession):
    """Test that large gaps are skipped."""
    sync_state = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        market_id=1,
        is_auto_syncing=True,
    )
    db_session.add(sync_state)
    await db_session.commit()

    # Large gap with 100 missing candles
    gaps = [
        {"start": datetime(2026, 2, 1, 0, 0, tzinfo=timezone.utc),
         "end": datetime(2026, 3, 3, 0, 0, tzinfo=timezone.utc),
         "missing_candles": 100}
    ]

    result = await _trigger_gap_backfill(db_session, sync_state, gaps)

    # Should skip large gap
    assert result == 0


@pytest.mark.asyncio
async def test_trigger_gap_backfill_no_gaps(db_session: AsyncSession):
    """Test backfill trigger with no gaps."""
    sync_state = DataSyncState(
        exchange="binance",
        symbol="BTC/USDT",
        timeframe="1h",
        market_id=1,
        is_auto_syncing=True,
    )
    db_session.add(sync_state)
    await db_session.commit()

    result = await _trigger_gap_backfill(db_session, sync_state, [])
    assert result == 0