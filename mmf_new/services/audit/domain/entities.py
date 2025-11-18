"""Domain entities for the audit service."""

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from mmf_new.core.domain.audit_types import AuditEventType, AuditOutcome, AuditSeverity
from mmf_new.core.domain.entity import AggregateRoot

from .value_objects import (
    ActorInfo,
    PerformanceMetrics,
    RequestContext,
    ResourceInfo,
    ResponseMetadata,
    ServiceContext,
)


class RequestAuditEvent(AggregateRoot):
    """Request audit event aggregate root."""

    def __init__(
        self,
        event_id: UUID | None = None,
        event_type: AuditEventType = AuditEventType.API_REQUEST,
        severity: AuditSeverity = AuditSeverity.INFO,
        outcome: AuditOutcome = AuditOutcome.SUCCESS,
        timestamp: datetime | None = None,
        message: str = "",
        request_context: RequestContext | None = None,
        response_metadata: ResponseMetadata | None = None,
        performance_metrics: PerformanceMetrics | None = None,
        actor_info: ActorInfo | None = None,
        resource_info: ResourceInfo | None = None,
        service_context: ServiceContext | None = None,
        details: dict[str, Any] | None = None,
        encrypted_fields: list[str] | None = None,
        security_event_id: str | None = None,
        created_at: datetime | None = None,
        updated_at: datetime | None = None,
    ):
        """Initialize request audit event.

        Args:
            event_id: Unique identifier for the event
            event_type: Type of audit event
            severity: Severity level of the event
            outcome: Outcome of the event
            timestamp: When the event occurred
            message: Human-readable message
            request_context: Request context information
            response_metadata: Response metadata
            performance_metrics: Performance metrics
            actor_info: Actor (user/service) information
            resource_info: Resource information
            service_context: Service context
            details: Additional details
            encrypted_fields: List of encrypted field names
            security_event_id: Correlation ID for high-severity events forwarded to audit_compliance
            created_at: Creation timestamp
            updated_at: Update timestamp
        """
        super().__init__(event_id, created_at, updated_at)
        self.event_type = event_type
        self.severity = severity
        self.outcome = outcome
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.message = message
        self.request_context = request_context
        self.response_metadata = response_metadata
        self.performance_metrics = performance_metrics
        self.actor_info = actor_info
        self.resource_info = resource_info
        self.service_context = service_context
        self.details = details or {}
        self.encrypted_fields = encrypted_fields or []
        self.security_event_id = security_event_id

    def should_forward_to_compliance(self) -> bool:
        """Check if event should be forwarded to audit_compliance.

        Returns:
            True if severity is HIGH or CRITICAL
        """
        return self.severity in (AuditSeverity.HIGH, AuditSeverity.CRITICAL)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        base_dict = super().to_dict()
        return {
            **base_dict,
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "outcome": self.outcome.value,
            "timestamp": self.timestamp.isoformat(),
            "message": self.message,
            "request_context": self.request_context.to_dict() if self.request_context else None,
            "response_metadata": (
                self.response_metadata.to_dict() if self.response_metadata else None
            ),
            "performance_metrics": (
                self.performance_metrics.to_dict() if self.performance_metrics else None
            ),
            "actor_info": self.actor_info.to_dict() if self.actor_info else None,
            "resource_info": self.resource_info.to_dict() if self.resource_info else None,
            "service_context": self.service_context.to_dict() if self.service_context else None,
            "details": self.details,
            "encrypted_fields": self.encrypted_fields,
            "security_event_id": self.security_event_id,
        }


class ApiCallEvent(RequestAuditEvent):
    """API call audit event specialization."""

    def __init__(
        self,
        target_service: str,
        target_endpoint: str,
        **kwargs,
    ):
        """Initialize API call event.

        Args:
            target_service: Target service name
            target_endpoint: Target endpoint
            **kwargs: Other RequestAuditEvent parameters
        """
        super().__init__(event_type=AuditEventType.SERVICE_CALL, **kwargs)
        self.target_service = target_service
        self.target_endpoint = target_endpoint

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        base_dict = super().to_dict()
        return {
            **base_dict,
            "target_service": self.target_service,
            "target_endpoint": self.target_endpoint,
        }


class MiddlewareAuditEvent(RequestAuditEvent):
    """Middleware audit event specialization."""

    def __init__(
        self,
        middleware_name: str,
        middleware_stage: str,
        **kwargs,
    ):
        """Initialize middleware event.

        Args:
            middleware_name: Name of the middleware
            middleware_stage: Stage (start/end/error)
            **kwargs: Other RequestAuditEvent parameters
        """
        super().__init__(event_type=AuditEventType.MIDDLEWARE_REQUEST_START, **kwargs)
        self.middleware_name = middleware_name
        self.middleware_stage = middleware_stage

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        base_dict = super().to_dict()
        return {
            **base_dict,
            "middleware_name": self.middleware_name,
            "middleware_stage": self.middleware_stage,
        }
