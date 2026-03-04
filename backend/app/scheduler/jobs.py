"""Scheduled jobs for data synchronization.

This module defines the actual tasks that will be scheduled by the scheduler.
"""
import asyncio
import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import SessionLocal
from app.models.sync_state import DataSyncState, SyncStatus
from app.models.market import OHLCV, Market
from app.services.exchange import ExchangeService, MarketDataService, MarketService
from app.services.sync_state_service import SyncStateService

logger = logging.getLogger(__name__)

# Concurrency control for exchange API calls
# Limits the number of concurrent sync operations to avoid rate limiting
MAX_CONCURRENT_SYNCS = settings.MAX_CONCURRENT_SYNCS
_sync_semaphore = asyncio.Semaphore(MAX_CONCURRENT_SYNCS)

# Exchange service cache to reuse connections across jobs
_exchange_services: dict[str, ExchangeService] = {}
_exchange_lock = asyncio.Lock()

# Job timeout (seconds)
JOB_TIMEOUT = 300  # 5 minutes

# Job statistics storage (in Redis)
JOB_STATS_PREFIX = "job_stats"


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
    Includes timeout control and automatic retry on failure.
    """

    job_id = "auto_sync_ohlcv"
    logger.info("Starting auto-sync OHLCV job")

    # Record job start time
    job_start = datetime.now(timezone.utc)

    try:
        async with asyncio.timeout(JOB_TIMEOUT):
            async with SessionLocal() as session:
                # Use SyncStateService for better encapsulation
                sync_service = SyncStateService(session)

                # Get all idle states with auto-syncing enabled
                sync_states = await sync_service.get_idle_states(limit=1000)

                if not sync_states:
                    logger.debug("No sync states with auto-syncing enabled")
                    await _update_job_stats(job_id, job_start, successful=True)
                    return

                logger.info(f"Found {len(sync_states)} sync states with auto-syncing enabled")

                # Process sync states concurrently with semaphore control
                tasks = [
                    _sync_single_market(session, sync_state, sync_service)
                    for sync_state in sync_states
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Count successes and failures
                successes = sum(1 for r in results if not isinstance(r, Exception))
                failures = sum(1 for r in results if isinstance(r, Exception))

                await session.commit()
                logger.info(f"Auto-sync OHLCV job completed: {successes} success, {failures} failed")

                # Update job statistics
                await _update_job_stats(job_id, job_start, successful=True, synced=successes, failed=failures)

    except asyncio.TimeoutError:
        logger.error(f"Auto-sync OHLCV job timed out after {JOB_TIMEOUT} seconds")
        await _update_job_stats(job_id, job_start, successful=False, error="timeout")
    except Exception:
        logger.exception("Auto-sync OHLCV job failed")
        await _update_job_stats(job_id, job_start, successful=False, error="exception")
        raise


async def _sync_single_market(
    session: AsyncSession,
    sync_state: DataSyncState,
    sync_service: Optional[SyncStateService] = None,
) -> None:
    """Sync OHLCV data for a single market.

    Args:
        session: Database session
        sync_state: Sync state record for the market
        sync_service: Optional SyncStateService instance

    This function is protected by a semaphore to limit concurrent API calls.
    Includes retry logic for transient failures.
    """
    if sync_service is None:
        sync_service = SyncStateService(session)

    async with _sync_semaphore:
        logger.debug(
            f"Syncing {sync_state.exchange}/{sync_state.symbol}/{sync_state.timeframe} "
            f"from {sync_state.last_sync_time}"
        )

        # Update sync status to syncing
        await sync_service.set_status(
            sync_state.market_id,
            sync_state.timeframe,
            SyncStatus.SYNCING,
        )

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

                # Fetch data using MarketDataService with retry logic
                rows_fetched = await _fetch_with_retry(
                    exchange_service,
                    session,
                    sync_state,
                    market_id,
                    start_time,
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
                        await sync_service.update_sync_time(
                            market_id, sync_state.timeframe, last_time
                        )
                    else:
                        await sync_service.update_sync_time(
                            market_id, sync_state.timeframe, datetime.now(timezone.utc)
                        )

                # Update sync status to idle
                await sync_service.set_status(
                    market_id,
                    sync_state.timeframe,
                    SyncStatus.IDLE,
                )

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
            await sync_service.set_status(
                market_id,
                sync_state.timeframe,
                SyncStatus.ERROR,
                error=str(e),
            )


async def _fetch_with_retry(
    exchange_service: ExchangeService,
    session: AsyncSession,
    sync_state: DataSyncState,
    market_id: int,
    start_time: datetime,
    max_retries: int = 2,
) -> int:
    """Fetch OHLCV data with retry logic.

    Args:
        exchange_service: Exchange service instance
        session: Database session
        sync_state: Sync state record
        market_id: Market ID
        start_time: Start time for fetching
        max_retries: Maximum number of retries

    Returns:
        Number of rows fetched

    Retries on transient errors (network issues, rate limits).
    """
    market_data_service = MarketDataService(exchange_service, session)
    last_error = None

    for attempt in range(max_retries + 1):
        try:
            return await market_data_service.fetch_ohlcv_history(
                symbol=sync_state.symbol,
                market_id=market_id,
                timeframe=sync_state.timeframe,
                start_time=start_time,
                end_time=None,
                limit=500,
            )
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                # Exponential backoff
                wait_time = 2 ** attempt
                logger.warning(
                    f"Fetch attempt {attempt + 1} failed for {sync_state.symbol}, "
                    f"retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)
            else:
                # Last attempt failed, raise the error
                raise

    raise last_error


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
    Includes timeout control and job statistics.
    """

    job_id = "sync_markets_metadata"
    logger.info("Starting market metadata sync job")

    job_start = datetime.now(timezone.utc)

    try:
        async with asyncio.timeout(JOB_TIMEOUT):
            async with SessionLocal() as session:
                # Get list of exchanges from config
                exchanges = settings.EXCHANGES

                total_synced = 0
                for exchange_id in exchanges:
                    exchange_service = await _get_exchange_service(exchange_id)

                    try:
                        market_service = MarketService(exchange_service, session)
                        synced = await market_service.sync_markets(
                            quote_allowlist=["USDT"],  # Only sync USDT pairs
                        )
                        logger.info(f"Synced {synced} markets from {exchange_id}")
                        total_synced += synced
                    except Exception as e:
                        logger.exception(f"Failed to sync markets from {exchange_id}: {e}")

                await session.commit()
                logger.info(f"Market metadata sync job completed: {total_synced} markets synced")

                await _update_job_stats(job_id, job_start, successful=True, synced=total_synced)

    except asyncio.TimeoutError:
        logger.error(f"Market metadata sync job timed out after {JOB_TIMEOUT} seconds")
        await _update_job_stats(job_id, job_start, successful=False, error="timeout")
    except Exception:
        logger.exception("Market metadata sync job failed")
        await _update_job_stats(job_id, job_start, successful=False, error="exception")
        raise


async def check_backfill_gaps():
    """Check for gaps in OHLCV data and trigger backfill if needed.

    This job runs at regular intervals (configured by BACKFILL_CHECK_INTERVAL_HOURS)
    and checks for gaps in the OHLCV data. If gaps are found, it triggers
    backfill jobs to fill the missing data.
    """

    job_id = "check_backfill_gaps"
    logger.info("Starting backfill gap check job")

    job_start = datetime.now(timezone.utc)

    try:
        async with asyncio.timeout(JOB_TIMEOUT):
            async with SessionLocal() as session:
                sync_service = SyncStateService(session)

                # Get all auto-syncing states
                sync_states = await sync_service.list_auto_syncing(limit=1000)

                gaps_found = 0
                gaps_backfilled = 0
                for sync_state in sync_states:
                    # Check for gaps in the data
                    gaps = await _detect_gaps(session, sync_state)
                    if gaps:
                        gaps_found += len(gaps)
                        logger.info(
                            f"Found {len(gaps)} gaps for {sync_state.symbol}/{sync_state.timeframe}"
                        )
                        # Trigger backfill for gaps
                        backfilled = await _trigger_gap_backfill(
                            session, sync_state, gaps
                        )
                        gaps_backfilled += backfilled

                await session.commit()
                logger.info(
                    f"Backfill gap check job completed: {gaps_found} gaps found, "
                    f"{gaps_backfilled} backfills triggered"
                )

                await _update_job_stats(
                    job_id, job_start, successful=True, gaps=gaps_found
                )

    except asyncio.TimeoutError:
        logger.error(f"Backfill gap check job timed out after {JOB_TIMEOUT} seconds")
        await _update_job_stats(job_id, job_start, successful=False, error="timeout")
    except Exception:
        logger.exception("Backfill gap check job failed")
        await _update_job_stats(job_id, job_start, successful=False, error="exception")
        raise


async def _detect_gaps(session: AsyncSession, sync_state: DataSyncState) -> list[dict]:
    """Detect gaps in OHLCV data for a market/timeframe.

    Args:
        session: Database session
        sync_state: Sync state record

    Returns:
        List of gap dictionaries
    """
    # Get the last 100 candles to check for gaps
    result = await session.execute(
        select(OHLCV)
        .where(
            OHLCV.market_id == sync_state.market_id,
            OHLCV.timeframe == sync_state.timeframe,
        )
        .order_by(OHLCV.time.desc())
        .limit(100)
    )
    candles = result.scalars().all()

    if len(candles) < 2:
        return []

    # Determine expected interval based on timeframe
    timeframe_seconds = {
        "1m": 60,
        "3m": 180,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1h": 3600,
        "2h": 7200,
        "4h": 14400,
        "6h": 21600,
        "8h": 28800,
        "12h": 43200,
        "1d": 86400,
        "3d": 259200,
        "1w": 604800,
    }.get(sync_state.timeframe, 3600)  # Default to 1h

    # Check for gaps between consecutive candles
    gaps = []
    for i in range(len(candles) - 1):
        time_diff = (candles[i].time - candles[i + 1].time).total_seconds()
        # Allow 10% tolerance for time differences
        if time_diff > timeframe_seconds * 1.1:
            missing_candles = int(time_diff / timeframe_seconds) - 1
            gaps.append({
                "start": candles[i + 1].time,
                "end": candles[i].time,
                "missing_candles": missing_candles,
            })

    return gaps


async def _trigger_gap_backfill(
    session: AsyncSession,
    sync_state: DataSyncState,
    gaps: list[dict],
) -> int:
    """Trigger backfill for detected gaps.

    Args:
        session: Database session
        sync_state: Sync state record
        gaps: List of gap dictionaries

    Returns:
        Number of gaps that were successfully triggered for backfill

    Gap backfill strategy:
    - Small gaps (<= 50 missing candles): Backfill immediately
    - Large gaps (> 50 missing candles): Log warning, skip auto-backfill
    """
    if not gaps:
        return 0

    # Get exchange service
    try:
        exchange_service = await _get_exchange_service(sync_state.exchange)
    except Exception as e:
        logger.error(
            f"Failed to get exchange service for {sync_state.exchange}: {e}"
        )
        return 0

    market_data_service = MarketDataService(exchange_service, session)
    backfilled_count = 0

    for gap in gaps:
        missing_candles = gap.get("missing_candles", 0)

        # Skip large gaps - they may need manual intervention
        if missing_candles > 50:
            logger.warning(
                f"Large gap detected for {sync_state.symbol}/{sync_state.timeframe}: "
                f"{missing_candles} missing candles from {gap['start']} to {gap['end']}. "
                "Skipping auto-backfill - consider manual backfill."
            )
            continue

        try:
            # Fetch data for the gap period
            rows_fetched = await market_data_service.fetch_ohlcv_history(
                symbol=sync_state.symbol,
                market_id=sync_state.market_id,
                timeframe=sync_state.timeframe,
                start_time=gap["start"],
                end_time=gap["end"],
                limit=500,
            )
            backfilled_count += 1
            logger.info(
                f"Backfilled gap for {sync_state.symbol}/{sync_state.timeframe}: "
                f"{rows_fetched} rows from {gap['start']} to {gap['end']}"
            )
        except Exception as e:
            logger.error(
                f"Failed to backfill gap for {sync_state.symbol}/{sync_state.timeframe}: {e}"
            )

    return backfilled_count


async def _update_job_stats(
    job_id: str,
    job_start: datetime,
    successful: bool,
    synced: int = 0,
    failed: int = 0,
    gaps: int = 0,
    error: Optional[str] = None,
) -> None:
    """Update job statistics in Redis.

    Args:
        job_id: Job identifier
        job_start: Job start time
        successful: Whether the job succeeded
        synced: Number of synced items
        failed: Number of failed items
        gaps: Number of gaps found
        error: Error message if failed
    """
    from app.core.redis import redis_client

    job_end = datetime.now(timezone.utc)

    # Get existing stats
    stats_key = f"{JOB_STATS_PREFIX}:{job_id}"
    existing = await redis_client.get(stats_key)

    if existing:
        stats = json.loads(existing)
    else:
        stats = {
            "total_runs": 0,
            "successful_runs": 0,
            "failed_runs": 0,
            "total_synced": 0,
            "total_failed": 0,
            "total_gaps": 0,
            "last_run_time": None,
            "last_error": None,
        }

    # Update stats
    stats["total_runs"] += 1
    stats["last_run_time"] = job_end.isoformat()

    if successful:
        stats["successful_runs"] += 1
        stats["total_synced"] += synced
        stats["total_failed"] += failed
        stats["total_gaps"] += gaps
        stats["last_error"] = None
    else:
        stats["failed_runs"] += 1
        stats["last_error"] = error

    # Store back in Redis with TTL
    await redis_client.setex(stats_key, 86400, json.dumps(stats))  # 24 hours TTL


async def get_job_stats(job_id: str) -> Optional[dict]:
    """Get job statistics from Redis.

    Args:
        job_id: Job identifier

    Returns:
        Job statistics dictionary, or None if not found
    """
    from app.core.redis import redis_client

    stats_key = f"{JOB_STATS_PREFIX}:{job_id}"
    stats = await redis_client.get(stats_key)

    if stats:
        return json.loads(stats)
    return None


async def get_all_job_stats() -> dict[str, dict]:
    """Get statistics for all jobs.

    Returns:
        Dictionary mapping job IDs to their statistics
    """

    job_ids = ["auto_sync_ohlcv", "sync_markets_metadata", "check_backfill_gaps"]
    stats = {}

    for job_id in job_ids:
        job_stats = await get_job_stats(job_id)
        if job_stats:
            stats[job_id] = job_stats

    return stats


async def get_exchange_service_count() -> int:
    """Get the number of cached exchange services.

    Returns:
        Number of cached exchange services
    """
    async with _exchange_lock:
        return len(_exchange_services)