"""
Rate Limiting Domain Models

Domain models for rate limiting functionality in the security module.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any


class RateLimitStrategy(Enum):
    """Rate limiting strategies."""

    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


class RateLimitScope(Enum):
    """Rate limit scope types."""

    GLOBAL = "global"
    PER_USER = "per_user"
    PER_IP = "per_ip"
    PER_ENDPOINT = "per_endpoint"
    PER_SERVICE = "per_service"


@dataclass
class RateLimitRule:
    """Rate limit rule definition."""

    name: str
    scope: RateLimitScope
    strategy: RateLimitStrategy
    limit: int  # Number of requests
    window_seconds: int  # Time window in seconds
    burst_size: int = 0  # Additional burst capacity
    key_pattern: str = ""  # Key pattern for scope (e.g., "user:{user_id}")
    enabled: bool = True

    def __post_init__(self):
        if self.limit <= 0:
            raise ValueError("Rate limit must be positive")
        if self.window_seconds <= 0:
            raise ValueError("Window size must be positive")
        if self.burst_size < 0:
            raise ValueError("Burst size cannot be negative")


@dataclass
class RateLimitWindow:
    """Rate limit window state."""

    key: str
    current_count: int
    reset_time: datetime
    burst_count: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)

    @property
    def is_expired(self) -> bool:
        """Check if window has expired."""
        return datetime.utcnow() >= self.reset_time

    @property
    def remaining_capacity(self) -> int:
        """Get remaining capacity in this window."""
        # This would be calculated by the rate limiter based on the rule
        return 0

    def reset(self, window_seconds: int) -> None:
        """Reset the window."""
        self.current_count = 0
        self.burst_count = 0
        self.reset_time = datetime.utcnow() + timedelta(seconds=window_seconds)


@dataclass
class RateLimitResult:
    """Result of rate limit check."""

    allowed: bool
    rule_name: str
    current_count: int
    limit: int
    reset_time: datetime
    retry_after_seconds: int = 0
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    @property
    def remaining(self) -> int:
        """Get remaining requests in current window."""
        return max(0, self.limit - self.current_count)


@dataclass
class RateLimitQuota:
    """Rate limit quota definition."""

    user_id: str | None = None
    ip_address: str | None = None
    endpoint: str | None = None
    service: str | None = None
    custom_key: str | None = None
    rules: builtins.list[RateLimitRule] = field(default_factory=list)
    override_limits: builtins.dict[str, int] = field(default_factory=dict)  # rule_name -> limit

    def get_cache_key(self, rule: RateLimitRule) -> str:
        """Generate cache key for this quota and rule."""
        scope_value = ""

        if rule.scope == RateLimitScope.PER_USER and self.user_id:
            scope_value = f"user:{self.user_id}"
        elif rule.scope == RateLimitScope.PER_IP and self.ip_address:
            scope_value = f"ip:{self.ip_address}"
        elif rule.scope == RateLimitScope.PER_ENDPOINT and self.endpoint:
            scope_value = f"endpoint:{self.endpoint}"
        elif rule.scope == RateLimitScope.PER_SERVICE and self.service:
            scope_value = f"service:{self.service}"
        elif rule.scope == RateLimitScope.GLOBAL:
            scope_value = "global"
        elif self.custom_key:
            scope_value = self.custom_key
        else:
            scope_value = "unknown"

        return f"rate_limit:{rule.name}:{scope_value}"


@dataclass
class RateLimitMetrics:
    """Rate limiting metrics."""

    total_requests: int = 0
    allowed_requests: int = 0
    blocked_requests: int = 0
    rules_triggered: builtins.dict[str, int] = field(default_factory=dict)
    average_response_time_ms: float = 0.0
    peak_requests_per_second: int = 0
    last_reset: datetime = field(default_factory=datetime.utcnow)

    @property
    def block_rate(self) -> float:
        """Calculate block rate percentage."""
        if self.total_requests == 0:
            return 0.0
        return (self.blocked_requests / self.total_requests) * 100

    @property
    def allow_rate(self) -> float:
        """Calculate allow rate percentage."""
        return 100.0 - self.block_rate

    def record_request(self, allowed: bool, rule_name: str | None = None) -> None:
        """Record a request in metrics."""
        self.total_requests += 1
        if allowed:
            self.allowed_requests += 1
        else:
            self.blocked_requests += 1
            if rule_name:
                self.rules_triggered[rule_name] = self.rules_triggered.get(rule_name, 0) + 1
