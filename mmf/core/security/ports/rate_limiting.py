"""
Rate Limiting Port

Interface for rate limiting functionality.
"""

from abc import ABC, abstractmethod
from typing import Any

from ..domain.models.rate_limit import RateLimitMetrics, RateLimitQuota, RateLimitResult


class IRateLimiter(ABC):
    """Interface for rate limiting implementations."""

    @abstractmethod
    async def check_rate_limit(self, quota: RateLimitQuota) -> RateLimitResult:
        """
        Check if request is allowed based on rate limiting rules.

        Args:
            quota: Rate limit quota with user/IP/endpoint information

        Returns:
            RateLimitResult with decision and metadata
        """
        pass

    @abstractmethod
    async def increment_counter(self, quota: RateLimitQuota) -> RateLimitResult:
        """
        Increment request counter and check rate limit.

        Args:
            quota: Rate limit quota with user/IP/endpoint information

        Returns:
            RateLimitResult with updated counters
        """
        pass

    @abstractmethod
    async def reset_quota(self, cache_key: str) -> bool:
        """
        Reset rate limit quota for a specific key.

        Args:
            cache_key: Cache key to reset

        Returns:
            True if reset was successful
        """
        pass

    @abstractmethod
    async def get_quota_status(self, cache_key: str) -> dict[str, Any] | None:
        """
        Get current quota status for a key.

        Args:
            cache_key: Cache key to check

        Returns:
            Quota status dictionary or None if not found
        """
        pass

    @abstractmethod
    async def get_metrics(self) -> RateLimitMetrics:
        """
        Get rate limiting metrics.

        Returns:
            RateLimitMetrics with current statistics
        """
        pass

    @abstractmethod
    async def cleanup_expired(self) -> int:
        """
        Clean up expired rate limit entries.

        Returns:
            Number of entries cleaned up
        """
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """
        Check if rate limiter is healthy.

        Returns:
            True if healthy, False otherwise
        """
        pass
