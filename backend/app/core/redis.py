import redis.asyncio as redis

from app.core.config import settings

redis_client = redis.from_url(
    str(settings.REDIS_URL),
    encoding="utf-8",
    decode_responses=True,
    socket_connect_timeout=settings.REDIS_SOCKET_CONNECT_TIMEOUT,
    socket_timeout=settings.REDIS_SOCKET_TIMEOUT,
)
