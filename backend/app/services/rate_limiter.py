"""Rate limiting service using Redis."""
import json
import time
from typing import Optional, Tuple

from app.core.redis import redis_client
from app.core.config import settings


class RateLimiter:
    """Rate limiter using Redis sliding window algorithm.

    Features:
    - Sliding window rate limiting
    - Per-user and per-API-key limits
    - Configurable rate limits
    """

    def __init__(self):
        self.enabled = settings.RATE_LIMIT_ENABLED
        self.default_limit = settings.RATE_LIMIT_PER_MINUTE

    async def is_allowed(
        self,
        identifier: str,
        limit: Optional[int] = None,
    ) -> Tuple[bool, dict]:
        """Check if a request is allowed under rate limiting.

        Args:
            identifier: Unique identifier (user_id or api_key_id)
            limit: Custom rate limit (requests per minute)

        Returns:
            Tuple of (is_allowed, rate_info_dict)
        """
        if not self.enabled:
            return True, {"limit": self.default_limit, "remaining": self.default_limit, "reset": time.time() + 60}

        limit = limit or self.default_limit
        key = f"rate_limit:{identifier}"
        now = time.time()
        window_start = now - 60  # 1 minute window

        try:
            # Use Redis pipeline for atomic operations
            pipe = redis_client.pipeline()

            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)

            # Count current requests in window
            pipe.zcard(key)

            # Add current request
            pipe.zadd(key, {str(now): now})

            # Set expiry on the key
            pipe.expire(key, 60)

            results = await pipe.execute()
            current_count = results[1]

            remaining = max(0, limit - current_count - 1)
            reset_time = int(now + 60)

            rate_info = {
                "limit": limit,
                "remaining": remaining,
                "reset": reset_time,
            }

            if current_count >= limit:
                return False, rate_info

            return True, rate_info

        except Exception:
            # If Redis fails, allow the request (fail open)
            return True, {"limit": limit, "remaining": limit, "reset": time.time() + 60}

    async def get_rate_info(self, identifier: str, limit: Optional[int] = None) -> dict:
        """Get current rate limit info without incrementing.

        Args:
            identifier: Unique identifier
            limit: Custom rate limit

        Returns:
            Rate info dictionary
        """
        if not self.enabled:
            return {"limit": self.default_limit, "remaining": self.default_limit, "reset": time.time() + 60}

        limit = limit or self.default_limit
        key = f"rate_limit:{identifier}"
        now = time.time()
        window_start = now - 60

        try:
            # Remove old entries and count
            await redis_client.zremrangebyscore(key, 0, window_start)
            current_count = await redis_client.zcard(key)

            remaining = max(0, limit - current_count)
            reset_time = int(now + 60)

            return {
                "limit": limit,
                "remaining": remaining,
                "reset": reset_time,
            }
        except Exception:
            return {"limit": limit, "remaining": limit, "reset": time.time() + 60}


# Global rate limiter instance
rate_limiter = RateLimiter()