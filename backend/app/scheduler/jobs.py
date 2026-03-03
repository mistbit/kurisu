"""Scheduled jobs for data synchronization.

This module defines the actual tasks that will be scheduled by the scheduler.
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.models.sync_state import DataSyncState, SyncStatus
from app.models.market import OHLCV, Market
from app.services.exchange import ExchangeService, MarketDataService, MarketService

logger = logging.getLogger(__name__)

# Concurrency control for exchange API calls
# Limits the number of concurrent sync operations to avoid rate limiting
MAX_CONCURRENT_SYNCS = 3
_sync_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNCS)

# Exchange service cache to reuse connections across jobs
_exchange_services: dict[str, ExchangeService] = {}
_exchange_lock = asyncio.Lock()


async def auto_sync_ohlcv():
    """Auto-sync OHLCV data for all markets with auto-syncing enabled.

    This job runs at regular intervals (configured by AUTO_SYNC_INTERVAL_MINUTES)
    and fetches the latest OHLCV data from exchanges for all markets where
    is_auto_syncing is True in the data_sync_state table.

    For each sync state record, the job:
    1. Fetches OHLCV data from the last_sync_time
    2. Updates the database with new data
    3. Updates the last_sync_time

    Uses concurrent execution with semaphore to avoid API rate limiting.
    """
    logger.info("Starting auto-sync OHLCV job")

    async with SessionLocal() as session:
        try:
            # Get all sync states with auto-syncing enabled
            result = await session.execute(
                select(DataSyncState).where(
                    DataSyncState.is_auto_syncing,
                    DataSyncState.sync_status == SyncStatus.IDLE,
                )
            )
            sync_states = result.scalars().all()

            if not sync_states:
                logger.debug("No sync states with auto-syncing enabled")
                return

            logger.info(f"Found {len(sync_states)} sync states with auto-syncing enabled")

            # Process sync states concurrently with semaphore control
            tasks = [
                _sync_single_market(session, sync_state)
                for sync_state in sync_states
            ]
            await asyncio.gather(*tasks, return_exceptions=True)

            await session.commit()
            logger.info("Auto-sync OHLCV job completed")

        except Exception:
            logger.exception("Auto-sync OHLCV job failed")
            await session.rollback()
            raise


async def _sync_single_market(session: AsyncSession, sync_state: DataSyncState) -> None:
    """Sync OHLCV data for a single market.

    Args:
        session: Database session
        sync_state: Sync state record for the market

    This function is protected by a semaphore to limit concurrent API calls.
    """
    async with _sync_semaphore:
        logger.debug(
            f"Syncing {sync_state.exchange}/{sync_state.symbol}/{sync_state.timeframe} "
            f"from {sync_state.last_sync_time}"
        )

        # Update sync status to syncing
        sync_state.sync_status = SyncStatus.SYNCING
        sync_state.error_message = None
        sync_state.last_error_time = None
        await session.flush()

        try:
            # Get market_id from sync_state (already populated)
            market_id = sync_state.market_id
            if not market_id:
                # Fallback: fetch market_id if not set
                result = await session.execute(
                    select(Market.id).where(
                        Market.exchange == sync_state.exchange,
                        Market.symbol == sync_state.symbol,
                    )
                )
                market_id = result.scalar_one_or_none()
                if market_id:
                    sync_state.market_id = market_id
                    await session.flush()
                else:
                    raise ValueError(f"Market not found for {sync_state.exchange}/{sync_state.symbol}")

            # Get or create cached exchange service
            exchange_service = await _get_exchange_service(sync_state.exchange)

            try:
                # Determine start time (last_sync_time or 24 hours ago if first sync)
                if sync_state.last_sync_time:
                    # Add 1 second to avoid duplicate data
                    start_time = sync_state.last_sync_time + timedelta(seconds=1)
                else:
                    start_time = datetime.now(timezone.utc) - timedelta(hours=24)

                # Fetch data using MarketDataService
                market_data_service = MarketDataService(exchange_service, session)
                rows_fetched = await market_data_service.fetch_ohlcv_history(
                    symbol=sync_state.symbol,
                    market_id=market_id,
                    timeframe=sync_state.timeframe,
                    start_time=start_time,
                    end_time=None,  # Get up to current time
                    limit=500,
                )

                # Update last_sync_time to current time (last candle time would be better, but we use current for simplicity)
                if rows_fetched > 0:
                    # Get the last synced time from the database
                    result = await session.execute(
                        select(OHLCV.time)
                        .where(OHLCV.market_id == market_id, OHLCV.timeframe == sync_state.timeframe)
                        .order_by(OHLCV.time.desc())
                        .limit(1)
                    )
                    last_time = result.scalar_one_or_none()
                    if last_time:
                        sync_state.last_sync_time = last_time
                    else:
                        sync_state.last_sync_time = datetime.now(timezone.utc)

                # Update sync status to idle
                sync_state.sync_status = SyncStatus.IDLE
                await session.flush()

                logger.debug(
                    f"Synced {rows_fetched} rows for {sync_state.exchange}/{sync_state.symbol}/{sync_state.timeframe}"
                )

            finally:
                # Don't close exchange service here, it's cached
                pass

        except Exception as e:
            logger.exception(
                f"Failed to sync market {sync_state.exchange}/{sync_state.symbol}/{sync_state.timeframe}: {e}"
            )
            # Update sync status to error
            sync_state.sync_status = SyncStatus.ERROR
            sync_state.error_message = str(e)[:500]  # Truncate to fit in column
            sync_state.last_error_time = datetime.now(timezone.utc)
            await session.flush()


async def _get_exchange_service(exchange_id: str) -> ExchangeService:
    """Get or create a cached exchange service.

    Args:
        exchange_id: Exchange identifier (e.g., "binance")

    Returns:
        Exchange service instance

    This caches exchange services to avoid creating new connections for each sync operation.
    """
    async with _exchange_lock:
        if exchange_id not in _exchange_services:
            service = ExchangeService(exchange_id)
            await service.initialize()
            _exchange_services[exchange_id] = service
            logger.debug(f"Created new ExchangeService for {exchange_id}")
        return _exchange_services[exchange_id]


async def close_exchange_services():
    """Close all cached exchange services.

    This should be called during application shutdown.
    """
    async with _exchange_lock:
        for exchange_id, service in _exchange_services.items():
            try:
                await service.close()
                logger.debug(f"Closed ExchangeService for {exchange_id}")
            except Exception:
                logger.exception(f"Failed to close ExchangeService for {exchange_id}")
        _exchange_services.clear()


async def sync_markets_metadata():
    """Sync market metadata from exchanges.

    This job runs daily (configured by MARKET_SYNC_HOUR) and syncs
    the market metadata (trading pairs, precision, etc.) from exchanges.
    """
    logger.info("Starting market metadata sync job")

    async with SessionLocal() as session:
        try:
            # Get list of exchanges from sync states (or use configured list)
            exchanges = ["binance"]  # TODO: Read from config or sync_states

            for exchange_id in exchanges:
                exchange_service = await _get_exchange_service(exchange_id)

                try:
                    market_service = MarketService(exchange_service, session)
                    synced = await market_service.sync_markets(
                        quote_allowlist=["USDT"],  # Only sync USDT pairs
                    )
                    logger.info(f"Synced {synced} markets from {exchange_id}")
                except Exception as e:
                    logger.exception(f"Failed to sync markets from {exchange_id}: {e}")

            await session.commit()
            logger.info("Market metadata sync job completed")

        except Exception:
            logger.exception("Market metadata sync job failed")
            await session.rollback()
            raise


async def check_backfill_gaps():
    """Check for gaps in OHLCV data and trigger backfill if needed.

    This job runs at regular intervals (configured by BACKFILL_CHECK_INTERVAL_HOURS)
    and checks for gaps in the OHLCV data. If gaps are found, it triggers
    backfill jobs to fill the missing data.
    """
    logger.info("Starting backfill gap check job")

    # TODO: Implement gap detection and backfill triggering
    # This is a placeholder for future implementation

    logger.debug("Backfill gap check job completed (not yet implemented)")