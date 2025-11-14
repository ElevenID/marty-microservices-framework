"""
Standard Correlation ID System for MMF

This module provides unified correlation ID tracking across all MMF services,
replacing multiple implementations with a single, standardized approach.
It integrates with the StandardObservability system and provides middleware
for both FastAPI and gRPC services.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from contextvars import ContextVar
from typing import Any, Optional

import grpc
from fastapi import Request, Response
from grpc import ServicerContext
from opentelemetry import trace
from starlette.middleware.base import BaseHTTPMiddleware

# TODO: Re-enable once grpc is migrated to mmf_new
# from mmf_new.core.grpc import ServiceDefinition

logger = logging.getLogger(__name__)

# Context variables for correlation tracking
_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_user_id: ContextVar[str | None] = ContextVar("user_id", default=None)
_session_id: ContextVar[str | None] = ContextVar("session_id", default=None)
_operation_id: ContextVar[str | None] = ContextVar("operation_id", default=None)
_plugin_id: ContextVar[str | None] = ContextVar("plugin_id", default=None)

# Standard headers for correlation
STANDARD_HEADERS = {
    "correlation_id": "x-mmf-correlation-id",
    "request_id": "x-mmf-request-id",
    "user_id": "x-mmf-user-id",
    "session_id": "x-mmf-session-id",
    "operation_id": "x-mmf-operation-id",
    "plugin_id": "x-mmf-plugin-id",
}


class CorrelationContext:
    """Standard correlation context for all MMF services."""

    @staticmethod
    def get_correlation_id() -> str | None:
        """Get current correlation ID."""
        return _correlation_id.get()

    @staticmethod
    def set_correlation_id(value: str) -> None:
        """Set correlation ID."""
        _correlation_id.set(value)

    @staticmethod
    def get_request_id() -> str | None:
        """Get current request ID."""
        return _request_id.get()

    @staticmethod
    def set_request_id(value: str) -> None:
        """Set request ID."""
        _request_id.set(value)

    @staticmethod
    def get_user_id() -> str | None:
        """Get current user ID."""
        return _user_id.get()

    @staticmethod
    def set_user_id(value: str) -> None:
        """Set user ID."""
        _user_id.set(value)

    @staticmethod
    def get_session_id() -> str | None:
        """Get current session ID."""
        return _session_id.get()

    @staticmethod
    def set_session_id(value: str) -> None:
        """Set session ID."""
        _session_id.set(value)

    @staticmethod
    def get_operation_id() -> str | None:
        """Get current operation ID."""
        return _operation_id.get()

    @staticmethod
    def set_operation_id(value: str) -> None:
        """Set operation ID."""
        _operation_id.set(value)

    @staticmethod
    def get_plugin_id() -> str | None:
        """Get current plugin ID."""
        return _plugin_id.get()

    @staticmethod
    def set_plugin_id(value: str) -> None:
        """Set plugin ID."""
        _plugin_id.set(value)

    @staticmethod
    def get_all() -> dict[str, str | None]:
        """Get all correlation values."""
        return {
            "correlation_id": CorrelationContext.get_correlation_id(),
            "request_id": CorrelationContext.get_request_id(),
            "user_id": CorrelationContext.get_user_id(),
            "session_id": CorrelationContext.get_session_id(),
            "operation_id": CorrelationContext.get_operation_id(),
            "plugin_id": CorrelationContext.get_plugin_id(),
        }

    @staticmethod
    def set_from_headers(headers: dict[str, str]) -> None:
        """Set correlation values from headers."""
        for key, header in STANDARD_HEADERS.items():
            value = headers.get(header) or headers.get(header.lower())
            if value:
                getattr(CorrelationContext, f"set_{key}")(value)

    @staticmethod
    def to_headers() -> dict[str, str]:
        """Convert correlation values to headers."""
        headers = {}
        for key, header in STANDARD_HEADERS.items():
            value = getattr(CorrelationContext, f"get_{key}")()
            if value:
                headers[header] = value
        return headers

    @staticmethod
    def ensure_correlation_id() -> str:
        """Ensure correlation ID exists, creating one if needed."""
        correlation_id = CorrelationContext.get_correlation_id()
        if not correlation_id:
            correlation_id = str(uuid.uuid4())
            CorrelationContext.set_correlation_id(correlation_id)
        return correlation_id


# FastAPI Middleware


class StandardCorrelationMiddleware(BaseHTTPMiddleware):
    """Standard correlation middleware for FastAPI applications."""

    async def dispatch(self, request: Request, call_next):
        """Process request with correlation tracking."""
        # Extract correlation values from headers
        headers = dict(request.headers)
        CorrelationContext.set_from_headers(headers)

        # Ensure correlation ID exists
        CorrelationContext.ensure_correlation_id()

        # Generate request ID if not provided
        if not CorrelationContext.get_request_id():
            CorrelationContext.set_request_id(str(uuid.uuid4()))

        # Process request
        response = await call_next(request)

        # Add correlation headers to response
        correlation_headers = CorrelationContext.to_headers()
        for header, value in correlation_headers.items():
            response.headers[header] = value

        return response


# gRPC Interceptor

# Framework imports


class StandardCorrelationInterceptor(grpc.ServerInterceptor):
    """Standard correlation interceptor for gRPC services."""

    def intercept_service(self, continuation, handler_call_details):
        """Intercept gRPC service calls for correlation tracking."""

        def wrapper(behavior):
            def new_behavior(request, context: ServicerContext):
                # Extract correlation values from metadata
                metadata = dict(context.invocation_metadata())
                CorrelationContext.set_from_headers(metadata)

                # Ensure correlation ID exists
                CorrelationContext.ensure_correlation_id()

                # Generate request ID if not provided
                if not CorrelationContext.get_request_id():
                    CorrelationContext.set_request_id(str(uuid.uuid4()))

                try:
                    # Process request
                    return behavior(request, context)
                finally:
                    # Add correlation headers to trailing metadata
                    correlation_headers = CorrelationContext.to_headers()
                    trailing_metadata = [
                        (header, value)
                        for header, value in correlation_headers.items()
                        if value is not None
                    ]
                    if trailing_metadata:
                        context.set_trailing_metadata(trailing_metadata)

            return new_behavior

        return wrapper(continuation(handler_call_details))


# Context manager for correlation tracking
class correlation_context:
    """Context manager for setting correlation values."""

    def __init__(self, **kwargs):
        self.values = kwargs
        self.tokens = {}

    def __enter__(self):
        """Set correlation values."""
        for key, value in self.values.items():
            if hasattr(CorrelationContext, f"set_{key}"):
                current_value = getattr(CorrelationContext, f"get_{key}")()
                self.tokens[key] = current_value
                getattr(CorrelationContext, f"set_{key}")(value)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Restore previous correlation values."""
        for key, value in self.tokens.items():
            if value is not None:
                getattr(CorrelationContext, f"set_{key}")(value)


# Async context manager for correlation tracking
class async_correlation_context:
    """Async context manager for setting correlation values."""

    def __init__(self, **kwargs):
        self.values = kwargs
        self.tokens = {}

    async def __aenter__(self):
        """Set correlation values."""
        for key, value in self.values.items():
            if hasattr(CorrelationContext, f"set_{key}"):
                current_value = getattr(CorrelationContext, f"get_{key}")()
                self.tokens[key] = current_value
                getattr(CorrelationContext, f"set_{key}")(value)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Restore previous correlation values."""
        for key, value in self.tokens.items():
            if value is not None:
                getattr(CorrelationContext, f"set_{key}")(value)


# Logging formatter for correlation
class CorrelationFormatter(logging.Formatter):
    """Logging formatter that includes correlation information."""

    def format(self, record):
        """Format log record with correlation information."""
        # Add correlation information to log record
        correlation_data = CorrelationContext.get_all()
        for key, value in correlation_data.items():
            if value:
                setattr(record, key, value)

        return super().format(record)


# Plugin developer utilities
def get_current_correlation() -> dict[str, str | None]:
    """Get current correlation context for plugin developers."""
    return CorrelationContext.get_all()


def set_plugin_correlation(plugin_id: str, operation_id: str | None = None) -> None:
    """Set correlation context for plugin operations."""
    CorrelationContext.set_plugin_id(plugin_id)
    if operation_id:
        CorrelationContext.set_operation_id(operation_id)


def clear_correlation() -> None:
    """Clear all correlation context."""
    CorrelationContext.set_correlation_id(None)
    CorrelationContext.set_request_id(None)
    CorrelationContext.set_user_id(None)
    CorrelationContext.set_session_id(None)
    CorrelationContext.set_operation_id(None)
    CorrelationContext.set_plugin_id(None)


# Integration with OpenTelemetry


def inject_correlation_to_span(span: Any | None = None) -> None:
    """Inject correlation information into OpenTelemetry span."""
    if span is None:
        span = trace.get_current_span()

    if span and span.is_recording():
        correlation_data = CorrelationContext.get_all()
        for key, value in correlation_data.items():
            if value:
                span.set_attribute(f"mmf.correlation.{key}", value)


# Export public API
__all__ = [
    "CorrelationContext",
    "StandardCorrelationMiddleware",
    "StandardCorrelationInterceptor",
    "correlation_context",
    "async_correlation_context",
    "CorrelationFormatter",
    "get_current_correlation",
    "set_plugin_correlation",
    "clear_correlation",
    "inject_correlation_to_span",
    "STANDARD_HEADERS",
]
