"""
Enhanced Correlation ID System for Marty Microservices Framework

This module extends the existing correlation ID system with enhanced propagation,
context management, and debugging capabilities for distributed systems.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from contextlib import asynccontextmanager, contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime
from typing import Any

# Third-party imports
import grpc
import httpx

# FastAPI/Starlette imports - fail if not available
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

# Framework imports
# TODO: Re-enable once grpc is migrated to mmf_new
# from mmf_new.core.grpc import ServiceRegistrationProtocol

logger = logging.getLogger(__name__)

# Context variables for correlation tracking
correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)
request_id_context: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_context: ContextVar[str | None] = ContextVar("user_id", default=None)
session_id_context: ContextVar[str | None] = ContextVar("session_id", default=None)
plugin_id_context: ContextVar[str | None] = ContextVar("plugin_id", default=None)
operation_id_context: ContextVar[str | None] = ContextVar("operation_id", default=None)

# Standard header names (MMF namespace for better identification)
CORRELATION_ID_HEADER = "X-MMF-Correlation-ID"
REQUEST_ID_HEADER = "X-MMF-Request-ID"
USER_ID_HEADER = "X-MMF-User-ID"
SESSION_ID_HEADER = "X-MMF-Session-ID"
PLUGIN_ID_HEADER = "X-MMF-Plugin-ID"
OPERATION_ID_HEADER = "X-MMF-Operation-ID"
TRACE_ID_HEADER = "X-Trace-ID"
SPAN_ID_HEADER = "X-Span-ID"


@dataclass
class CorrelationContext:
    """Enhanced correlation context with multiple tracking dimensions for plugin debugging."""

    correlation_id: str
    request_id: str | None = None
    user_id: str | None = None
    session_id: str | None = None
    plugin_id: str | None = None
    operation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_request_id: str | None = None
    service_name: str | None = None
    operation_name: str | None = None
    plugin_version: str | None = None
    custom_tags: dict[str, str] | None = None

    def to_headers(self) -> dict[str, str]:
        """Convert context to HTTP headers for propagation."""
        headers = {CORRELATION_ID_HEADER: self.correlation_id}

        if self.request_id:
            headers[REQUEST_ID_HEADER] = self.request_id
        if self.user_id:
            headers[USER_ID_HEADER] = self.user_id
        if self.session_id:
            headers[SESSION_ID_HEADER] = self.session_id
        if self.plugin_id:
            headers[PLUGIN_ID_HEADER] = self.plugin_id
        if self.operation_id:
            headers[OPERATION_ID_HEADER] = self.operation_id
        if self.trace_id:
            headers[TRACE_ID_HEADER] = self.trace_id
        if self.span_id:
            headers[SPAN_ID_HEADER] = self.span_id

        return headers

    def to_log_context(self) -> dict[str, Any]:
        """Convert context to structured logging context."""
        context = {
            "correlation_id": self.correlation_id,
            "request_id": self.request_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "plugin_id": self.plugin_id,
            "operation_id": self.operation_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_request_id": self.parent_request_id,
            "service_name": self.service_name,
            "operation_name": self.operation_name,
            "plugin_version": self.plugin_version,
        }

        # Add custom tags
        if self.custom_tags:
            for key, value in self.custom_tags.items():
                context[f"tag_{key}"] = value

        # Remove None values
        return {k: v for k, v in context.items() if v is not None}


class CorrelationManager:
    """Enhanced correlation ID manager with full context support."""

    def __init__(self, service_name: str | None = None):
        self.service_name = service_name

    def generate_correlation_id(self) -> str:
        """Generate a new correlation ID."""
        return str(uuid.uuid4())

    def generate_request_id(self) -> str:
        """Generate a new request ID."""
        return str(uuid.uuid4())

    def get_current_context(self) -> CorrelationContext | None:
        """Get current correlation context."""
        correlation_id = correlation_id_context.get()
        if not correlation_id:
            return None

        return CorrelationContext(
            correlation_id=correlation_id,
            request_id=request_id_context.get(),
            user_id=user_id_context.get(),
            session_id=session_id_context.get(),
            service_name=self.service_name,
        )

    def set_context(self, context: CorrelationContext) -> None:
        """Set the current correlation context."""
        correlation_id_context.set(context.correlation_id)
        if context.request_id:
            request_id_context.set(context.request_id)
        if context.user_id:
            user_id_context.set(context.user_id)
        if context.session_id:
            session_id_context.set(context.session_id)

    def create_context_from_headers(self, headers: dict[str, str]) -> CorrelationContext:
        """Create correlation context from HTTP headers."""
        correlation_id = headers.get(CORRELATION_ID_HEADER, self.generate_correlation_id())
        request_id = headers.get(REQUEST_ID_HEADER)
        user_id = headers.get(USER_ID_HEADER)
        session_id = headers.get(SESSION_ID_HEADER)
        trace_id = headers.get(TRACE_ID_HEADER)
        span_id = headers.get(SPAN_ID_HEADER)

        # Generate request ID if not present
        if not request_id:
            request_id = self.generate_request_id()

        return CorrelationContext(
            correlation_id=correlation_id,
            request_id=request_id,
            user_id=user_id,
            session_id=session_id,
            trace_id=trace_id,
            span_id=span_id,
            service_name=self.service_name,
        )

    @contextmanager
    def correlation_context(self, context: CorrelationContext):
        """Context manager for correlation tracking."""
        # Store current values
        old_correlation_id = correlation_id_context.get()
        old_request_id = request_id_context.get()
        old_user_id = user_id_context.get()
        old_session_id = session_id_context.get()

        try:
            # Set new context
            self.set_context(context)
            yield context
        finally:
            # Restore previous values
            correlation_id_context.set(old_correlation_id)
            request_id_context.set(old_request_id)
            user_id_context.set(old_user_id)
            session_id_context.set(old_session_id)

    @asynccontextmanager
    async def async_correlation_context(self, context: CorrelationContext):
        """Async context manager for correlation tracking."""
        with self.correlation_context(context):
            yield context

    def create_child_context(
        self, operation_name: str | None = None, **custom_tags
    ) -> CorrelationContext:
        """Create a child context for sub-operations."""
        current = self.get_current_context()
        if not current:
            # Create new context if none exists
            return CorrelationContext(
                correlation_id=self.generate_correlation_id(),
                request_id=self.generate_request_id(),
                service_name=self.service_name,
                operation_name=operation_name,
                custom_tags=custom_tags or None,
            )

        # Create child context
        return CorrelationContext(
            correlation_id=current.correlation_id,  # Keep same correlation ID
            request_id=self.generate_request_id(),  # New request ID for child
            user_id=current.user_id,
            session_id=current.session_id,
            trace_id=current.trace_id,
            span_id=current.span_id,
            parent_request_id=current.request_id,
            service_name=self.service_name,
            operation_name=operation_name,
            custom_tags=custom_tags or None,
        )


# Middleware implementations
class CorrelationMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for correlation ID management."""

    def __init__(self, app, correlation_manager: CorrelationManager):
        super().__init__(app)
        self.correlation_manager = correlation_manager

    async def dispatch(self, request: Request, call_next: Callable):
        # Extract headers
        headers = dict(request.headers)

        # Create correlation context
        context = self.correlation_manager.create_context_from_headers(headers)

        async with self.correlation_manager.async_correlation_context(context):
            # Add correlation info to request state
            request.state.correlation_context = context

            # Process request
            response = await call_next(request)

            # Add correlation headers to response
            for key, value in context.to_headers().items():
                response.headers[key] = value

            return response


class CorrelationInterceptor(grpc.ServerInterceptor):
    """gRPC server interceptor for correlation ID management."""

    def __init__(self, correlation_manager: CorrelationManager):
        self.correlation_manager = correlation_manager

    def intercept_service(self, continuation, handler_call_details):
        # Get the original handler
        handler = continuation(handler_call_details)

        if handler is None:
            return None

        def enhanced_unary_unary(request, context):
            # Extract metadata
            metadata = dict(context.invocation_metadata())

            # Create correlation context from metadata
            headers = {k.title(): v for k, v in metadata.items()}
            correlation_context = self.correlation_manager.create_context_from_headers(headers)

            # Set correlation context
            with self.correlation_manager.correlation_context(correlation_context):
                # Add context to gRPC context
                try:
                    context.set_trailing_metadata(correlation_context.to_headers().items())
                except Exception:
                    pass  # Ignore if trailing metadata cannot be set

                # Call the original handler
                if hasattr(handler, "unary_unary") and handler.unary_unary:
                    return handler.unary_unary(request, context)
                else:
                    raise grpc.RpcError("Invalid handler type")

        return grpc.unary_unary_rpc_method_handler(enhanced_unary_unary)


# Decorators for automatic correlation
def with_correlation(operation_name: str | None = None, **custom_tags):
    """Decorator for automatic correlation context management."""

    def decorator(func):
        if asyncio.iscoroutinefunction(func):

            async def async_wrapper(*args, **kwargs):
                # Try to get correlation manager from self
                correlation_manager = None
                if args and hasattr(args[0], "correlation_manager"):
                    correlation_manager = args[0].correlation_manager
                elif args and hasattr(args[0], "_correlation_manager"):
                    correlation_manager = args[0]._correlation_manager
                else:
                    # Create a default one
                    correlation_manager = CorrelationManager()

                # Create child context
                context = correlation_manager.create_child_context(operation_name, **custom_tags)

                async with correlation_manager.async_correlation_context(context):
                    return await func(*args, **kwargs)

            return async_wrapper
        else:

            def sync_wrapper(*args, **kwargs):
                # Try to get correlation manager from self
                correlation_manager = None
                if args and hasattr(args[0], "correlation_manager"):
                    correlation_manager = args[0].correlation_manager
                elif args and hasattr(args[0], "_correlation_manager"):
                    correlation_manager = args[0]._correlation_manager
                else:
                    # Create a default one
                    correlation_manager = CorrelationManager()

                # Create child context
                context = correlation_manager.create_child_context(operation_name, **custom_tags)

                with correlation_manager.correlation_context(context):
                    return func(*args, **kwargs)

            return sync_wrapper

    return decorator


# Enhanced logging filter
class EnhancedCorrelationFilter(logging.Filter):
    """Enhanced correlation filter with full context support."""

    def __init__(self, correlation_manager: CorrelationManager | None = None):
        super().__init__()
        self.correlation_manager = correlation_manager or CorrelationManager()

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation context to log record."""
        context = self.correlation_manager.get_current_context()
        if context:
            log_context = context.to_log_context()
            for key, value in log_context.items():
                setattr(record, key, value)
        else:
            # Set default values
            record.correlation_id = "unknown"  # type: ignore[attr-defined]
            record.request_id = "unknown"  # type: ignore[attr-defined]

        return True


# Utility functions
def get_correlation_id() -> str | None:
    """Get current correlation ID."""
    return correlation_id_context.get()


def get_request_id() -> str | None:
    """Get current request ID."""
    return request_id_context.get()


def get_user_id() -> str | None:
    """Get current user ID."""
    return user_id_context.get()


def get_session_id() -> str | None:
    """Get current session ID."""
    return session_id_context.get()


def set_correlation_id(correlation_id: str) -> None:
    """Set correlation ID for current context."""
    correlation_id_context.set(correlation_id)


def set_request_id(request_id: str) -> None:
    """Set request ID for current context."""
    request_id_context.set(request_id)


def set_user_id(user_id: str) -> None:
    """Set user ID for current context."""
    user_id_context.set(user_id)


def get_plugin_id() -> str | None:
    """Get current plugin ID."""
    return plugin_id_context.get()


def get_operation_id() -> str | None:
    """Get current operation ID."""
    return operation_id_context.get()


def set_plugin_id(plugin_id: str) -> None:
    """Set plugin ID for current context."""
    plugin_id_context.set(plugin_id)


def set_operation_id(operation_id: str) -> None:
    """Set operation ID for current context."""
    operation_id_context.set(operation_id)


# HTTP client helpers for correlation propagation
class CorrelationHTTPClient:
    """HTTP client wrapper that automatically propagates correlation context."""

    def __init__(self, correlation_manager: CorrelationManager):
        self.correlation_manager = correlation_manager

    def prepare_headers(self, headers: dict[str, str] | None = None) -> dict[str, str]:
        """Prepare headers with correlation context."""
        if headers is None:
            headers = {}

        context = self.correlation_manager.get_current_context()
        if context:
            headers.update(context.to_headers())

        return headers

    async def request(self, method: str, url: str, headers: dict[str, str] | None = None, **kwargs):
        """Make HTTP request with correlation propagation."""
        headers = self.prepare_headers(headers)

        # Use httpx
        async with httpx.AsyncClient() as client:
            return await client.request(method, url, headers=headers, **kwargs)


# Plugin debugging utilities
@contextmanager
def plugin_operation_context(
    plugin_id: str, operation_name: str, plugin_version: str | None = None, **custom_tags
):
    """Context manager for plugin operation debugging."""
    # Generate operation ID
    operation_id = str(uuid.uuid4())

    # Set plugin context
    original_plugin_id = get_plugin_id()
    original_operation_id = get_operation_id()

    set_plugin_id(plugin_id)
    set_operation_id(operation_id)

    # Create correlation context with plugin information
    correlation_manager = CorrelationManager()
    context = correlation_manager.create_child_context(
        operation_name=operation_name,
        plugin_id=plugin_id,
        operation_id=operation_id,
        plugin_version=plugin_version,
        **custom_tags,
    )

    try:
        with correlation_manager.correlation_context(context):
            logger.info(
                f"Starting plugin operation: {plugin_id}.{operation_name}",
                extra={
                    "plugin_id": plugin_id,
                    "operation_name": operation_name,
                    "operation_id": operation_id,
                    "plugin_version": plugin_version,
                },
            )
            yield context
            logger.info(
                f"Completed plugin operation: {plugin_id}.{operation_name}",
                extra={
                    "plugin_id": plugin_id,
                    "operation_name": operation_name,
                    "operation_id": operation_id,
                },
            )
    except Exception as e:
        logger.error(
            f"Failed plugin operation: {plugin_id}.{operation_name}",
            extra={
                "plugin_id": plugin_id,
                "operation_name": operation_name,
                "operation_id": operation_id,
                "error": str(e),
            },
        )
        raise
    finally:
        # Restore original context
        if original_plugin_id:
            set_plugin_id(original_plugin_id)
        if original_operation_id:
            set_operation_id(original_operation_id)


def trace_plugin_interaction(
    from_plugin: str, to_plugin: str, interaction_type: str = "call", **metadata
):
    """Trace interaction between plugins for debugging."""
    correlation_id = get_correlation_id() or str(uuid.uuid4())

    logger.info(
        f"Plugin interaction: {from_plugin} -> {to_plugin}",
        extra={
            "correlation_id": correlation_id,
            "from_plugin": from_plugin,
            "to_plugin": to_plugin,
            "interaction_type": interaction_type,
            "metadata": metadata,
        },
    )

    return {
        "correlation_id": correlation_id,
        "from_plugin": from_plugin,
        "to_plugin": to_plugin,
        "interaction_type": interaction_type,
        "timestamp": datetime.utcnow().isoformat(),
    }
