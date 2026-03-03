"""APScheduler integration for background data sync tasks.

This module provides a centralized scheduler instance that can be used
to schedule and manage background tasks such as:
- Auto-syncing OHLCV data from exchanges
- Market metadata synchronization
- Backfill gap detection and repair
"""
import asyncio
import logging
from contextlib import contextmanager
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from app.core.config import settings

logger = logging.getLogger(__name__)

# Global scheduler instance
_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    """Get the global scheduler instance.

    Returns:
        The global AsyncIOScheduler instance.

    Raises:
        RuntimeError: If the scheduler has not been started.
    """
    global _scheduler
    if _scheduler is None:
        raise RuntimeError("Scheduler not initialized. Call start_scheduler() first.")
    return _scheduler


def start_scheduler() -> None:
    """Initialize and start the global scheduler.

    This should be called during application startup (e.g., in FastAPI lifespan).
    If the scheduler is already running, this is a no-op.

    The scheduler is configured with:
    - Redis job store for persistent job storage across restarts (with memory fallback)
    - AsyncIO executor for async task execution
    - Default job coalescing and misfire grace time settings
    """
    global _scheduler

    if _scheduler is not None and _scheduler.running:
        logger.info("Scheduler already running, skipping initialization.")
        return

    # Try Redis job store first, fall back to memory if Redis is unavailable
    jobstores = {}
    try:
        redis_jobstore = RedisJobStore(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            db=settings.REDIS_DB,
        )
        # Test Redis connection
        redis_jobstore.redis.ping()
        jobstores["default"] = redis_jobstore
        logger.info("Using Redis job store for scheduler")
    except Exception as e:
        logger.warning(f"Redis job store unavailable, using memory store: {e}")
        # Memory store (jobs are lost on restart)
        from apscheduler.jobstores.memory import MemoryJobStore
        jobstores["default"] = MemoryJobStore()

    # Configure executors
    executors = {
        "default": AsyncIOExecutor(),
    }

    # Create scheduler instance
    _scheduler = AsyncIOScheduler(
        jobstores=jobstores,
        executors=executors,
        job_defaults={
            # Coalesce runs if multiple executions are missed
            "coalesce": True,
            # Allow job to run up to 5 minutes after scheduled time
            "max_instances": 3,
            "misfire_grace_time": 300,
        },
        timezone="UTC",
    )

    # Register default jobs
    _register_default_jobs(_scheduler)

    try:
        _scheduler.start()
        logger.info("Scheduler started successfully.")
    except Exception:
        logger.exception("Failed to start scheduler")
        _scheduler = None
        raise


def _register_default_jobs(scheduler: AsyncIOScheduler) -> None:
    """Register default scheduled jobs.

    Args:
        scheduler: The scheduler instance to register jobs with
    """
    from app.scheduler import jobs

    # Auto-sync OHLCV job - runs every N minutes
    scheduler.add_job(
        jobs.auto_sync_ohlcv,
        "interval",
        minutes=settings.AUTO_SYNC_INTERVAL_MINUTES,
        id="auto_sync_ohlcv",
        name="Auto Sync OHLCV",
        replace_existing=True,
    )

    # Market metadata sync job - runs daily at specified hour
    scheduler.add_job(
        jobs.sync_markets_metadata,
        "cron",
        hour=settings.MARKET_SYNC_HOUR,
        minute=0,
        id="sync_markets_metadata",
        name="Sync Markets Metadata",
        replace_existing=True,
    )

    # Backfill gap check job - runs every N hours
    scheduler.add_job(
        jobs.check_backfill_gaps,
        "interval",
        hours=settings.BACKFILL_CHECK_INTERVAL_HOURS,
        id="check_backfill_gaps",
        name="Check Backfill Gaps",
        replace_existing=True,
    )

    logger.info("Registered default scheduled jobs")


def shutdown_scheduler() -> None:
    """Shutdown the global scheduler gracefully.

    This should be called during application shutdown (e.g., in FastAPI lifespan).
    If the scheduler is not running, this is a no-op.

    Also closes all cached exchange services.
    """
    global _scheduler

    # Close exchange services first
    from app.scheduler import jobs

    try:
        if hasattr(jobs, 'close_exchange_services'):
            loop = asyncio.get_event_loop()
            loop.run_until_complete(jobs.close_exchange_services())
    except Exception:
        logger.exception("Failed to close exchange services")

    if _scheduler is None:
        return

    if _scheduler.running:
        logger.info("Shutting down scheduler...")
        _scheduler.shutdown(wait=True)
        logger.info("Scheduler shut down successfully.")

    _scheduler = None


def get_job_stats(job_id: str) -> Optional[dict]:
    """Get statistics for a specific job.

    Args:
        job_id: Job identifier

    Returns:
        Job statistics, or None if not found
    """
    from app.scheduler import jobs

    loop = asyncio.get_event_loop()
    return loop.run_until_complete(jobs.get_job_stats(job_id))


def get_all_job_stats() -> dict[str, dict]:
    """Get statistics for all jobs.

    Returns:
        Dictionary mapping job IDs to their statistics
    """
    from app.scheduler import jobs

    loop = asyncio.get_event_loop()
    return loop.run_until_complete(jobs.get_all_job_stats())


def get_active_connections() -> int:
    """Get the number of active exchange connections.

    Returns:
        Number of cached exchange services
    """
    from app.scheduler import jobs

    loop = asyncio.get_event_loop()
    return loop.run_until_complete(jobs.get_exchange_service_count())


@contextmanager
def scheduler_context():
    """Context manager for scheduler lifecycle.

    Usage:
        with scheduler_context():
            # Application code that needs scheduler
            pass
        # Scheduler is automatically shut down
    """
    try:
        start_scheduler()
        yield
    finally:
        shutdown_scheduler()