"""
Correlation ID middleware for distributed tracing.

This middleware automatically adds correlation IDs to requests for tracking
across microservices. Works with FastAPI and integrates with MMF logging.
"""

import uuid
from collections.abc import Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware to add correlation IDs to all requests for distributed tracing.

    This middleware:
    - Extracts correlation ID from X-Correlation-ID header
    - Generates new correlation ID if not provided
    - Adds correlation ID to request state
    - Includes correlation ID in response headers
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process request with correlation ID."""
        # Extract or generate correlation ID
        correlation_id = request.headers.get("X-Correlation-ID")
        if not correlation_id:
            correlation_id = str(uuid.uuid4())

        # Add to request state for access in route handlers
        request.state.correlation_id = correlation_id

        # Process request
        response = await call_next(request)

        # Add correlation ID to response headers
        response.headers["X-Correlation-ID"] = correlation_id

        return response


def add_correlation_id_middleware(app) -> None:
    """
    Add correlation ID middleware to the FastAPI app.

    Args:
        app: FastAPI application instance
    """
    app.add_middleware(CorrelationIdMiddleware)
