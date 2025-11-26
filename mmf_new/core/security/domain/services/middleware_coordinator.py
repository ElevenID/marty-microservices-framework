"""
Security Middleware Coordinator

Implementation of IMiddlewareCoordinator for coordinating security components.
"""

import logging
from datetime import datetime
from typing import Any

from mmf_new.core.security.domain.config import RateLimitConfig, SessionConfig, JWTConfig
from mmf_new.core.security.domain.models.rate_limit import (
    RateLimitResult,
    RateLimitQuota,
    RateLimitRule,
    RateLimitScope,
    RateLimitStrategy,
)
from mmf_new.core.security.domain.models.session import SessionData, SessionState
from mmf_new.core.security.ports.middleware import IMiddlewareCoordinator
from mmf_new.core.security.ports.rate_limiting import IRateLimiter
from mmf_new.core.security.ports.session import ISessionManager

logger = logging.getLogger(__name__)


class SecurityMiddlewareCoordinator(IMiddlewareCoordinator):
    """
    Coordinator for security middleware components.

    Orchestrates authentication, authorization, rate limiting, and session management.
    """

    def __init__(
        self,
        session_manager: ISessionManager,
        rate_limiter: IRateLimiter,
        session_config: SessionConfig,
        rate_limit_config: RateLimitConfig,
        jwt_config: JWTConfig | None = None,
    ):
        """
        Initialize security coordinator.

        Args:
            session_manager: Session manager instance
            rate_limiter: Rate limiter instance
            session_config: Session configuration
            rate_limit_config: Rate limit configuration
            jwt_config: JWT configuration (optional)
        """
        self.session_manager = session_manager
        self.rate_limiter = rate_limiter
        self.session_config = session_config
        self.rate_limit_config = rate_limit_config
        self.jwt_config = jwt_config

    async def process_request(
        self,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process incoming request through security pipeline.

        Pipeline:
        1. Rate Limiting (Fail fast)
        2. Session Management / Authentication
        3. Authorization (TODO)
        """
        # 1. Rate Limiting
        rate_limit_result = await self.check_rate_limits(request_context)
        if not rate_limit_result.allowed:
            request_context["error"] = "Rate limit exceeded"
            request_context["status_code"] = 429
            return request_context

        # 2. Session Management / Authentication
        session = await self.manage_session(request_context)
        if session:
            request_context["user"] = session.user_id
            request_context["session"] = session
        else:
            # Try JWT or other auth if session not found
            auth_result = await self.authenticate_request(request_context)
            if "user" in auth_result:
                request_context["user"] = auth_result["user"]
                # Create session if configured to do so on auth?
                # Usually we create session on login, not every request.

        # 3. Authorization
        # TODO: Implement authorization logic

        return request_context

    async def authenticate_request(
        self,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Authenticate incoming request."""
        # Placeholder for JWT/API Key auth logic
        # In a real implementation, we would parse headers and validate tokens
        return request_context

    async def authorize_request(
        self,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Authorize incoming request."""
        # Placeholder for RBAC/ABAC logic
        return request_context

    async def check_rate_limits(
        self,
        request_context: dict[str, Any],
    ) -> RateLimitResult:
        """Check rate limits for request."""
        if not self.rate_limit_config.enabled:
            return RateLimitResult(
                allowed=True,
                rule_name="disabled",
                current_count=0,
                limit=0,
                reset_time=datetime.utcnow()
            )

        # Determine key (IP, User ID, etc.)
        ip_address = request_context.get("ip_address")
        user_id = request_context.get("user_id")
        endpoint = request_context.get("path")

        # Create default rule if none exists
        # In reality, we should fetch rules from config or repository
        # For now, we'll create a dynamic rule based on config
        limit_str = self.rate_limit_config.default_rate
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
            window_seconds=60
        )

        quota = RateLimitQuota(
            user_id=user_id,
            ip_address=ip_address,
            endpoint=endpoint,
            rules=[rule]
        )

        return await self.rate_limiter.check_rate_limit(quota)

    async def manage_session(
        self,
        request_context: dict[str, Any],
    ) -> SessionData | None:
        """Manage session for request."""
        if not self.session_config.enabled:
            return None

        session_id = request_context.get("session_id")
        if not session_id:
            # Try to get from cookies
            cookies = request_context.get("cookies", {})
            session_id = cookies.get(self.session_config.session_cookie_name)

        if not session_id:
            return None

        session = await self.session_manager.get_session(session_id)
        if not session:
            return None

        # Validate session
        if session.state != SessionState.ACTIVE:
            return None

        # Update access time (sliding window)
        await self.session_manager.update_session(session)

        return session

    async def apply_security_headers(
        self,
        response_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Apply security headers to response."""
        headers = response_context.get("headers", {})

        # Standard security headers
        headers["X-Content-Type-Options"] = "nosniff"
        headers["X-Frame-Options"] = "DENY"
        headers["X-XSS-Protection"] = "1; mode=block"
        headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"

        response_context["headers"] = headers
        return response_context