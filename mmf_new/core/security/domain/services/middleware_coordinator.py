"""
Security Middleware Coordinator

Implementation of IMiddlewareCoordinator for coordinating security components.
"""

import logging
from typing import Any

from mmf_new.core.security.domain.config import (
    JWTConfig,
    RateLimitConfig,
    SessionConfig,
)
from mmf_new.core.security.domain.services.middleware.authentication import (
    AuthenticationMiddleware,
)
from mmf_new.core.security.domain.services.middleware.rate_limit import (
    RateLimitMiddleware,
)
from mmf_new.core.security.domain.services.middleware.session import SessionMiddleware
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
