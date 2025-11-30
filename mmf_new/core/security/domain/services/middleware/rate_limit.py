"""
Rate Limit Middleware

Middleware for enforcing rate limits on requests.
"""

from datetime import datetime
from typing import Any

from mmf_new.core.security.domain.config import RateLimitConfig
from mmf_new.core.security.domain.models.rate_limit import (
    RateLimitQuota,
    RateLimitResult,
    RateLimitRule,
    RateLimitScope,
    RateLimitStrategy,
)
from mmf_new.core.security.domain.services.middleware.base import BaseMiddleware
from mmf_new.core.security.ports.rate_limiting import IRateLimiter


class RateLimitMiddleware(BaseMiddleware):
    """Middleware for rate limiting."""

    def __init__(self, rate_limiter: IRateLimiter, config: RateLimitConfig):
        self.rate_limiter = rate_limiter
        self.config = config

    async def process(
        self,
        request_context: dict[str, Any],
        next_middleware: Any = None,
    ) -> dict[str, Any]:
        """
        Check rate limits before proceeding.
        """
        rate_limit_result = await self._check_rate_limits(request_context)

        if not rate_limit_result.allowed:
            request_context["error"] = "Rate limit exceeded"
            request_context["status_code"] = 429
            return request_context

        if next_middleware:
            return await next_middleware(request_context)

        return request_context

    async def _check_rate_limits(
        self,
        request_context: dict[str, Any],
    ) -> RateLimitResult:
        """Check rate limits for request."""
        if not self.config.enabled:
            return RateLimitResult(
                allowed=True,
                rule_name="disabled",
                current_count=0,
                limit=0,
                reset_time=datetime.utcnow(),
            )

        # Determine key (IP, User ID, etc.)
        ip_address = request_context.get("ip_address")
        user_id = request_context.get("user_id")
        endpoint = request_context.get("path")

        # Create default rule if none exists
        # In reality, we should fetch rules from config or repository
        # For now, we'll create a dynamic rule based on config
        limit_str = self.config.default_rate
        limit = 100
        if "/" in limit_str:
            try:
                limit = int(limit_str.split("/")[0])
            except ValueError:
                pass

        rule = RateLimitRule(
            name="default",
            scope=RateLimitScope.PER_IP if not user_id else RateLimitScope.PER_USER,
            strategy=RateLimitStrategy.TOKEN_BUCKET,
            limit=limit,
            window_seconds=60,
        )

        quota = RateLimitQuota(
            user_id=user_id, ip_address=ip_address, endpoint=endpoint, rules=[rule]
        )

        return await self.rate_limiter.check_rate_limit(quota)
