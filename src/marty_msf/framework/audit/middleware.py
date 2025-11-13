"""
Middleware integration for audit logging with FastAPI and gRPC applications.

This module provides middleware components that automatically log audit events
for API requests, authentication events, and other application activities.
"""

import asyncio
import builtins
import json
import logging
import random
import time
from typing import Any

import grpc
from fastapi import FastAPI, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from grpc._server import _Context as GrpcContext
from starlette.middleware.base import RequestResponseEndpoint

from .events import AuditEventType, AuditOutcome, AuditSeverity
from .logger import AuditLogger, get_audit_logger

# FastAPI imports
try:
    FASTAPI_AVAILABLE = True
except ImportError:
    FASTAPI_AVAILABLE = False

# gRPC imports
try:
    GRPC_AVAILABLE = True
except ImportError:
    GRPC_AVAILABLE = False


logger = logging.getLogger(__name__)


class AuditMiddlewareConfig:
    """Configuration for audit middleware."""

    def __init__(self):
        # Logging control
        self.log_requests: bool = True
        self.log_responses: bool = True
        self.log_headers: bool = False
        self.log_body: bool = False
        self.log_query_params: bool = True

        # Filtering
        self.exclude_paths: builtins.list[str] = [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
        ]
        self.exclude_methods: builtins.list[str] = ["OPTIONS"]
        self.sensitive_headers: builtins.list[str] = [
            "authorization",
            "cookie",
            "x-api-key",
            "x-auth-token",
        ]
        self.max_body_size: int = 10 * 1024  # 10KB

        # Performance
        self.sample_rate: float = 1.0  # Log 100% of requests
        self.log_slow_requests: bool = True
        self.slow_request_threshold_ms: float = 1000.0

        # Security
        self.detect_anomalies: bool = True
        self.rate_limit_threshold: int = 100  # requests per minute per IP
        self.large_response_threshold: int = 1 * 1024 * 1024  # 1MB


def should_log_request(request_path: str, method: str, config: AuditMiddlewareConfig) -> bool:
    """Determine if request should be logged based on configuration."""

    # Check excluded paths
    for excluded_path in config.exclude_paths:
        if request_path.startswith(excluded_path):
            return False

    # Check excluded methods
    if method.upper() in config.exclude_methods:
        return False

    # Apply sampling rate

    if random.random() > config.sample_rate:
        return False

    return True


def extract_user_info(request_data: builtins.dict[str, Any]) -> builtins.dict[str, Any]:
    """Extract user information from request."""

    user_info = {}

    # From headers
    headers = request_data.get("headers", {})
    if "user-id" in headers:
        user_info["user_id"] = headers["user-id"]
    if "x-user-id" in headers:
        user_info["user_id"] = headers["x-user-id"]
    if "x-user-email" in headers:
        user_info["user_email"] = headers["x-user-email"]
    if "x-user-role" in headers:
        user_info["user_role"] = headers["x-user-role"]

    # From authentication token (simplified)
    auth_header = headers.get("authorization", "")
    if auth_header.startswith("Bearer "):
        # In real implementation, decode JWT token
        user_info["has_token"] = True

    return user_info


def sanitize_headers(
    headers: builtins.dict[str, str], sensitive_headers: builtins.list[str]
) -> builtins.dict[str, str]:
    """Remove or mask sensitive headers."""

    sanitized = {}
    for key, value in headers.items():
        if key.lower() in [h.lower() for h in sensitive_headers]:
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = value

    return sanitized


def sanitize_body(body: bytes, max_size: int) -> str | None:
    """Safely extract and sanitize request/response body."""

    if not body or len(body) == 0:
        return None

    if len(body) > max_size:
        return f"[TRUNCATED - {len(body)} bytes]"

    try:
        # Try to decode as text
        text = body.decode("utf-8", errors="ignore")

        # Try to parse as JSON to validate structure
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            # Not JSON, return as text if safe
            if all(ord(c) < 128 for c in text):  # ASCII only
                return text
            return f"[BINARY - {len(body)} bytes]"

    except Exception:
        return f"[UNPARSEABLE - {len(body)} bytes]"


if FASTAPI_AVAILABLE:

    class FastAPIAuditMiddleware(BaseHTTPMiddleware):
        """FastAPI middleware for audit logging."""

        def __init__(self, app: FastAPI, config: AuditMiddlewareConfig = None):
            super().__init__(app)
            self.config = config or AuditMiddlewareConfig()
            logger.info("FastAPI audit middleware initialized")

        async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
            """Process request and response with audit logging."""

            start_time = time.time()
            request_path = str(request.url.path)
            method = request.method

            # Check if we should log this request
            if not should_log_request(request_path, method, self.config):
                return await call_next(request)

            audit_logger = get_audit_logger()
            if not audit_logger:
                return await call_next(request)

            # Extract request information
            client_ip = request.client.host if request.client else "unknown"
            request.headers.get("user-agent", "")
            headers = dict(request.headers)
            query_params = dict(request.query_params)

            # Extract user information
            user_info = extract_user_info({"headers": headers})
            user_id = user_info.get("user_id")

            # Read request body if configured
            request_body = None
            if self.config.log_body:
                try:
                    body_bytes = await request.body()
                    request_body = sanitize_body(body_bytes, self.config.max_body_size)
                except Exception as e:
                    logger.warning(f"Could not read request body: {e}")

            # Process request
            try:
                response = await call_next(request)
                error_message = None

                # Determine outcome based on status code
                if response.status_code >= 400:
                    pass

            except Exception as e:
                error_message = str(e)

                # Create error response
                response = Response(
                    content=json.dumps({"error": "Internal server error"}),
                    status_code=500,
                    media_type="application/json",
                )

            # Calculate timing
            duration_ms = (time.time() - start_time) * 1000

            # Extract response information
            response_headers = dict(response.headers)
            content_length = response.headers.get("content-length")
            response_size = int(content_length) if content_length else None

            # Log the API request event
            try:
                await audit_logger.log_api_event(
                    method=method,
                    endpoint=request_path,
                    status_code=response.status_code,
                    user_id=user_id,
                    source_ip=client_ip,
                    duration_ms=duration_ms,
                    request_size=len(await request.body()) if request_body else None,
                    response_size=response_size,
                    error_message=error_message,
                )

                # Log additional details if configured
                if self.config.log_headers or self.config.log_body or self.config.log_query_params:
                    details = {}

                    if self.config.log_headers:
                        details["request_headers"] = sanitize_headers(
                            headers, self.config.sensitive_headers
                        )
                        details["response_headers"] = sanitize_headers(
                            response_headers, self.config.sensitive_headers
                        )

                    if self.config.log_query_params and query_params:
                        details["query_params"] = query_params

                    if self.config.log_body and request_body:
                        details["request_body"] = request_body

                    if details:
                        builder = audit_logger.create_event_builder()
                        event = (
                            builder.event_type(AuditEventType.API_REQUEST)
                            .action(f"{method} {request_path} - Details")
                            .severity(AuditSeverity.INFO)
                            .details(details)
                            .build()
                        )
                        await audit_logger.log_event(event)

                # Log slow requests
                if (
                    self.config.log_slow_requests
                    and duration_ms > self.config.slow_request_threshold_ms
                ):
                    await audit_logger.log_system_event(
                        AuditEventType.PERFORMANCE_ISSUE,
                        f"Slow API request: {method} {request_path} took {duration_ms:.2f}ms",
                        severity=AuditSeverity.MEDIUM,
                        details={
                            "method": method,
                            "endpoint": request_path,
                            "duration_ms": duration_ms,
                            "user_id": user_id,
                            "source_ip": client_ip,
                        },
                    )

                # Detect potential security issues
                if self.config.detect_anomalies:
                    await self._detect_anomalies(
                        audit_logger,
                        method,
                        request_path,
                        client_ip,
                        user_id,
                        response.status_code,
                        duration_ms,
                        response_size,
                    )

            except Exception as e:
                logger.error(f"Failed to log audit event: {e}")

            return response

        async def _detect_anomalies(
            self,
            audit_logger: AuditLogger,
            method: str,
            path: str,
            client_ip: str,
            user_id: str | None,
            status_code: int,
            duration_ms: float,
            response_size: int | None,
        ) -> None:
            """Detect potential security anomalies."""

            # Large response size (potential data exfiltration)
            if response_size and response_size > self.config.large_response_threshold:
                await audit_logger.log_security_event(
                    AuditEventType.SECURITY_VIOLATION,
                    f"Large response detected: {response_size} bytes",
                    severity=AuditSeverity.MEDIUM,
                    source_ip=client_ip,
                    user_id=user_id,
                    details={
                        "method": method,
                        "endpoint": path,
                        "response_size": response_size,
                        "threshold": self.config.large_response_threshold,
                    },
                )

            # Multiple authentication failures
            if status_code == 401:
                # This would require maintaining state/cache
                # For now, just log the failure
                await audit_logger.log_security_event(
                    AuditEventType.AUTH_FAILURE,
                    f"Authentication failure from {client_ip}",
                    severity=AuditSeverity.MEDIUM,
                    source_ip=client_ip,
                    user_id=user_id,
                    details={
                        "method": method,
                        "endpoint": path,
                        "status_code": status_code,
                    },
                )


if GRPC_AVAILABLE:

    class GRPCAuditInterceptor(grpc.ServerInterceptor):
        """gRPC server interceptor for audit logging."""

        def __init__(self, config: AuditMiddlewareConfig = None):
            self.config = config or AuditMiddlewareConfig()
            logger.info("gRPC audit interceptor initialized")

        def intercept_service(self, continuation, handler_call_details):
            """Intercept gRPC service calls."""

            # Get audit logger
            audit_logger = get_audit_logger()
            if not audit_logger:
                return continuation(handler_call_details)

            # Extract method information
            method_name = handler_call_details.method

            # Create wrapper for the handler
            def audit_wrapper(request, context: GrpcContext):
                start_time = time.time()

                # Extract client information
                client_ip = "unknown"
                user_id = None

                # Get metadata
                metadata = dict(context.invocation_metadata())

                # Extract user info from metadata
                user_info = extract_user_info({"headers": metadata})
                user_id = user_info.get("user_id")

                if "x-forwarded-for" in metadata:
                    client_ip = metadata["x-forwarded-for"]
                elif hasattr(context, "peer") and context.peer():
                    client_ip = context.peer()

                try:
                    # Call the actual handler
                    handler = continuation(handler_call_details)
                    response = handler(request, context)

                    # Calculate timing
                    duration_ms = (time.time() - start_time) * 1000

                    # Determine outcome
                    outcome = AuditOutcome.SUCCESS
                    error_message = None

                    # Check if context has error
                    if hasattr(context, "_state") and context._state.code is not None:
                        if context._state.code != grpc.StatusCode.OK:
                            outcome = AuditOutcome.FAILURE
                            error_message = context._state.details

                    # Log the gRPC call
                    asyncio.create_task(
                        self._log_grpc_event(
                            audit_logger,
                            method_name,
                            client_ip,
                            user_id,
                            duration_ms,
                            outcome,
                            error_message,
                            metadata,
                        )
                    )

                    return response

                except Exception as e:
                    duration_ms = (time.time() - start_time) * 1000

                    # Log the error
                    asyncio.create_task(
                        self._log_grpc_event(
                            audit_logger,
                            method_name,
                            client_ip,
                            user_id,
                            duration_ms,
                            AuditOutcome.ERROR,
                            str(e),
                            metadata,
                        )
                    )

                    raise

            return audit_wrapper

        async def _log_grpc_event(
            self,
            audit_logger: AuditLogger,
            method_name: str,
            client_ip: str,
            user_id: str | None,
            duration_ms: float,
            outcome: AuditOutcome,
            error_message: str | None,
            metadata: builtins.dict[str, str],
        ) -> None:
            """Log gRPC audit event."""

            try:
                severity = (
                    AuditSeverity.INFO if outcome == AuditOutcome.SUCCESS else AuditSeverity.MEDIUM
                )

                builder = (
                    audit_logger.create_event_builder()
                    .event_type(AuditEventType.API_REQUEST)
                    .action(f"gRPC {method_name}")
                    .outcome(outcome)
                    .severity(severity)
                    .request(source_ip=client_ip, method="gRPC", endpoint=method_name)
                    .performance(duration_ms)
                )

                if user_id:
                    builder.user(user_id)

                if error_message:
                    builder.error(error_message=error_message)

                # Add metadata details if configured
                if self.config.log_headers:
                    sanitized_metadata = sanitize_headers(metadata, self.config.sensitive_headers)
                    builder.detail("metadata", sanitized_metadata)

                await audit_logger.log_event(builder.build())

                # Log slow requests
                if (
                    self.config.log_slow_requests
                    and duration_ms > self.config.slow_request_threshold_ms
                ):
                    await audit_logger.log_system_event(
                        AuditEventType.PERFORMANCE_ISSUE,
                        f"Slow gRPC call: {method_name} took {duration_ms:.2f}ms",
                        severity=AuditSeverity.MEDIUM,
                        details={
                            "method": method_name,
                            "duration_ms": duration_ms,
                            "user_id": user_id,
                            "source_ip": client_ip,
                        },
                    )

            except Exception as e:
                logger.error(f"Failed to log gRPC audit event: {e}")


def setup_fastapi_audit_middleware(app: FastAPI, config: AuditMiddlewareConfig = None) -> None:
    """Setup FastAPI audit middleware."""

    if not FASTAPI_AVAILABLE:
        logger.warning("FastAPI not available, skipping audit middleware setup")
        return

    middleware = FastAPIAuditMiddleware(app, config)
    app.add_middleware(BaseHTTPMiddleware, dispatch=middleware.dispatch)
    logger.info("FastAPI audit middleware added")


def setup_grpc_audit_interceptor(server, config: AuditMiddlewareConfig = None):
    """Setup gRPC audit interceptor."""

    if not GRPC_AVAILABLE:
        logger.warning("gRPC not available, skipping audit interceptor setup")
        return

    interceptor = GRPCAuditInterceptor(config)
    server.add_interceptor(interceptor)
    logger.info("gRPC audit interceptor added")


# Import asyncio at module level for gRPC usage
