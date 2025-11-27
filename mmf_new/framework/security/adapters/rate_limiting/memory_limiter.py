"""
Memory Rate Limiter Adapter

In-memory implementation of the rate limiting port for development and testing.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import Any

from mmf_new.core.security.domain.models.rate_limit import (
    RateLimitMetrics,
    RateLimitQuota,
    RateLimitResult,
    RateLimitWindow,
)
from mmf_new.core.security.domain.services.rate_limiting import RateLimitEngine
from mmf_new.core.security.ports.rate_limiting import IRateLimiter

logger = logging.getLogger(__name__)


class MemoryRateLimiter(IRateLimiter):
    """In-memory rate limiter for development and testing."""

    def __init__(self, key_prefix: str = "rate_limit"):
        self.key_prefix = key_prefix
        self.engine = RateLimitEngine()
        self.metrics = RateLimitMetrics()
        self._windows: dict[str, RateLimitWindow] = {}

    async def check_rate_limit(self, quota: RateLimitQuota) -> RateLimitResult:
        """Check rate limit without incrementing counter."""
        try:
            self._cleanup_expired_windows()

            # Check all rules for this quota
            for rule in quota.rules:
                cache_key = quota.get_cache_key(rule)
                window_data = self._windows.get(cache_key)

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
            logger.error("Error checking rate limit: %s", str(e))
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
            self._cleanup_expired_windows()

            # Check all rules for this quota
            for rule in quota.rules:
                cache_key = quota.get_cache_key(rule)
                window_data = self._windows.get(cache_key)

                result = self.engine.check_limit(rule, quota, window_data)

                if result.allowed and window_data is not None:
                    # Store updated window data
                    self._windows[cache_key] = window_data
                elif not result.allowed:
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
            logger.error("Error incrementing rate limit counter: %s", str(e))
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
            if full_key in self._windows:
                del self._windows[full_key]
                return True
            return False
        except Exception as e:
            logger.error("Error resetting quota for key %s: %s", cache_key, str(e))
            return False

    async def get_quota_status(self, cache_key: str) -> dict[str, Any] | None:
        """Get current quota status for a key."""
        try:
            full_key = f"{self.key_prefix}:{cache_key}"
            window_data = self._windows.get(full_key)

            if window_data is None:
                return None

            return {
                "key": cache_key,
                "current_count": window_data.current_count,
                "reset_time": window_data.reset_time.isoformat(),
                "burst_count": window_data.burst_count,
                "created_at": window_data.created_at.isoformat(),
                "is_expired": window_data.is_expired,
            }

        except Exception as e:
            logger.error("Error getting quota status for key %s: %s", cache_key, str(e))
            return None

    async def get_metrics(self) -> RateLimitMetrics:
        """Get rate limiting metrics."""
        return self.metrics

    async def cleanup_expired(self) -> int:
        """Clean up expired rate limit entries."""
        try:
            return self._cleanup_expired_windows()
        except Exception as e:
            logger.error("Error during cleanup: %s", str(e))
            return 0

    async def health_check(self) -> bool:
        """Check if rate limiter is healthy."""
        try:
            # Test basic functionality
            test_window = RateLimitWindow(
                key="health_check",
                current_count=0,
                reset_time=datetime.utcnow() + timedelta(seconds=1),
            )
            self._windows["health_check"] = test_window

            # Clean up test data
            if "health_check" in self._windows:
                del self._windows["health_check"]

            return True
        except Exception as e:
            logger.error("Health check failed: %s", str(e))
            return False

    def _cleanup_expired_windows(self) -> int:
        """Clean up expired windows."""
        now = datetime.utcnow()
        expired_keys = []

        for key, window in self._windows.items():
            if window.reset_time <= now:
                expired_keys.append(key)

        for key in expired_keys:
            del self._windows[key]

        return len(expired_keys)
