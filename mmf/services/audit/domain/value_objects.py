"""Value objects for the audit domain."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(frozen=True)
class RequestContext:
    """Immutable request context information."""

    method: str
    endpoint: str
    source_ip: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    query_params: dict[str, Any] | None = None
    headers: dict[str, str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "method": self.method,
            "endpoint": self.endpoint,
            "source_ip": self.source_ip,
            "user_agent": self.user_agent,
            "request_id": self.request_id,
            "correlation_id": self.correlation_id,
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "query_params": self.query_params,
            "headers": self.headers,
        }


@dataclass(frozen=True)
class ResponseMetadata:
    """Immutable response metadata."""

    status_code: int
    response_size: int | None = None
    headers: dict[str, str] | None = None
    error_code: str | None = None
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status_code": self.status_code,
            "response_size": self.response_size,
            "headers": self.headers,
            "error_code": self.error_code,
            "error_message": self.error_message,
        }


@dataclass(frozen=True)
class PerformanceMetrics:
    """Immutable performance metrics."""

    duration_ms: float
    started_at: datetime
    completed_at: datetime
    is_slow_request: bool = False
    is_large_response: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "duration_ms": self.duration_ms,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
            "is_slow_request": self.is_slow_request,
            "is_large_response": self.is_large_response,
        }


@dataclass(frozen=True)
class ActorInfo:
    """Immutable actor (user/service) information."""

    user_id: str | None = None
    username: str | None = None
    session_id: str | None = None
    api_key_id: str | None = None
    client_id: str | None = None
    roles: tuple[str, ...] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "user_id": self.user_id,
            "username": self.username,
            "session_id": self.session_id,
            "api_key_id": self.api_key_id,
            "client_id": self.client_id,
            "roles": list(self.roles) if self.roles else None,
        }


@dataclass(frozen=True)
class ResourceInfo:
    """Immutable resource information."""

    resource_type: str
    resource_id: str | None = None
    action: str = ""
    attributes: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "resource_type": self.resource_type,
            "resource_id": self.resource_id,
            "action": self.action,
            "attributes": self.attributes,
        }


@dataclass(frozen=True)
class ServiceContext:
    """Immutable service context information."""

    service_name: str
    environment: str
    version: str
    instance_id: str

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "service_name": self.service_name,
            "environment": self.environment,
            "version": self.version,
            "instance_id": self.instance_id,
        }
