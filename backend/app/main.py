from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, status, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import engine, get_db
from app.core.redis import redis_client
import logging
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
        
    except Exception:
        logger.exception("Startup check failed")
        await redis_client.close()
        await engine.dispose()
        raise
    
    yield
    
    logger.info("Shutting down...")
    await redis_client.close()
    await engine.dispose()
    logger.info("Shutdown complete.")

app = FastAPI(
    title="Kurisu Trading Bot",
    lifespan=lifespan
)

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
