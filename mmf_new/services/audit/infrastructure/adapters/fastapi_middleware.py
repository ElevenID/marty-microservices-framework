"""FastAPI middleware adapter for audit logging."""

import json
import logging
import random
import time
import uuid
from typing import Any

from fastapi import FastAPI, Request, Response
from fastapi.middleware.base import BaseHTTPMiddleware
from starlette.middleware.base import RequestResponseEndpoint

from mmf_new.core.domain.audit_types import AuditEventType, AuditOutcome, AuditSeverity
from mmf_new.services.audit.application.commands import LogRequestCommand
from mmf_new.services.audit.domain.contracts import IMiddlewareAuditor
from mmf_new.services.audit.service_factory import AuditService

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
        self.exclude_paths: list[str] = [
            "/health",
            "/metrics",
            "/docs",
            "/openapi.json",
        ]
        self.exclude_methods: list[str] = ["OPTIONS"]
        self.sensitive_headers: list[str] = [
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


class FastAPIAuditMiddleware(BaseHTTPMiddleware):
    """FastAPI middleware for audit logging using hexagonal architecture."""

    def __init__(
        self,
        app: FastAPI,
        audit_service: AuditService,
        config: AuditMiddlewareConfig | None = None,
    ):
        """Initialize FastAPI audit middleware.

        Args:
            app: FastAPI application
            audit_service: Audit service instance
            config: Middleware configuration
        """
        super().__init__(app)
        self.audit_service = audit_service
        self.config = config or AuditMiddlewareConfig()
        logger.info("FastAPI audit middleware initialized")

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Process request and response with audit logging.

        Args:
            request: FastAPI request
            call_next: Next middleware/handler

        Returns:
            Response
        """
        start_time = time.time()
        request_path = str(request.url.path)
        method = request.method

        # Check if we should log this request
        if not self._should_log_request(request_path, method):
            return await call_next(request)

        # Generate correlation ID for this request
        correlation_id = str(uuid.uuid4())
        request_id = request.headers.get("x-request-id", correlation_id)

        # Extract request information
        client_ip = request.client.host if request.client else "unknown"
        user_agent = request.headers.get("user-agent", "")
        headers = dict(request.headers)
        query_params = dict(request.query_params)

        # Extract user information
        user_info = self._extract_user_info(headers)

        # Read request body if configured
        request_body = None
        if self.config.log_body:
            try:
                body_bytes = await request.body()
                request_body = self._sanitize_body(body_bytes)
            except Exception as e:
                logger.warning("Could not read request body: %s", e)

        # Process request
        error_message = None
        try:
            response = await call_next(request)
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

        # Determine severity and outcome
        severity = self._determine_severity(response.status_code, duration_ms, error_message)
        outcome = self._determine_outcome(response.status_code, error_message)

        # Build audit command
        command = LogRequestCommand(
            event_type=AuditEventType.API_REQUEST,
            severity=severity,
            outcome=outcome,
            message=f"{method} {request_path}",
            method=method,
            endpoint=request_path,
            source_ip=client_ip,
            user_agent=user_agent,
            request_id=request_id,
            correlation_id=correlation_id,
            user_id=user_info.get("user_id"),
            username=user_info.get("username"),
            session_id=user_info.get("session_id"),
            status_code=response.status_code,
            response_size=response_size,
            duration_ms=duration_ms,
            details=self._build_details(
                headers, response_headers, query_params, request_body, error_message
            ),
        )

        # Log the audit event
        try:
            audit_response = await self.audit_service.log_request(command)
            logger.debug("Logged audit event: %s", audit_response.event_id)

            # Log additional events for anomalies
            if self.config.detect_anomalies:
                await self._detect_and_log_anomalies(
                    method,
                    request_path,
                    client_ip,
                    user_info.get("user_id"),
                    response.status_code,
                    duration_ms,
                    response_size,
                )

        except Exception as e:
            logger.error("Failed to log audit event: %s", e, exc_info=True)

        return response

    def _should_log_request(self, request_path: str, method: str) -> bool:
        """Determine if request should be logged.

        Args:
            request_path: Request path
            method: HTTP method

        Returns:
            True if should log
        """
        # Check excluded paths
        for excluded_path in self.config.exclude_paths:
            if request_path.startswith(excluded_path):
                return False

        # Check excluded methods
        if method.upper() in self.config.exclude_methods:
            return False

        # Apply sampling rate
        if random.random() > self.config.sample_rate:
            return False

        return True

    def _extract_user_info(self, headers: dict[str, str]) -> dict[str, Any]:
        """Extract user information from headers.

        Args:
            headers: Request headers

        Returns:
            User information dictionary
        """
        user_info = {}

        # Standard user headers
        if "user-id" in headers:
            user_info["user_id"] = headers["user-id"]
        if "x-user-id" in headers:
            user_info["user_id"] = headers["x-user-id"]
        if "x-user-name" in headers:
            user_info["username"] = headers["x-user-name"]
        if "x-session-id" in headers:
            user_info["session_id"] = headers["x-session-id"]

        return user_info

    def _sanitize_headers(self, headers: dict[str, str]) -> dict[str, str]:
        """Remove or mask sensitive headers.

        Args:
            headers: Headers to sanitize

        Returns:
            Sanitized headers
        """
        sanitized = {}
        for key, value in headers.items():
            if key.lower() in [h.lower() for h in self.config.sensitive_headers]:
                sanitized[key] = "[REDACTED]"
            else:
                sanitized[key] = value
        return sanitized

    def _sanitize_body(self, body: bytes) -> str | None:
        """Safely extract and sanitize request body.

        Args:
            body: Request body bytes

        Returns:
            Sanitized body string or None
        """
        if not body or len(body) == 0:
            return None

        if len(body) > self.config.max_body_size:
            return f"[TRUNCATED - {len(body)} bytes]"

        try:
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
            return f"[UNPARSABLE - {len(body)} bytes]"

    def _determine_severity(
        self, status_code: int, duration_ms: float, error_message: str | None
    ) -> AuditSeverity:
        """Determine event severity based on response.

        Args:
            status_code: HTTP status code
            duration_ms: Request duration
            error_message: Error message if any

        Returns:
            Audit severity level
        """
        if error_message or status_code >= 500:
            return AuditSeverity.HIGH
        elif status_code >= 400:
            return AuditSeverity.MEDIUM
        elif duration_ms > self.config.slow_request_threshold_ms:
            return AuditSeverity.MEDIUM
        else:
            return AuditSeverity.INFO

    def _determine_outcome(self, status_code: int, error_message: str | None) -> AuditOutcome:
        """Determine event outcome based on response.

        Args:
            status_code: HTTP status code
            error_message: Error message if any

        Returns:
            Audit outcome
        """
        if error_message:
            return AuditOutcome.ERROR
        elif status_code >= 400:
            return AuditOutcome.FAILURE
        else:
            return AuditOutcome.SUCCESS

    def _build_details(
        self,
        headers: dict[str, str],
        response_headers: dict[str, str],
        query_params: dict[str, str],
        request_body: str | None,
        error_message: str | None,
    ) -> dict[str, Any]:
        """Build details dictionary for audit event.

        Args:
            headers: Request headers
            response_headers: Response headers
            query_params: Query parameters
            request_body: Request body
            error_message: Error message if any

        Returns:
            Details dictionary
        """
        details = {}

        if self.config.log_headers:
            details["request_headers"] = self._sanitize_headers(headers)
            details["response_headers"] = self._sanitize_headers(response_headers)

        if self.config.log_query_params and query_params:
            details["query_params"] = query_params

        if self.config.log_body and request_body:
            details["request_body"] = request_body

        if error_message:
            details["error_message"] = error_message

        return details

    async def _detect_and_log_anomalies(
        self,
        method: str,
        path: str,
        client_ip: str,
        user_id: str | None,
        status_code: int,
        duration_ms: float,
        response_size: int | None,
    ) -> None:
        """Detect and log potential security anomalies.

        Args:
            method: HTTP method
            path: Request path
            client_ip: Client IP address
            user_id: User ID if available
            status_code: Response status code
            duration_ms: Request duration
            response_size: Response size in bytes
        """
        try:
            # Large response size (potential data exfiltration)
            if response_size and response_size > self.config.large_response_threshold:
                command = LogRequestCommand(
                    event_type=AuditEventType.SECURITY_POLICY_VIOLATION,
                    severity=AuditSeverity.HIGH,
                    outcome=AuditOutcome.SUCCESS,
                    message=f"Large response detected: {response_size} bytes",
                    method=method,
                    endpoint=path,
                    source_ip=client_ip,
                    user_id=user_id,
                    details={
                        "response_size": response_size,
                        "threshold": self.config.large_response_threshold,
                        "anomaly_type": "large_response",
                    },
                )
                await self.audit_service.log_request(command)

            # Multiple authentication failures would require state tracking
            # For now, just log individual failures
            if status_code == 401:
                command = LogRequestCommand(
                    event_type=AuditEventType.AUTH_LOGIN_FAILURE,
                    severity=AuditSeverity.MEDIUM,
                    outcome=AuditOutcome.FAILURE,
                    message=f"Authentication failed for {method} {path}",
                    method=method,
                    endpoint=path,
                    source_ip=client_ip,
                    user_id=user_id,
                    status_code=status_code,
                )
                await self.audit_service.log_request(command)

        except Exception as e:
            logger.error("Failed to log anomaly: %s", e, exc_info=True)


class MiddlewareAuditor(IMiddlewareAuditor):
    """Middleware auditor implementation."""

    def __init__(self, audit_service: AuditService):
        """Initialize middleware auditor.

        Args:
            audit_service: Audit service instance
        """
        self.audit_service = audit_service
        self._active_requests: dict[str, dict[str, Any]] = {}

    async def audit_request_start(
        self,
        request_id: str,
        method: str,
        endpoint: str,
        **kwargs,
    ) -> str:
        """Audit the start of a request.

        Args:
            request_id: Request identifier
            method: HTTP method
            endpoint: Request endpoint
            **kwargs: Additional request attributes

        Returns:
            Audit event ID
        """
        # Store request start info
        self._active_requests[request_id] = {
            "method": method,
            "endpoint": endpoint,
            "start_time": time.time(),
            **kwargs,
        }

        command = LogRequestCommand(
            event_type=AuditEventType.MIDDLEWARE_REQUEST_START,
            severity=AuditSeverity.INFO,
            outcome=AuditOutcome.SUCCESS,
            message=f"Request started: {method} {endpoint}",
            method=method,
            endpoint=endpoint,
            request_id=request_id,
            **kwargs,
        )

        response = await self.audit_service.log_request(command)
        return str(response.event_id)

    async def audit_request_end(
        self,
        request_id: str,
        status_code: int,
        duration_ms: float,
        **kwargs,
    ) -> str:
        """Audit the end of a request.

        Args:
            request_id: Request identifier
            status_code: Response status code
            duration_ms: Request duration
            **kwargs: Additional response attributes

        Returns:
            Audit event ID
        """
        # Get request start info
        request_info = self._active_requests.pop(request_id, {})

        command = LogRequestCommand(
            event_type=AuditEventType.MIDDLEWARE_REQUEST_END,
            severity=AuditSeverity.INFO,
            outcome=AuditOutcome.SUCCESS if status_code < 400 else AuditOutcome.FAILURE,
            message=f"Request completed: {request_info.get('method', 'UNKNOWN')} "
            f"{request_info.get('endpoint', 'UNKNOWN')}",
            method=request_info.get("method"),
            endpoint=request_info.get("endpoint"),
            request_id=request_id,
            status_code=status_code,
            duration_ms=duration_ms,
            **kwargs,
        )

        response = await self.audit_service.log_request(command)
        return str(response.event_id)

    async def audit_error(
        self,
        request_id: str,
        error_message: str,
        **kwargs,
    ) -> str:
        """Audit an error during request processing.

        Args:
            request_id: Request identifier
            error_message: Error message
            **kwargs: Additional error attributes

        Returns:
            Audit event ID
        """
        # Get request start info
        request_info = self._active_requests.get(request_id, {})

        command = LogRequestCommand(
            event_type=AuditEventType.MIDDLEWARE_ERROR,
            severity=AuditSeverity.HIGH,
            outcome=AuditOutcome.ERROR,
            message=f"Middleware error: {error_message}",
            method=request_info.get("method"),
            endpoint=request_info.get("endpoint"),
            request_id=request_id,
            details={"error_message": error_message, **kwargs},
        )

        response = await self.audit_service.log_request(command)
        return str(response.event_id)
