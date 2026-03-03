"""Scheduler module for background data synchronization tasks."""
from .scheduler import (
    get_scheduler,
    start_scheduler,
    shutdown_scheduler,
    get_job_stats,
    get_all_job_stats,
    get_active_connections,
)
from .jobs import (
    auto_sync_ohlcv,
    sync_markets_metadata,
    check_backfill_gaps,
    close_exchange_services,
    get_exchange_service_count,
)

__all__ = [
    "get_scheduler",
    "start_scheduler",
    "shutdown_scheduler",
    "auto_sync_ohlcv",
    "sync_markets_metadata",
    "check_backfill_gaps",
    "close_exchange_services",
    "get_job_stats",
    "get_all_job_stats",
    "get_active_connections",
    "get_exchange_service_count",
]