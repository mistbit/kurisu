"""Tests for rate limiting service."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.rate_limiter import RateLimiter


@pytest.mark.asyncio
async def test_rate_limiter_disabled():
    """Test that disabled rate limiter always allows requests."""
    limiter = RateLimiter()
    limiter.enabled = False

    allowed, info = await limiter.is_allowed("test_user")

    assert allowed is True
    assert info["limit"] == limiter.default_limit


@pytest.mark.asyncio
async def test_rate_limiter_redis_failure():
    """Test that rate limiter fails open when Redis is unavailable."""
    limiter = RateLimiter()
    limiter.enabled = True

    with patch("app.services.rate_limiter.redis_client") as mock_redis:
        # Make pipeline raise an exception
        mock_pipeline = MagicMock()
        mock_pipeline.zremrangebyscore.return_value = None
        mock_pipeline.zcard.return_value = None
        mock_pipeline.zadd.return_value = None
        mock_pipeline.expire.return_value = None
        # Make execute raise an exception
        mock_pipeline.execute = AsyncMock(side_effect=Exception("Redis connection failed"))
        mock_redis.pipeline = MagicMock(return_value=mock_pipeline)

        allowed, info = await limiter.is_allowed("test_user")

        # Should allow request when Redis fails (fail open)
        assert allowed is True


@pytest.mark.asyncio
async def test_rate_limiter_get_rate_info():
    """Test getting rate info without incrementing."""
    limiter = RateLimiter()
    limiter.enabled = True

    with patch("app.services.rate_limiter.redis_client") as mock_redis:
        mock_redis.zremrangebyscore = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=3)

        info = await limiter.get_rate_info("test_user", limit=10)

        assert info["limit"] == 10
        assert info["remaining"] == 7


@pytest.mark.asyncio
async def test_rate_limiter_get_rate_info_redis_failure():
    """Test get_rate_info handles Redis failure gracefully."""
    limiter = RateLimiter()
    limiter.enabled = True

    with patch("app.services.rate_limiter.redis_client") as mock_redis:
        mock_redis.zremrangebyscore = AsyncMock(side_effect=Exception("Redis error"))

        info = await limiter.get_rate_info("test_user", limit=10)

        # Should return safe defaults on failure
        assert info["limit"] == 10
        assert info["remaining"] == 10


@pytest.mark.asyncio
async def test_rate_limiter_get_rate_info_disabled():
    """Test get_rate_info when rate limiting is disabled."""
    limiter = RateLimiter()
    limiter.enabled = False

    info = await limiter.get_rate_info("test_user", limit=10)

    assert info["limit"] == limiter.default_limit
