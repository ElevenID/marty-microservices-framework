"""
Rate limiting for the enterprise security framework.
"""

import asyncio
import builtins
import logging
import re
import time
from abc import ABC, abstractmethod
from collections.abc import Callable
from functools import wraps

import redis.asyncio as redis

from .config import RateLimitConfig
from .errors import RateLimitExceededError

logger = logging.getLogger(__name__)


class RateLimitBackend(ABC):
    """Abstract base class for rate limit backends."""

    @abstractmethod
    async def increment(self, key: str, window: int, limit: int) -> tuple[int, int]:
        """Increment counter and return (current_count, ttl)."""

    @abstractmethod
    async def reset(self, key: str) -> None:
        """Reset counter for a key."""


class MemoryRateLimitBackend(RateLimitBackend):
    """In-memory rate limit backend using sliding window."""

    def __init__(self):
        self._windows: builtins.dict[str, builtins.dict[int, int]] = {}
        self._lock = asyncio.Lock()

    async def increment(self, key: str, window: int, limit: int) -> tuple[int, int]:
        """Increment counter using sliding window algorithm."""
        async with self._lock:
            current_time = int(time.time())
            window_start = current_time - window

            if key not in self._windows:
                self._windows[key] = {}

            # Clean old entries
            expired_times = [t for t in self._windows[key] if t < window_start]
            for t in expired_times:
                del self._windows[key][t]

            # Add current request
            if current_time not in self._windows[key]:
                self._windows[key][current_time] = 0
            self._windows[key][current_time] += 1

            # Count total requests in window
            total_requests = sum(self._windows[key].values())

            # Calculate TTL (time until oldest entry expires)
            if self._windows[key]:
                oldest_time = min(self._windows[key].keys())
                ttl = window - (current_time - oldest_time)
            else:
                ttl = window

            return total_requests, max(0, ttl)

    async def reset(self, key: str) -> None:
        """Reset counter for a key."""
        async with self._lock:
            if key in self._windows:
                del self._windows[key]


class RedisRateLimitBackend(RateLimitBackend):
    """Redis-based rate limit backend."""

    def __init__(self, redis_url: str):
        self.redis_url = redis_url
        self._redis = None

    async def _get_redis(self):
        """Get Redis connection (lazy initialization)."""
        if self._redis is None:
            try:

                self._redis = redis.from_url(self.redis_url)
            except ImportError:
                logger.error("redis package not installed. Using memory backend.")
                raise ImportError("redis package required for Redis backend")
        return self._redis

    async def increment(self, key: str, window: int, limit: int) -> tuple[int, int]:
        """Increment counter using Redis sliding window."""
        try:
            redis_client = await self._get_redis()
            current_time = time.time()
            window_start = current_time - window

            # Use Redis sorted set for sliding window
            pipe = redis_client.pipeline()

            # Remove expired entries
            pipe.zremrangebyscore(key, 0, window_start)

            # Add current request
            pipe.zadd(key, {str(current_time): current_time})

            # Count total requests in window
            pipe.zcard(key)

            # Set expiration
            pipe.expire(key, window)

            results = await pipe.execute()

            total_requests = results[2]  # Result of zcard
            ttl = await redis_client.ttl(key)

            return total_requests, max(0, ttl)

        except Exception as e:
            logger.error("Redis rate limit error: %s", e)
            # Fallback to allow request if Redis fails
            return 0, window

    async def reset(self, key: str) -> None:
        """Reset counter for a key."""
        try:
            redis_client = await self._get_redis()
            await redis_client.delete(key)
        except Exception as e:
            logger.error("Redis reset error: %s", e)


class RateLimitRule:
    """Represents a rate limiting rule."""

    def __init__(self, rate_string: str):
        self.rate_string = rate_string
        self.limit, self.window = self._parse_rate_string(rate_string)

    def _parse_rate_string(self, rate_string: str) -> tuple[int, int]:
        """Parse rate string like '100/minute' into (limit, window_seconds)."""
        match = re.match(r"(\d+)/(\w+)", rate_string)
        if not match:
            raise ValueError(f"Invalid rate string format: {rate_string}")

        limit = int(match.group(1))
        period = match.group(2).lower()

        period_map = {
            "second": 1,
            "minute": 60,
            "hour": 3600,
            "day": 86400,
        }

        if period not in period_map:
            raise ValueError(f"Invalid period: {period}")

        window = period_map[period]
        return limit, window


class RateLimiter:
    """Rate limiter with configurable backends and rules."""

    def __init__(self, config: RateLimitConfig):
        self.config = config
        self.enabled = config.enabled

        if not self.enabled:
            return

        # Initialize backend
        if config.redis_url and not config.use_memory_backend:
            try:
                self.backend = RedisRateLimitBackend(config.redis_url)
            except ImportError:
                logger.warning("Redis not available, falling back to memory backend")
                self.backend = MemoryRateLimitBackend()
        else:
            self.backend = MemoryRateLimitBackend()

        # Parse default rate
        self.default_rule = RateLimitRule(config.default_rate)

        # Parse endpoint-specific rates
        self.endpoint_rules = {}
        for endpoint, rate in config.per_endpoint_limits.items():
            self.endpoint_rules[endpoint] = RateLimitRule(rate)

        # Parse user-specific rates
        self.user_rules = {}
        for user, rate in config.per_user_limits.items():
            self.user_rules[user] = RateLimitRule(rate)

    async def check_rate_limit(
        self,
        identifier: str,
        endpoint: str | None = None,
        user_id: str | None = None,
    ) -> tuple[bool, builtins.dict[str, int | str]]:
        """
        Check rate limit for an identifier.

        Returns:
            (allowed, info) where info contains rate limit details
        """
        if not self.enabled:
            return True, {}

        # Determine which rule to use
        rule = self._get_applicable_rule(endpoint, user_id)

        # Create rate limit key
        key_parts = [self.config.key_prefix, identifier]
        if endpoint:
            key_parts.append(f"endpoint:{endpoint}")
        if user_id:
            key_parts.append(f"user:{user_id}")

        key = ":".join(key_parts)

        # Check rate limit
        try:
            count, ttl = await self.backend.increment(key, rule.window, rule.limit)

            allowed = count <= rule.limit

            info = {
                "limit": rule.limit,
                "remaining": max(0, rule.limit - count),
                "reset_time": int(time.time()) + ttl,
                "retry_after": ttl if not allowed else 0,
                "rate": rule.rate_string,
            }

            return allowed, info

        except Exception as e:
            logger.error("Rate limit check failed: %s", e)
            # Fail open - allow request if rate limiting fails
            return True, {}

    def _get_applicable_rule(self, endpoint: str | None, user_id: str | None) -> RateLimitRule:
        """Get the most specific applicable rule."""
        # User-specific rules take precedence
        if user_id and user_id in self.user_rules:
            return self.user_rules[user_id]

        # Then endpoint-specific rules
        if endpoint and endpoint in self.endpoint_rules:
            return self.endpoint_rules[endpoint]

        # Finally default rule
        return self.default_rule

    async def reset_rate_limit(self, identifier: str) -> None:
        """Reset rate limit for an identifier."""
        if not self.enabled:
            return

        key = f"{self.config.key_prefix}:{identifier}"
        await self.backend.reset(key)


# Global rate limiter instance
_rate_limiter_instance: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter | None:
    """Get the global rate limiter instance."""
    return _rate_limiter_instance


def initialize_rate_limiter(config: RateLimitConfig) -> None:
    """Initialize the global rate limiter."""
    # Using module-level variable
    globals()["_rate_limiter_instance"] = RateLimiter(config)


def rate_limit(
    identifier_func: Callable | None = None,
    endpoint: str | None = None,
    per_user: bool = True,
):
    """Decorator to apply rate limiting to a function."""

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            limiter = get_rate_limiter()
            if not limiter or not limiter.enabled:
                return await func(*args, **kwargs)

            # Get identifier
            if identifier_func:
                identifier = identifier_func(*args, **kwargs)
            else:
                # Try to get from request context
                request = kwargs.get("request")
                if request:
                    # Use client IP as default identifier
                    identifier = (
                        getattr(request.client, "host", "unknown") if request.client else "unknown"
                    )
                else:
                    identifier = "default"

            # Get user ID if per_user is enabled
            user_id = None
            if per_user:
                user = kwargs.get("user") or kwargs.get("current_user")
                request = kwargs.get("request")
                if request and hasattr(request, "state") and hasattr(request.state, "user"):
                    user = request.state.user

                if user and hasattr(user, "user_id"):
                    user_id = user.user_id

            # Check rate limit
            allowed, info = await limiter.check_rate_limit(
                identifier=identifier,
                endpoint=endpoint or func.__name__,
                user_id=user_id,
            )

            if not allowed:
                raise RateLimitExceededError(
                    message=f"Rate limit exceeded: {info.get('rate', 'unknown')}",
                    retry_after=info.get("retry_after"),
                    details=info,
                )

            # Add rate limit info to response if possible
            result = await func(*args, **kwargs)

            # If result is a response object, add headers
            if hasattr(result, "headers"):
                result.headers["X-RateLimit-Limit"] = str(info.get("limit", ""))
                result.headers["X-RateLimit-Remaining"] = str(info.get("remaining", ""))
                result.headers["X-RateLimit-Reset"] = str(info.get("reset_time", ""))

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # For sync functions, we need to run rate limiting in async context
            # This is a simplified version - in practice you'd need proper async handling
            return func(*args, **kwargs)

        # Return appropriate wrapper based on whether function is async

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator
