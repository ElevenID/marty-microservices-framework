"""
Event Type Definitions and Data Classes

Defines the types and structures used throughout the event publishing system.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class EventPriority(Enum):
    """Event priority levels."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEventType(Enum):
    """Types of audit events."""

    # Authentication and authorization
    USER_LOGIN = "user.login"
    USER_LOGOUT = "user.logout"
    USER_LOGIN_FAILED = "user.login.failed"
    PERMISSION_DENIED = "permission.denied"
    ROLE_CHANGED = "role.changed"

    # Data access and modification
    DATA_ACCESSED = "data.accessed"
    DATA_CREATED = "data.created"
    DATA_UPDATED = "data.updated"
    DATA_DELETED = "data.deleted"
    DATA_EXPORTED = "data.exported"

    # Security events
    SECURITY_VIOLATION = "security.violation"
    CERTIFICATE_ISSUED = "certificate.issued"
    CERTIFICATE_REVOKED = "certificate.revoked"
    CERTIFICATE_VALIDATED = "certificate.validated"

    # System events
    SERVICE_STARTED = "service.started"
    SERVICE_STOPPED = "service.stopped"
    SERVICE_ERROR = "service.error"
    CONFIGURATION_CHANGED = "configuration.changed"

    # Trust and compliance
    TRUST_ANCHORED = "trust.anchored"
    TRUST_REVOKED = "trust.revoked"
    COMPLIANCE_CHECKED = "compliance.checked"
    COMPLIANCE_VIOLATION = "compliance.violation"


class NotificationEventType(Enum):
    """Types of notification events."""

    # User notifications
    USER_WELCOME = "user.welcome"
    USER_PASSWORD_RESET = "user.password.reset"
    USER_ACCOUNT_LOCKED = "user.account.locked"

    # Certificate notifications
    CERTIFICATE_EXPIRING = "certificate.expiring"
    CERTIFICATE_EXPIRED = "certificate.expired"
    CERTIFICATE_RENEWAL_REQUIRED = "certificate.renewal.required"

    # System notifications
    SYSTEM_MAINTENANCE = "system.maintenance"
    SYSTEM_ALERT = "system.alert"
    BACKUP_COMPLETED = "backup.completed"
    BACKUP_FAILED = "backup.failed"

    # Compliance notifications
    COMPLIANCE_REVIEW_DUE = "compliance.review.due"
    AUDIT_REQUIRED = "audit.required"
    POLICY_UPDATED = "policy.updated"


class EventMetadata(BaseModel):
    """Metadata for all events."""

    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service_name: str
    service_version: str = "1.0.0"
    correlation_id: str | None = None
    causation_id: str | None = None

    # User context
    user_id: str | None = None
    session_id: str | None = None

    # Request context
    trace_id: str | None = None
    span_id: str | None = None
    request_id: str | None = None

    # Event properties
    priority: EventPriority = EventPriority.NORMAL

    # Additional context
    source_ip: str | None = None
    user_agent: str | None = None
    custom_headers: dict[str, str] = Field(default_factory=dict)

    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class AuditEventData(BaseModel):
    """Audit event payload structure."""

    event_type: AuditEventType
    action: str
    resource_type: str
    resource_id: str | None = None

    # Details about the operation
    operation_details: dict[str, Any] = Field(default_factory=dict)
    previous_state: dict[str, Any] | None = None
    new_state: dict[str, Any] | None = None

    # Security context
    security_context: dict[str, Any] = Field(default_factory=dict)

    # Result information
    success: bool = True
    error_message: str | None = None
    error_code: str | None = None

    # Compliance and risk
    compliance_tags: list[str] = Field(default_factory=list)
    risk_level: str = "low"  # low, medium, high, critical


class NotificationEventData(BaseModel):
    """Notification event payload structure."""

    event_type: NotificationEventType
    recipient_type: str  # user, admin, system
    recipient_ids: list[str] = Field(default_factory=list)

    # Message content
    subject: str
    message: str
    message_template: str | None = None
    template_variables: dict[str, Any] = Field(default_factory=dict)

    # Delivery options
    channels: list[str] = Field(default_factory=lambda: ["email"])  # email, sms, push, webhook
    delivery_time: datetime | None = None
    expiry_time: datetime | None = None

    # Additional data
    action_url: str | None = None
    action_label: str | None = None
    attachments: list[str] = Field(default_factory=list)


class DomainEventData(BaseModel):
    """Domain event payload structure."""

    aggregate_type: str
    aggregate_id: str
    event_type: str
    event_version: int = 1

    # Event payload
    event_data: dict[str, Any] = Field(default_factory=dict)

    # Business context
    business_context: dict[str, Any] = Field(default_factory=dict)

    # Schema information
    schema_version: str = "1.0"
    schema_url: str | None = None
