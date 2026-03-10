import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, status
from sqlalchemy import asc, desc, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import engine, get_db
from app.core.redis import redis_client
from app.models.market import Market, OHLCV
from app.services.exchange import ExchangeService, MarketService
from app.scheduler import start_scheduler, shutdown_scheduler
from app.api.v1 import sync, auth
from app.api.v1.websocket import router as websocket_router
from app.api.v1.backtest import router as backtest_router
from app.services.ohlcv_stream import ohlcv_stream_service

logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        logger.info("Performing startup checks...")

        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection established.")

        await redis_client.ping()
        logger.info("Redis connection established.")

        # Start the scheduler if enabled
        if settings.SCHEDULER_ENABLED:
            logger.info("Starting scheduler...")
            start_scheduler()
            logger.info("Scheduler started.")
        else:
            logger.info("Scheduler disabled by configuration.")

        # Start OHLCV stream service
        logger.info("Starting OHLCV stream service...")
        await ohlcv_stream_service.start()
        logger.info("OHLCV stream service started.")

    except Exception:
        logger.exception("Startup check failed")
        await redis_client.close()
        await engine.dispose()
        raise

    yield

    logger.info("Shutting down...")
    # Stop OHLCV stream service
    await ohlcv_stream_service.stop()
    # Shutdown scheduler if running
    shutdown_scheduler()
    await redis_client.close()
    await engine.dispose()
    logger.info("Shutdown complete.")

app = FastAPI(
    title="Kurisu Trading Bot",
    version="0.1.0",
    lifespan=lifespan
)

# Include API routers
app.include_router(sync.router, prefix="/api/v1")
app.include_router(auth.router, prefix="/api/v1")
app.include_router(backtest_router, prefix="/api/v1")
app.include_router(websocket_router)

@app.get("/health", status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_db)):
    """
    Health check endpoint to verify DB and Redis connections.
    """
    health_status = {
        "status": "ok",
        "database": "unknown",
        "redis": "unknown"
    }
    
    # Check Database
    try:
        await db.execute(text("SELECT 1"))
        health_status["database"] = "connected"
    except Exception as e:
        health_status["database"] = "error"
        health_status["status"] = "error"
        logger.error(f"Health check DB failed: {e}")

    # Check Redis
    try:
        await redis_client.ping()
        health_status["redis"] = "connected"
    except Exception as e:
        health_status["redis"] = "error"
        health_status["status"] = "error"
        logger.error(f"Health check Redis failed: {e}")
    
    if health_status["status"] == "error":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health_status
        )
        
    return health_status


@app.get("/api/v1/health", status_code=status.HTTP_200_OK)
async def health_check_v1(db: AsyncSession = Depends(get_db)):
    return await health_check(db)


@app.get("/api/v1/version", status_code=status.HTTP_200_OK)
async def get_version():
    return {"version": app.version}


@app.get("/api/v1/markets", status_code=status.HTTP_200_OK)
async def list_markets(
    exchange: Optional[str] = None,
    symbol: Optional[str] = None,
    active: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 500))
    offset = max(0, offset)
    query = select(Market)
    if exchange:
        query = query.where(Market.exchange == exchange)
    if symbol:
        query = query.where(Market.symbol == symbol)
    if active is not None:
        query = query.where(Market.active == active)
    query = query.order_by(Market.id).limit(limit).offset(offset)
    result = await db.execute(query)
    markets = result.scalars().all()
    return [
        {
            "id": market.id,
            "exchange": market.exchange,
            "symbol": market.symbol,
            "base_asset": market.base_asset,
            "quote_asset": market.quote_asset,
            "active": market.active,
            "meta": market.meta,
            "exchange_symbol": market.exchange_symbol,
            "price_precision": market.price_precision,
            "amount_precision": market.amount_precision,
        }
        for market in markets
    ]


@app.get("/api/v1/markets/{market_id}", status_code=status.HTTP_200_OK)
async def get_market(market_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Market).where(Market.id == market_id))
    market = result.scalar_one_or_none()
    if not market:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Market not found")
    return {
        "id": market.id,
        "exchange": market.exchange,
        "symbol": market.symbol,
        "base_asset": market.base_asset,
        "quote_asset": market.quote_asset,
        "active": market.active,
        "meta": market.meta,
        "exchange_symbol": market.exchange_symbol,
        "price_precision": market.price_precision,
        "amount_precision": market.amount_precision,
    }


async def get_exchange_service(
    exchange_id: str = "binance",
) -> AsyncGenerator[ExchangeService, None]:
    service = ExchangeService(exchange_id)
    await service.initialize()
    try:
        yield service
    finally:
        await service.close()


@app.post("/api/v1/markets/sync", status_code=status.HTTP_200_OK)
async def sync_markets(
    quote_allowlist: Optional[list[str]] = None,
    quote_denylist: Optional[list[str]] = None,
    exchange_service: ExchangeService = Depends(get_exchange_service),
    db: AsyncSession = Depends(get_db),
):
    market_service = MarketService(exchange_service, db)
    synced = await market_service.sync_markets(
        quote_allowlist=quote_allowlist, quote_denylist=quote_denylist
    )
    return {"synced": synced}


@app.get("/api/v1/data/ohlcv", status_code=status.HTTP_200_OK)
async def get_ohlcv(
    market_id: int,
    timeframe: str,
    start_time: datetime,
    end_time: Optional[datetime] = None,
    limit: int = 500,
    order: str = "asc",
    db: AsyncSession = Depends(get_db),
):
    limit = max(1, min(limit, 2000))
    ordering = asc if order == "asc" else desc if order == "desc" else None
    if ordering is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid order")
    query = (
        select(OHLCV)
        .where(OHLCV.market_id == market_id, OHLCV.timeframe == timeframe)
        .where(OHLCV.time >= _ensure_utc(start_time))
    )
    if end_time is not None:
        query = query.where(OHLCV.time <= _ensure_utc(end_time))
    query = query.order_by(ordering(OHLCV.time)).limit(limit)
    result = await db.execute(query)
    rows = result.scalars().all()
    return [
        [
            _to_ms(item.time),
            float(item.open),
            float(item.high),
            float(item.low),
            float(item.close),
            float(item.volume),
        ]
        for item in rows
    ]


def _ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _to_ms(value: datetime) -> int:
    return int(_ensure_utc(value).timestamp() * 1000)
