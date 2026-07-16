"""
Redis Rate Limiter Adapter

Redis-based implementation of the rate limiting port using the existing cache infrastructure.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from typing import Any

from mmf.core.security.domain.models.rate_limit import (
    RateLimitMetrics,
    RateLimitQuota,
    RateLimitResult,
    RateLimitWindow,
)
from mmf.core.security.domain.services.rate_limiting import RateLimitEngine
from mmf.core.security.ports.rate_limiting import IRateLimiter
from mmf.framework.infrastructure.cache import CacheManager

logger = logging.getLogger(__name__)


class RedisRateLimiter(IRateLimiter):
    """Redis-based rate limiter using existing cache infrastructure."""

    def __init__(
        self,
        cache_manager: CacheManager,
        key_prefix: str = "rate_limit",
        default_ttl: int = 3600,
    ):
        self.cache = cache_manager
        self.key_prefix = key_prefix
        self.default_ttl = default_ttl
        self.engine = RateLimitEngine()
        self.metrics = RateLimitMetrics()

    async def check_rate_limit(self, quota: RateLimitQuota) -> RateLimitResult:
        """Check rate limit without incrementing counter."""
        try:
            # Check all rules for this quota
            for rule in quota.rules:
                cache_key = quota.get_cache_key(rule)
                window_data = await self._get_window_data(cache_key)

                result = self.engine.check_limit(rule, quota, window_data)

                if not result.allowed:
                    self.metrics.record_request(False, rule.name)
                    return result

            # If all rules pass, create a success result
            self.metrics.record_request(True)
            return RateLimitResult(
                allowed=True,
                rule_name="check_only",
                current_count=0,
                limit=0,
                reset_time=datetime.utcnow() + timedelta(seconds=60),
            )

        except Exception as e:
            logger.error(f"Error checking rate limit: {e}")
            # Fail open for availability
            return RateLimitResult(
                allowed=True,
                rule_name="error_fallback",
                current_count=0,
                limit=0,
                reset_time=datetime.utcnow() + timedelta(seconds=60),
                metadata={"error": str(e)},
            )

    async def increment_counter(self, quota: RateLimitQuota) -> RateLimitResult:
        """Increment counter and check rate limit."""
        try:
            # Check all rules for this quota
            for rule in quota.rules:
                cache_key = quota.get_cache_key(rule)
                window_data = await self._get_window_data(cache_key)

                result = self.engine.check_limit(rule, quota, window_data)

                if result.allowed:
                    # Store updated window data
                    await self._store_window_data(cache_key, window_data, rule.window_seconds)
                else:
                    self.metrics.record_request(False, rule.name)
                    return result

            # If all rules pass, record success
            self.metrics.record_request(True)
            return RateLimitResult(
                allowed=True,
                rule_name="all_passed",
                current_count=1,
                limit=quota.rules[0].limit if quota.rules else 1,
                reset_time=datetime.utcnow() + timedelta(seconds=60),
            )

        except Exception as e:
            logger.error(f"Error incrementing rate limit counter: {e}")
            # Fail open for availability
            return RateLimitResult(
                allowed=True,
                rule_name="error_fallback",
                current_count=0,
                limit=0,
                reset_time=datetime.utcnow() + timedelta(seconds=60),
                metadata={"error": str(e)},
            )

    async def reset_quota(self, cache_key: str) -> bool:
        """Reset rate limit quota for a specific key."""
        try:
            full_key = f"{self.key_prefix}:{cache_key}"
            return await self.cache.delete(full_key)
        except Exception as e:
            logger.error(f"Error resetting quota for key {cache_key}: {e}")
            return False

    async def get_quota_status(self, cache_key: str) -> dict[str, Any] | None:
        """Get current quota status for a key."""
        try:
            full_key = f"{self.key_prefix}:{cache_key}"
            data = await self.cache.get(full_key)

            if data is None:
                return None

            window_data = self._deserialize_window_data(data)
            return {
                "key": cache_key,
                "current_count": window_data.current_count,
                "reset_time": window_data.reset_time.isoformat(),
                "burst_count": window_data.burst_count,
                "created_at": window_data.created_at.isoformat(),
                "is_expired": window_data.is_expired,
            }

        except Exception as e:
            logger.error(f"Error getting quota status for key {cache_key}: {e}")
            return None

    async def get_metrics(self) -> RateLimitMetrics:
        """Get rate limiting metrics."""
        return self.metrics

    async def cleanup_expired(self) -> int:
        """Clean up expired rate limit entries."""
        # Redis TTL handles expiration automatically
        # This method could be used for additional cleanup logic
        return 0

    async def health_check(self) -> bool:
        """Check if rate limiter is healthy."""
        try:
            # Test cache connectivity
            test_key = f"{self.key_prefix}:health_check"
            await self.cache.set(test_key, "ok", ttl=1)
            result = await self.cache.get(test_key)
            await self.cache.delete(test_key)
            return result is not None
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return False

    async def _get_window_data(self, cache_key: str) -> RateLimitWindow | None:
        """Get window data from cache."""
        try:
            full_key = f"{self.key_prefix}:{cache_key}"
            data = await self.cache.get(full_key)

            if data is None:
                return None

            return self._deserialize_window_data(data)

        except Exception as e:
            logger.error(f"Error getting window data for key {cache_key}: {e}")
            return None

    async def _store_window_data(
        self, cache_key: str, window_data: RateLimitWindow, ttl_seconds: int
    ) -> bool:
        """Store window data in cache."""
        try:
            full_key = f"{self.key_prefix}:{cache_key}"
            serialized_data = self._serialize_window_data(window_data)

            return await self.cache.set(full_key, serialized_data, ttl=ttl_seconds)

        except Exception as e:
            logger.error(f"Error storing window data for key {cache_key}: {e}")
            return False

    def _serialize_window_data(self, window_data: RateLimitWindow) -> str:
        """Serialize window data for cache storage."""
        return json.dumps(
            {
                "key": window_data.key,
                "current_count": window_data.current_count,
                "reset_time": window_data.reset_time.isoformat(),
                "burst_count": window_data.burst_count,
                "created_at": window_data.created_at.isoformat(),
            }
        )

    def _deserialize_window_data(self, data: str | bytes) -> RateLimitWindow:
        """Deserialize window data from cache."""
        if isinstance(data, bytes):
            data = data.decode("utf-8")

        parsed = json.loads(data)
        return RateLimitWindow(
            key=parsed["key"],
            current_count=parsed["current_count"],
            reset_time=datetime.fromisoformat(parsed["reset_time"]),
            burst_count=parsed["burst_count"],
            created_at=datetime.fromisoformat(parsed["created_at"]),
        )
