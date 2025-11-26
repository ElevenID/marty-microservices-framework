"""
Gateway middleware for request/response processing.

Provides comprehensive middleware system for API gateway including:
- Request/response transformation
- Logging and monitoring
- CORS handling
- Request validation
- Response caching
- Error handling
"""

import builtins
import json
import logging
import re
import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class MiddlewareType(Enum):
    """Middleware execution types."""

    REQUEST = "request"
    RESPONSE = "response"
    ERROR = "error"


@dataclass
class MiddlewareContext:
    """Context passed through middleware chain."""

    request_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    start_time: float = field(default_factory=time.time)
    request_data: builtins.dict[str, Any] = field(default_factory=dict)
    response_data: builtins.dict[str, Any] | None = None
    error: Exception | None = None
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    @property
    def processing_time(self) -> float:
        """Get processing time in seconds."""
        return time.time() - self.start_time


class Middleware(ABC):
    """Abstract middleware interface."""

    @abstractmethod
    async def process_request(self, context: MiddlewareContext) -> MiddlewareContext:
        """Process incoming request."""
        return context

    @abstractmethod
    async def process_response(self, context: MiddlewareContext) -> MiddlewareContext:
        """Process outgoing response."""
        return context

    @abstractmethod
    async def process_error(self, context: MiddlewareContext) -> MiddlewareContext:
        """Process error condition."""
        return context


class LoggingMiddleware(Middleware):
    """Request/response logging middleware."""

    def __init__(self, log_level: int = logging.INFO):
        self.log_level = log_level

    async def process_request(self, context: MiddlewareContext) -> MiddlewareContext:
        """Log incoming request."""
        request = context.request_data
        logger.log(
            self.log_level,
            f"[{context.request_id}] {request.get('method', 'GET')} {request.get('path', '/')} "
            f"from {request.get('client_ip', 'unknown')}",
        )
        return context

    async def process_response(self, context: MiddlewareContext) -> MiddlewareContext:
        """Log outgoing response."""
        if context.response_data:
            status = context.response_data.get("status", 0)
            logger.log(
                self.log_level,
                f"[{context.request_id}] Response {status} in {context.processing_time:.3f}s",
            )
        return context

    async def process_error(self, context: MiddlewareContext) -> MiddlewareContext:
        """Log error."""
        if context.error:
            logger.error(
                f"[{context.request_id}] Error: {context.error} in {context.processing_time:.3f}s"
            )
        return context


class CORSMiddleware(Middleware):
    """Cross-Origin Resource Sharing middleware."""

    def __init__(
        self,
        allowed_origins: builtins.list[str] = None,
        allowed_methods: builtins.list[str] = None,
        allowed_headers: builtins.list[str] = None,
        allow_credentials: bool = False,
        max_age: int = 86400,
    ):
        self.allowed_origins = allowed_origins or ["*"]
        self.allowed_methods = allowed_methods or [
            "GET",
            "POST",
            "PUT",
            "DELETE",
            "OPTIONS",
        ]
        self.allowed_headers = allowed_headers or ["*"]
        self.allow_credentials = allow_credentials
        self.max_age = max_age

    async def process_request(self, context: MiddlewareContext) -> MiddlewareContext:
        """Process CORS preflight requests."""
        request = context.request_data

        if request.get("method") == "OPTIONS":
            # Handle preflight request
            response_headers = {
                "Access-Control-Allow-Methods": ", ".join(self.allowed_methods),
                "Access-Control-Allow-Headers": ", ".join(self.allowed_headers),
                "Access-Control-Max-Age": str(self.max_age),
            }

            origin = request.get("headers", {}).get("Origin")
            if self._is_origin_allowed(origin):
                response_headers["Access-Control-Allow-Origin"] = origin

            if self.allow_credentials:
                response_headers["Access-Control-Allow-Credentials"] = "true"

            context.response_data = {
                "status": 200,
                "headers": response_headers,
                "body": "",
            }

        return context

    async def process_response(self, context: MiddlewareContext) -> MiddlewareContext:
        """Add CORS headers to response."""
        if context.response_data:
            headers = context.response_data.get("headers", {})

            origin = context.request_data.get("headers", {}).get("Origin")
            if self._is_origin_allowed(origin):
                headers["Access-Control-Allow-Origin"] = origin

            if self.allow_credentials:
                headers["Access-Control-Allow-Credentials"] = "true"

            context.response_data["headers"] = headers

        return context

    async def process_error(self, context: MiddlewareContext) -> MiddlewareContext:
        """Pass through errors."""
        return context

    def _is_origin_allowed(self, origin: str | None) -> bool:
        """Check if origin is allowed."""
        if not origin:
            return False

        if "*" in self.allowed_origins:
            return True

        return origin in self.allowed_origins


class ValidationMiddleware(Middleware):
    """Request validation middleware."""

    def __init__(self, validators: builtins.dict[str, Callable] = None):
        self.validators = validators or {}

    async def process_request(self, context: MiddlewareContext) -> MiddlewareContext:
        """Validate incoming request."""
        request = context.request_data
        path = request.get("path", "/")

        # Find matching validator
        validator = None
        for pattern, validator_func in self.validators.items():
            if re.match(pattern, path):
                validator = validator_func
                break

        if validator:
            try:
                is_valid, error_message = validator(request)
                if not is_valid:
                    context.response_data = {
                        "status": 400,
                        "headers": {"Content-Type": "application/json"},
                        "body": json.dumps({"error": error_message}),
                    }
            except Exception as e:
                logger.error(f"Validation error: {e}")
                context.response_data = {
                    "status": 400,
                    "headers": {"Content-Type": "application/json"},
                    "body": json.dumps({"error": "Invalid request"}),
                }

        return context

    async def process_response(self, context: MiddlewareContext) -> MiddlewareContext:
        """Pass through responses."""
        return context

    async def process_error(self, context: MiddlewareContext) -> MiddlewareContext:
        """Pass through errors."""
        return context


class CachingMiddleware(Middleware):
    """Response caching middleware."""

    def __init__(self, cache_backend=None, default_ttl: int = 300):
        self.cache = cache_backend
        self.default_ttl = default_ttl
        self.cacheable_methods = {"GET", "HEAD"}

    async def process_request(self, context: MiddlewareContext) -> MiddlewareContext:
        """Check cache for response."""
        if not self.cache:
            return context

        request = context.request_data
        method = request.get("method", "GET")

        if method not in self.cacheable_methods:
            return context

        cache_key = self._get_cache_key(request)

        try:
            cached_response = await self.cache.get(cache_key)
            if cached_response:
                context.response_data = json.loads(cached_response)
                context.metadata["cache_hit"] = True
        except Exception as e:
            logger.warning(f"Cache read error: {e}")

        return context

    async def process_response(self, context: MiddlewareContext) -> MiddlewareContext:
        """Cache successful responses."""
        if not self.cache or context.metadata.get("cache_hit"):
            return context

        response = context.response_data
        if not response:
            return context

        status = response.get("status", 0)
        if 200 <= status < 300:  # Only cache successful responses
            request = context.request_data
            method = request.get("method", "GET")

            if method in self.cacheable_methods:
                cache_key = self._get_cache_key(request)

                try:
                    await self.cache.set(cache_key, json.dumps(response), ttl=self.default_ttl)
                except Exception as e:
                    logger.warning(f"Cache write error: {e}")

        return context

    async def process_error(self, context: MiddlewareContext) -> MiddlewareContext:
        """Pass through errors."""
        return context

    def _get_cache_key(self, request: builtins.dict[str, Any]) -> str:
        """Generate cache key for request."""
        path = request.get("path", "/")
        query = request.get("query_params", {})

        # Sort query parameters for consistent key
        query_string = "&".join(f"{k}={v}" for k, v in sorted(query.items()))

        if query_string:
            return f"gateway_cache:{path}?{query_string}"
        return f"gateway_cache:{path}"


class MetricsMiddleware(Middleware):
    """Metrics collection middleware."""

    def __init__(self, metrics_collector=None):
        self.metrics = metrics_collector
        self.request_count = 0
        self.error_count = 0

    async def process_request(self, context: MiddlewareContext) -> MiddlewareContext:
        """Record request metrics."""
        self.request_count += 1

        if self.metrics:
            request = context.request_data
            self.metrics.increment(
                "gateway.requests.total",
                {
                    "method": request.get("method", "GET"),
                    "path": request.get("path", "/"),
                },
            )

        return context

    async def process_response(self, context: MiddlewareContext) -> MiddlewareContext:
        """Record response metrics."""
        if self.metrics and context.response_data:
            status = context.response_data.get("status", 0)

            self.metrics.increment(
                "gateway.responses.total",
                {"status": str(status), "status_class": f"{status // 100}xx"},
            )

            self.metrics.histogram("gateway.response_time", context.processing_time)

        return context

    async def process_error(self, context: MiddlewareContext) -> MiddlewareContext:
        """Record error metrics."""
        self.error_count += 1

        if self.metrics:
            self.metrics.increment("gateway.errors.total")

        return context


class TransformationMiddleware(Middleware):
    """Request/response transformation middleware."""

    def __init__(
        self,
        request_transformers: builtins.dict[str, Callable] = None,
        response_transformers: builtins.dict[str, Callable] = None,
    ):
        self.request_transformers = request_transformers or {}
        self.response_transformers = response_transformers or {}

    async def process_request(self, context: MiddlewareContext) -> MiddlewareContext:
        """Transform request."""
        request = context.request_data
        path = request.get("path", "/")

        # Find matching transformer
        for pattern, transformer in self.request_transformers.items():
            if re.match(pattern, path):
                try:
                    context.request_data = transformer(request)
                    break
                except Exception as e:
                    logger.error(f"Request transformation error: {e}")

        return context

    async def process_response(self, context: MiddlewareContext) -> MiddlewareContext:
        """Transform response."""
        if not context.response_data:
            return context

        request = context.request_data
        path = request.get("path", "/")

        # Find matching transformer
        for pattern, transformer in self.response_transformers.items():
            if re.match(pattern, path):
                try:
                    context.response_data = transformer(context.response_data)
                    break
                except Exception as e:
                    logger.error(f"Response transformation error: {e}")

        return context

    async def process_error(self, context: MiddlewareContext) -> MiddlewareContext:
        """Pass through errors."""
        return context


class SecurityMiddleware(Middleware):
    """Security headers middleware."""

    def __init__(self):
        self.security_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "X-XSS-Protection": "1; mode=block",
            "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
            "Referrer-Policy": "strict-origin-when-cross-origin",
        }

    async def process_request(self, context: MiddlewareContext) -> MiddlewareContext:
        """Pass through requests."""
        return context

    async def process_response(self, context: MiddlewareContext) -> MiddlewareContext:
        """Add security headers."""
        if context.response_data:
            headers = context.response_data.get("headers", {})
            headers.update(self.security_headers)
            context.response_data["headers"] = headers

        return context

    async def process_error(self, context: MiddlewareContext) -> MiddlewareContext:
        """Pass through errors."""
        return context


class MiddlewareChain:
    """Middleware execution chain."""

    def __init__(self):
        self.middlewares: builtins.list[Middleware] = []

    def add_middleware(self, middleware: Middleware) -> None:
        """Add middleware to chain."""
        self.middlewares.append(middleware)

    def remove_middleware(self, middleware: Middleware) -> None:
        """Remove middleware from chain."""
        if middleware in self.middlewares:
            self.middlewares.remove(middleware)

    async def process_request(self, request_data: builtins.dict[str, Any]) -> MiddlewareContext:
        """Process request through middleware chain."""
        context = MiddlewareContext(request_data=request_data)

        for middleware in self.middlewares:
            try:
                context = await middleware.process_request(context)

                # If middleware sets response, short-circuit
                if context.response_data:
                    break

            except Exception as e:
                context.error = e
                logger.error(f"Middleware error in {middleware.__class__.__name__}: {e}")
                break

        return context

    async def process_response(self, context: MiddlewareContext) -> MiddlewareContext:
        """Process response through middleware chain (reverse order)."""
        for middleware in reversed(self.middlewares):
            try:
                context = await middleware.process_response(context)
            except Exception as e:
                context.error = e
                logger.error(f"Middleware error in {middleware.__class__.__name__}: {e}")

        return context

    async def process_error(self, context: MiddlewareContext) -> MiddlewareContext:
        """Process error through middleware chain."""
        for middleware in self.middlewares:
            try:
                context = await middleware.process_error(context)
            except Exception as e:
                logger.error(f"Error middleware error in {middleware.__class__.__name__}: {e}")

        return context


# Utility functions for creating common middleware configurations
def create_standard_middleware_chain(
    enable_cors: bool = True,
    enable_logging: bool = True,
    enable_security: bool = True,
    enable_metrics: bool = True,
    cache_backend=None,
) -> MiddlewareChain:
    """Create standard middleware chain."""
    chain = MiddlewareChain()

    if enable_security:
        chain.add_middleware(SecurityMiddleware())

    if enable_cors:
        chain.add_middleware(CORSMiddleware())

    if enable_logging:
        chain.add_middleware(LoggingMiddleware())

    if cache_backend:
        chain.add_middleware(CachingMiddleware(cache_backend))

    if enable_metrics:
        chain.add_middleware(MetricsMiddleware())

    return chain


def create_api_validation_middleware(
    validators: builtins.dict[str, Callable],
) -> ValidationMiddleware:
    """Create API validation middleware."""
    return ValidationMiddleware(validators)


def create_transformation_middleware(
    request_transformers: builtins.dict[str, Callable] = None,
    response_transformers: builtins.dict[str, Callable] = None,
) -> TransformationMiddleware:
    """Create transformation middleware."""
    return TransformationMiddleware(request_transformers, response_transformers)
