"""
Rate Limiting Domain Services

Core business logic for rate limiting functionality.
"""

from __future__ import annotations

import builtins
import math
from datetime import datetime, timedelta
from typing import Any

from ..models.rate_limit import (
    RateLimitQuota,
    RateLimitResult,
    RateLimitRule,
    RateLimitStrategy,
    RateLimitWindow,
)


class RateLimitEngine:
    """Core rate limiting engine with various strategies."""

    def __init__(self):
        self.strategies = {
            RateLimitStrategy.TOKEN_BUCKET: self._token_bucket_check,
            RateLimitStrategy.SLIDING_WINDOW: self._sliding_window_check,
            RateLimitStrategy.FIXED_WINDOW: self._fixed_window_check,
            RateLimitStrategy.LEAKY_BUCKET: self._leaky_bucket_check,
        }

    def check_limit(
        self,
        rule: RateLimitRule,
        quota: RateLimitQuota,
        current_window: RateLimitWindow | None = None,
    ) -> RateLimitResult:
        """
        Check rate limit using appropriate strategy.

        Args:
            rule: Rate limit rule to apply
            quota: Rate limit quota information
            current_window: Current window state (if available)

        Returns:
            RateLimitResult with decision
        """
        if not rule.enabled:
            return RateLimitResult(
                allowed=True,
                rule_name=rule.name,
                current_count=0,
                limit=rule.limit,
                reset_time=datetime.utcnow() + timedelta(seconds=rule.window_seconds),
            )

        strategy_func = self.strategies.get(rule.strategy)
        if not strategy_func:
            raise ValueError(f"Unsupported rate limit strategy: {rule.strategy}")

        return strategy_func(rule, quota, current_window)

    def _token_bucket_check(
        self,
        rule: RateLimitRule,
        quota: RateLimitQuota,
        current_window: RateLimitWindow | None = None,
    ) -> RateLimitResult:
        """Token bucket algorithm implementation."""
        now = datetime.utcnow()

        if current_window is None:
            # Initialize new bucket
            current_window = RateLimitWindow(
                key=quota.get_cache_key(rule),
                current_count=rule.limit,  # Start with full bucket
                reset_time=now + timedelta(seconds=rule.window_seconds),
            )

        # Calculate tokens to add based on time elapsed
        time_elapsed = (now - current_window.created_at).total_seconds()
        refill_rate = rule.limit / rule.window_seconds  # tokens per second
        tokens_to_add = int(time_elapsed * refill_rate)

        # Refill bucket (up to limit + burst)
        max_tokens = rule.limit + rule.burst_size
        current_window.current_count = min(max_tokens, current_window.current_count + tokens_to_add)

        # Check if request can be allowed
        if current_window.current_count >= 1:
            current_window.current_count -= 1
            allowed = True
            retry_after = 0
        else:
            allowed = False
            # Calculate retry after time
            retry_after = int(1 / refill_rate) if refill_rate > 0 else rule.window_seconds

        return RateLimitResult(
            allowed=allowed,
            rule_name=rule.name,
            current_count=rule.limit - current_window.current_count,
            limit=rule.limit,
            reset_time=current_window.reset_time,
            retry_after_seconds=retry_after,
        )

    def _sliding_window_check(
        self,
        rule: RateLimitRule,
        quota: RateLimitQuota,
        current_window: RateLimitWindow | None = None,
    ) -> RateLimitResult:
        """Sliding window algorithm implementation."""
        now = datetime.utcnow()

        if current_window is None:
            current_window = RateLimitWindow(
                key=quota.get_cache_key(rule),
                current_count=0,
                reset_time=now + timedelta(seconds=rule.window_seconds),
            )

        # Check if window has expired
        if current_window.is_expired:
            current_window.reset(rule.window_seconds)

        # For sliding window, we need to track requests in time buckets
        # This is a simplified implementation - in practice, you'd maintain
        # a list of timestamps or use Redis sorted sets
        now - timedelta(seconds=rule.window_seconds)

        # In a real implementation, you'd filter requests within the sliding window
        # For now, we'll use a simple approximation
        current_window.current_count / rule.window_seconds

        # Check if adding this request would exceed the limit
        effective_limit = rule.limit + rule.burst_size
        if current_window.current_count < effective_limit:
            current_window.current_count += 1
            allowed = True
            retry_after = 0
        else:
            allowed = False
            # Calculate when the oldest request in window expires
            retry_after = rule.window_seconds

        return RateLimitResult(
            allowed=allowed,
            rule_name=rule.name,
            current_count=current_window.current_count,
            limit=rule.limit,
            reset_time=current_window.reset_time,
            retry_after_seconds=retry_after,
        )

    def _fixed_window_check(
        self,
        rule: RateLimitRule,
        quota: RateLimitQuota,
        current_window: RateLimitWindow | None = None,
    ) -> RateLimitResult:
        """Fixed window algorithm implementation."""
        now = datetime.utcnow()

        if current_window is None:
            current_window = RateLimitWindow(
                key=quota.get_cache_key(rule),
                current_count=0,
                reset_time=now + timedelta(seconds=rule.window_seconds),
            )

        # Check if window has expired
        if current_window.is_expired:
            current_window.reset(rule.window_seconds)

        # Check if request can be allowed
        effective_limit = rule.limit + rule.burst_size
        if current_window.current_count < effective_limit:
            current_window.current_count += 1
            allowed = True
            retry_after = 0
        else:
            allowed = False
            retry_after = int((current_window.reset_time - now).total_seconds())

        return RateLimitResult(
            allowed=allowed,
            rule_name=rule.name,
            current_count=current_window.current_count,
            limit=rule.limit,
            reset_time=current_window.reset_time,
            retry_after_seconds=max(0, retry_after),
        )

    def _leaky_bucket_check(
        self,
        rule: RateLimitRule,
        quota: RateLimitQuota,
        current_window: RateLimitWindow | None = None,
    ) -> RateLimitResult:
        """Leaky bucket algorithm implementation."""
        now = datetime.utcnow()

        if current_window is None:
            current_window = RateLimitWindow(
                key=quota.get_cache_key(rule),
                current_count=0,
                reset_time=now + timedelta(seconds=rule.window_seconds),
            )

        # Calculate leak rate (requests per second)
        leak_rate = rule.limit / rule.window_seconds

        # Calculate how much has leaked since last check
        time_elapsed = (now - current_window.created_at).total_seconds()
        leaked_amount = int(time_elapsed * leak_rate)

        # Leak from bucket
        current_window.current_count = max(0, current_window.current_count - leaked_amount)

        # Check if bucket has capacity
        bucket_capacity = rule.limit + rule.burst_size
        if current_window.current_count < bucket_capacity:
            current_window.current_count += 1
            allowed = True
            retry_after = 0
        else:
            allowed = False
            # Calculate when bucket will have capacity
            retry_after = int(1 / leak_rate) if leak_rate > 0 else rule.window_seconds

        return RateLimitResult(
            allowed=allowed,
            rule_name=rule.name,
            current_count=current_window.current_count,
            limit=rule.limit,
            reset_time=current_window.reset_time,
            retry_after_seconds=retry_after,
        )


class SessionCleanupService:
    """Domain service for session cleanup operations."""

    def __init__(self, cleanup_interval_minutes: int = 5):
        self.cleanup_interval_minutes = cleanup_interval_minutes
        self.last_cleanup = datetime.utcnow()

    def should_run_cleanup(self) -> bool:
        """Check if cleanup should run based on interval."""
        now = datetime.utcnow()
        return (now - self.last_cleanup).total_seconds() >= (self.cleanup_interval_minutes * 60)

    def mark_cleanup_completed(self) -> None:
        """Mark cleanup as completed."""
        completed_at = datetime.utcnow()
        if completed_at <= self.last_cleanup:
            completed_at = self.last_cleanup + timedelta(microseconds=1)
        self.last_cleanup = completed_at

    def calculate_cleanup_priority(self, session_age_minutes: int) -> int:
        """
        Calculate cleanup priority for a session.

        Args:
            session_age_minutes: Age of session in minutes

        Returns:
            Priority level (higher = more urgent)
        """
        if session_age_minutes > 720:  # 12 hours
            return 5  # Critical
        elif session_age_minutes > 480:  # 8 hours
            return 4  # High
        elif session_age_minutes > 240:  # 4 hours
            return 3  # Medium
        elif session_age_minutes > 60:  # 1 hour
            return 2  # Low
        else:
            return 1  # Minimal


class RateLimitCoordinationService:
    """Service for coordinating application and Istio rate limits."""

    def __init__(self, istio_safety_multiplier: float = 2.0):
        self.istio_safety_multiplier = istio_safety_multiplier

    def calculate_istio_limit(self, app_limit: int) -> int:
        """
        Calculate Istio rate limit based on application limit.

        Args:
            app_limit: Application layer rate limit

        Returns:
            Istio rate limit (safety net)
        """
        return int(app_limit * self.istio_safety_multiplier)

    def should_apply_istio_limit(
        self, app_result: RateLimitResult, user_authenticated: bool
    ) -> bool:
        """
        Determine if Istio rate limiting should be applied.

        Args:
            app_result: Application rate limit result
            user_authenticated: Whether user is authenticated

        Returns:
            True if Istio limits should be applied
        """
        # Apply Istio limits for unauthenticated users or when app limits are hit
        return not user_authenticated or not app_result.allowed

    def create_coordination_metadata(self, app_result: RateLimitResult) -> builtins.dict[str, Any]:
        """
        Create metadata for coordinating rate limits.

        Args:
            app_result: Application rate limit result

        Returns:
            Coordination metadata
        """
        return {
            "app_limit_hit": not app_result.allowed,
            "app_current_count": app_result.current_count,
            "app_limit": app_result.limit,
            "istio_limit": self.calculate_istio_limit(app_result.limit),
            "coordination_strategy": "safety_net",
        }
