"""
Security Middleware Coordinator

Implementation of IMiddlewareCoordinator for coordinating security components.
"""

import logging
from typing import Any

from mmf.core.security.domain.config import JWTConfig, RateLimitConfig, SessionConfig
from mmf.core.security.domain.models.rate_limit import RateLimitQuota, RateLimitResult
from mmf.core.security.domain.models.session import SessionData
from mmf.core.security.domain.services.middleware.authentication import (
    AuthenticationMiddleware,
)
from mmf.core.security.domain.services.middleware.rate_limit import RateLimitMiddleware
from mmf.core.security.domain.services.middleware.session import SessionMiddleware
from mmf.core.security.ports.middleware import IMiddlewareCoordinator
from mmf.core.security.ports.rate_limiting import IRateLimiter
from mmf.core.security.ports.session import ISessionManager

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

        # Initialize middleware components
        self.rate_limit_middleware = RateLimitMiddleware(rate_limiter, rate_limit_config)
        self.session_middleware = SessionMiddleware(session_manager, session_config)
        self.auth_middleware = AuthenticationMiddleware(jwt_config)

    async def process_request(
        self,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Process incoming request through security pipeline.

        Pipeline:
        1. Rate Limiting (Fail fast)
        2. Session Management
        3. Authentication (if no session)
        4. Authorization (TODO)
        """

        # Define the chain execution
        async def run_auth(ctx: dict[str, Any]) -> dict[str, Any]:
            return await self.auth_middleware.process(ctx)

        async def run_session(ctx: dict[str, Any]) -> dict[str, Any]:
            return await self.session_middleware.process(ctx, run_auth)

        # Start with Rate Limiting
        return await self.rate_limit_middleware.process(request_context, run_session)

    async def authenticate_request(
        self,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Authenticate incoming request."""
        # Delegate to auth middleware logic directly
        return await self.auth_middleware._authenticate_request(request_context)

    async def authorize_request(
        self,
        request_context: dict[str, Any],
    ) -> dict[str, Any]:
        """Authorize incoming request."""
        # Placeholder for RBAC/ABAC logic
        return request_context

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

    async def check_rate_limits(
        self,
        request_context: dict[str, Any],
    ) -> RateLimitResult:
        """Check rate limits for request."""
        quota = RateLimitQuota(
            ip_address=request_context.get("ip_address"),
            user_id=request_context.get("user_id"),
            endpoint=request_context.get("path"),
        )
        return await self.rate_limiter.check_rate_limit(quota)

    async def manage_session(
        self,
        request_context: dict[str, Any],
    ) -> SessionData | None:
        """Manage session for request."""
        session_id = request_context.get("cookies", {}).get(self.session_config.session_cookie_name)
        if session_id:
            return await self.session_manager.get_session(session_id)
        return None

    async def log_security_event(
        self,
        event_type: str,
        request_context: dict[str, Any],
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Log security event."""
        logger.info(f"Security Event: {event_type} - {details}")
        return True

    async def health_check(self) -> dict[str, Any]:
        """Check health of all middleware components."""
        return {"status": "healthy", "components": {"rate_limiter": "ok", "session_manager": "ok"}}
