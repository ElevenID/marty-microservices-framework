"""
FastAPI Security Middleware Adapter

Adapter for integrating security coordinator with FastAPI/Starlette.
"""

import logging
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from mmf_new.core.security.ports.middleware import IMiddlewareCoordinator

logger = logging.getLogger(__name__)


class SecurityMiddleware(BaseHTTPMiddleware):
    """
    FastAPI middleware for security coordination.

    Delegates security logic to IMiddlewareCoordinator.
    """

    def __init__(
        self,
        app: ASGIApp,
        coordinator: IMiddlewareCoordinator,
    ):
        """
        Initialize security middleware.

        Args:
            app: ASGI application
            coordinator: Security middleware coordinator
        """
        super().__init__(app)
        self.coordinator = coordinator

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        """Process request through security pipeline."""
        # Build request context
        context = {
            "path": request.url.path,
            "method": request.method,
            "headers": dict(request.headers),
            "cookies": request.cookies,
            "ip_address": request.client.host if request.client else None,
            "query_params": dict(request.query_params),
        }

        # Process request
        try:
            processed_context = await self.coordinator.process_request(context)
        except Exception as e:
            logger.error("Security processing failed: %s", e)
            return Response(content="Internal Server Error", status_code=500)

        # Check for errors
        if "error" in processed_context:
            status_code = processed_context.get("status_code", 403)
            return Response(content=processed_context["error"], status_code=status_code)

        # Inject user/session into request state
        if "user" in processed_context:
            request.state.user = processed_context["user"]
        if "session" in processed_context:
            request.state.session = processed_context["session"]

        # Call next middleware/endpoint
        response = await call_next(request)

        # Apply security headers
        response_context = {
            "headers": dict(response.headers),
            "status_code": response.status_code,
        }

        processed_response = await self.coordinator.apply_security_headers(response_context)

        # Update response headers
        headers = processed_response.get("headers", {})
        if isinstance(headers, dict):
            for key, value in headers.items():
                response.headers[key] = value

        return response
