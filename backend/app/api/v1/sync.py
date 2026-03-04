"""API routes for sync state management and scheduler control."""
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from pydantic import BaseModel, Field, field_validator

from app.core.database import get_db
from app.core.redis import redis_client
from app.scheduler import get_scheduler, get_all_job_stats, get_active_connections
from app.services.sync_state_service import SyncStateService
from app.services.exchange import MarketDataService
from app.scheduler.jobs import _get_exchange_service
from sqlalchemy.ext.asyncio import AsyncSession
from apscheduler.jobstores.redis import RedisJobStore
from apscheduler.jobstores.memory import MemoryJobStore

logger = logging.getLogger(__name__)

router = APIRouter(tags=["sync", "scheduler"])


# ============ Constants ============

# Threshold for considering a task as "large" (needs background processing)
LARGE_TASK_THRESHOLD = 10  # market-timeframe combinations

# Task status storage
TASK_STATUS_PREFIX = "backfill_task"


# ============ Pydantic Models ============

class SyncStateResponse(BaseModel):
    """Sync state response model."""

    id: int
    market_id: Optional[int] = None
    exchange: str
    symbol: str
    timeframe: str
    sync_status: str
    last_sync_time: Optional[datetime] = None
    backfill_completed_until: Optional[datetime] = None
    is_auto_syncing: bool
    error_message: Optional[str] = None
    last_error_time: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class SyncStateListResponse(BaseModel):
    """Sync state list response model."""

    items: list[SyncStateResponse]
    total: int
    limit: int
    offset: int


class BackfillRequest(BaseModel):
    """Backfill request model."""

    market_ids: Optional[list[int]] = Field(None, description="List of market IDs to backfill")
    timeframes: list[str] = Field(..., description="List of timeframes to backfill")
    start_time: Optional[datetime] = Field(None, description="Start time for backfill")
    end_time: Optional[datetime] = Field(None, description="End time for backfill")
    symbol_pattern: Optional[str] = Field(None, description="Symbol pattern (e.g., BTC/*)")
    force: bool = Field(False, description="Force overwrite existing data")

    @field_validator("timeframes")
    @classmethod
    def validate_timeframes(cls, v):
        """Validate timeframes."""
        valid_timeframes = {
            "1m", "3m", "5m", "15m", "30m",
            "1h", "2h", "4h", "6h", "8h", "12h",
            "1d", "3d", "1w", "1M"
        }
        for tf in v:
            if tf not in valid_timeframes:
                raise ValueError(f"Invalid timeframe: {tf}")
        return v


class BackfillResponse(BaseModel):
    """Backfill response model."""

    task_id: str
    status: str
    estimated_markets: int
    estimated_timeframes: int
    message: str


class BackfillTaskStatus(BaseModel):
    """Backfill task status model."""

    task_id: str
    status: str  # pending, running, completed, failed
    total_combinations: int
    completed_combinations: int
    failed_combinations: int
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None


class AutoSyncRequest(BaseModel):
    """Auto-sync control request model."""

    market_id: int
    timeframes: list[str]
    enabled: bool


class AutoSyncResponse(BaseModel):
    """Auto-sync response model."""

    updated: int
    message: str


class JobStats(BaseModel):
    """Job statistics model."""

    id: str
    name: str
    next_run_time: Optional[datetime] = None
    last_run_time: Optional[datetime] = None
    stats: dict


class SchedulerStatusResponse(BaseModel):
    """Scheduler status response model."""

    running: bool
    job_store: str
    jobs: list[JobStats]
    active_connections: int


# ============ Sync State Endpoints ============


# ============ Background Task Functions ============


async def _run_backfill_task(
    task_id: str,
    backfill_items: list[dict],
    start_time: Optional[datetime],
    end_time: Optional[datetime],
) -> None:
    """Execute backfill task in the background.

    Args:
        task_id: Unique task identifier
        backfill_items: List of items to backfill, each containing:
            - market_id: Market ID
            - symbol: Trading symbol
            - exchange: Exchange name
            - timeframe: Timeframe string
        start_time: Start time for backfill
        end_time: End time for backfill
    """
    from app.core.database import SessionLocal

    # Initialize task status
    task_key = f"{TASK_STATUS_PREFIX}:{task_id}"
    task_status = {
        "task_id": task_id,
        "status": "running",
        "total_combinations": len(backfill_items),
        "completed_combinations": 0,
        "failed_combinations": 0,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "error": None,
    }
    await redis_client.setex(task_key, 86400, json.dumps(task_status))  # 24h TTL

    try:
        async with SessionLocal() as session:
            # Group items by exchange to reuse connections
            exchanges_cache: dict[str, any] = {}

            for item in backfill_items:
                try:
                    # Get or create exchange service
                    exchange = item["exchange"]
                    if exchange not in exchanges_cache:
                        exchanges_cache[exchange] = await _get_exchange_service(exchange)
                    exchange_service = exchanges_cache[exchange]

                    # Create market data service
                    market_data_service = MarketDataService(exchange_service, session)

                    # Fetch and upsert OHLCV data
                    rows_fetched = await market_data_service.fetch_ohlcv_history(
                        symbol=item["symbol"],
                        market_id=item["market_id"],
                        timeframe=item["timeframe"],
                        start_time=start_time or datetime.now(timezone.utc) - timedelta(days=30),
                        end_time=end_time,
                        limit=500,
                    )

                    # Update task status
                    task_status["completed_combinations"] += 1
                    await redis_client.setex(task_key, 86400, json.dumps(task_status))

                    logger.info(
                        f"Backfill task {task_id}: completed {item['symbol']}/{item['timeframe']}, "
                        f"{rows_fetched} rows fetched"
                    )

                except Exception as e:
                    task_status["failed_combinations"] += 1
                    logger.error(
                        f"Backfill task {task_id}: failed {item['symbol']}/{item['timeframe']}: {e}"
                    )
                    await redis_client.setex(task_key, 86400, json.dumps(task_status))

            # Mark task as completed
            task_status["status"] = "completed"
            task_status["completed_at"] = datetime.now(timezone.utc).isoformat()
            await redis_client.setex(task_key, 86400, json.dumps(task_status))

    except Exception as e:
        task_status["status"] = "failed"
        task_status["error"] = str(e)
        task_status["completed_at"] = datetime.now(timezone.utc).isoformat()
        await redis_client.setex(task_key, 86400, json.dumps(task_status))
        logger.exception(f"Backfill task {task_id} failed: {e}")

@router.get("/data/sync_state", response_model=SyncStateListResponse)
async def list_sync_states(
    market_id: Optional[int] = None,
    timeframe: Optional[str] = None,
    sync_status: Optional[str] = None,
    has_errors: bool = False,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    """List sync states with optional filtering.

    Query parameters:
    - market_id: Filter by market ID
    - timeframe: Filter by timeframe
    - sync_status: Filter by sync status (idle, syncing, error)
    - has_errors: Only return states with errors
    - limit: Maximum number of results (default: 100)
    - offset: Pagination offset (default: 0)
    """
    sync_service = SyncStateService(db)

    # Apply filters
    if has_errors:
        states = await sync_service.get_error_states()
        total = len(states)
        items = states[offset:offset + limit]
    elif sync_status:
        states = await sync_service.list_auto_syncing(status=sync_status, limit=1000)
        total = len(states)
        items = states[offset:offset + limit]
    else:
        states = await sync_service.get_all_sync_states(limit=limit + 1, offset=offset)
        total = len(states) if len(states) <= limit else None
        items = states[:limit]

    # Additional filters
    if market_id:
        items = [s for s in items if s.market_id == market_id]
    if timeframe:
        items = [s for s in items if s.timeframe == timeframe]

    return SyncStateListResponse(
        items=[SyncStateResponse.model_validate(s) for s in items],
        total=total or len(items),
        limit=limit,
        offset=offset,
    )


@router.get("/data/sync_state/{sync_state_id}", response_model=SyncStateResponse)
async def get_sync_state(
    sync_state_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a specific sync state by ID."""
    sync_service = SyncStateService(db)
    sync_state = await sync_service.get_by_id(sync_state_id)

    if not sync_state:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Sync state with ID {sync_state_id} not found",
        )

    return SyncStateResponse.model_validate(sync_state)


@router.post("/data/backfill", response_model=BackfillResponse)
async def trigger_backfill(
    request: BackfillRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Trigger a backfill task for specified markets and timeframes.

    For small tasks (<= 10 market-timeframe combinations), the backfill runs synchronously.
    For larger tasks, a background task is queued and can be monitored via the task_id.
    """
    sync_service = SyncStateService(db)

    # Determine which markets to backfill
    markets_to_backfill = []
    if request.market_ids:
        for market_id in request.market_ids:
            for timeframe in request.timeframes:
                sync_state = await sync_service.get_by_market_timeframe(market_id, timeframe)
                if sync_state:
                    markets_to_backfill.append(sync_state)
    elif request.symbol_pattern:
        # Filter by symbol pattern (simplified implementation)
        all_states = await sync_service.get_all_sync_states(limit=1000)
        for state in all_states:
            if request.symbol_pattern in state.symbol and state.timeframe in request.timeframes:
                markets_to_backfill.append(state)

    if not markets_to_backfill:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No matching markets found for backfill",
        )

    # Generate task ID
    task_id = f"backfill_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"

    # Prepare backfill items
    backfill_items = [
        {
            "market_id": s.market_id,
            "symbol": s.symbol,
            "exchange": s.exchange,
            "timeframe": s.timeframe,
        }
        for s in markets_to_backfill
    ]

    estimated_timeframes = len(backfill_items)

    # Initialize task status in Redis
    task_key = f"{TASK_STATUS_PREFIX}:{task_id}"
    initial_status = {
        "task_id": task_id,
        "status": "pending",
        "total_combinations": estimated_timeframes,
        "completed_combinations": 0,
        "failed_combinations": 0,
        "started_at": None,
        "completed_at": None,
        "error": None,
    }
    await redis_client.setex(task_key, 86400, json.dumps(initial_status))

    # Queue background task
    background_tasks.add_task(
        _run_backfill_task,
        task_id,
        backfill_items,
        request.start_time,
        request.end_time,
    )

    logger.info(
        f"Queued backfill task {task_id} for {estimated_timeframes} combinations"
    )

    return BackfillResponse(
        task_id=task_id,
        status="queued",
        estimated_markets=len(set(s.market_id for s in markets_to_backfill)),
        estimated_timeframes=estimated_timeframes,
        message=f"Backfill task queued for {estimated_timeframes} combinations",
    )


@router.post("/data/auto_sync", response_model=AutoSyncResponse)
async def control_auto_sync(
    request: AutoSyncRequest,
    db: AsyncSession = Depends(get_db),
):
    """Enable or disable auto-syncing for a market and timeframes.

    Set enabled=true to enable auto-syncing, enabled=false to disable.
    """
    sync_service = SyncStateService(db)

    updated = 0
    for timeframe in request.timeframes:
        if request.enabled:
            await sync_service.enable_auto_sync(request.market_id, timeframe)
        else:
            await sync_service.disable_auto_sync(request.market_id, timeframe)
        updated += 1

    await db.commit()

    return AutoSyncResponse(
        updated=updated,
        message=f"Auto-sync {'enabled' if request.enabled else 'disabled'} for {updated} timeframes",
    )


# ============ Scheduler Endpoints ============

@router.get("/scheduler/status", response_model=SchedulerStatusResponse)
async def get_scheduler_status():
    """Get scheduler status and job statistics."""
    scheduler = get_scheduler()

    # Get job statistics from Redis
    all_stats = get_all_job_stats()

    # Determine job store type
    job_store = "memory"
    for jobstore_name, jobstore in scheduler._jobstores.items():
        if isinstance(jobstore, RedisJobStore):
            job_store = "redis"
            break

    # Build job list with statistics
    jobs = []
    for job in scheduler.get_jobs():
        job_id = job.id
        job_stats = all_stats.get(job_id, {})

        jobs.append(JobStats(
            id=job_id,
            name=job.name,
            next_run_time=job.next_run_time,
            last_run_time=job_stats.get("last_run_time"),
            stats=job_stats,
        ))

    return SchedulerStatusResponse(
        running=scheduler.running,
        job_store=job_store,
        jobs=jobs,
        active_connections=get_active_connections(),
    )


# ============ Backfill Task Status Endpoint ============

@router.get("/data/backfill/{task_id}", response_model=BackfillTaskStatus)
async def get_backfill_status(task_id: str):
    """Get the status of a backfill task.

    Args:
        task_id: The task ID returned from the backfill request

    Returns:
        Current status of the backfill task
    """
    task_key = f"{TASK_STATUS_PREFIX}:{task_id}"
    task_data = await redis_client.get(task_key)

    if not task_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Backfill task {task_id} not found or expired",
        )

    status_dict = json.loads(task_data)
    return BackfillTaskStatus(**status_dict)