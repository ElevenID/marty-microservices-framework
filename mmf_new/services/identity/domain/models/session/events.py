"""
Session events domain models.

This module contains event models for session lifecycle events,
audit tracking, and event-driven session management.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from mmf_new.core.domain.entity import ValueObject


class SessionEventType(Enum):
    """Types of session events."""

    # Lifecycle events
    SESSION_CREATED = "session_created"
    SESSION_ACCESSED = "session_accessed"
    SESSION_EXTENDED = "session_extended"
    SESSION_EXPIRED = "session_expired"
    SESSION_INVALIDATED = "session_invalidated"
    SESSION_TERMINATED = "session_terminated"
    SESSION_ROTATED = "session_rotated"

    # Security events
    SECURITY_VIOLATION = "security_violation"
    IP_ADDRESS_CHANGED = "ip_address_changed"
    USER_AGENT_CHANGED = "user_agent_changed"
    CONCURRENT_SESSION_DETECTED = "concurrent_session_detected"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"

    # Authentication events
    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"
    MFA_COMPLETED = "mfa_completed"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    ROLE_CHANGED = "role_changed"

    # Data events
    SESSION_DATA_UPDATED = "session_data_updated"
    SESSION_DATA_CLEARED = "session_data_cleared"

    # Administrative events
    ADMIN_SESSION_VIEW = "admin_session_view"
    ADMIN_SESSION_TERMINATE = "admin_session_terminate"
    SESSION_CLEANUP = "session_cleanup"


class EventSeverity(Enum):
    """Event severity levels for monitoring and alerting."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class SessionEventMetadata(ValueObject):
    """Metadata for session events."""

    # Request context
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None

    # Security context
    client_fingerprint: str | None = None
    geo_location: dict[str, Any] = field(default_factory=dict)
    device_info: dict[str, Any] = field(default_factory=dict)

    # Application context
    application_id: str | None = None
    service_name: str | None = None
    environment: str | None = None

    # Additional metadata
    custom_data: dict[str, Any] = field(default_factory=dict)

    def with_custom_data(self, key: str, value: Any) -> SessionEventMetadata:
        """Add custom metadata."""
        new_custom_data = {**self.custom_data, key: value}
        return SessionEventMetadata(
            ip_address=self.ip_address,
            user_agent=self.user_agent,
            request_id=self.request_id,
            client_fingerprint=self.client_fingerprint,
            geo_location=self.geo_location,
            device_info=self.device_info,
            application_id=self.application_id,
            service_name=self.service_name,
            environment=self.environment,
            custom_data=new_custom_data,
        )


@dataclass(frozen=True)
class SessionEvent(ValueObject):
    """
    Base session event model.

    Represents any event that occurs during a session's lifecycle,
    including security events, state changes, and administrative actions.
    """

    event_id: str
    session_id: str
    user_id: str
    event_type: SessionEventType
    timestamp: datetime

    # Event details
    message: str | None = None
    severity: EventSeverity = EventSeverity.LOW
    metadata: SessionEventMetadata = field(default_factory=SessionEventMetadata)

    # Event context
    correlation_id: str | None = None
    parent_event_id: str | None = None

    # Event data
    before_state: dict[str, Any] = field(default_factory=dict)
    after_state: dict[str, Any] = field(default_factory=dict)
    event_data: dict[str, Any] = field(default_factory=dict)

    # Processing information
    processed: bool = False
    processed_at: datetime | None = None
    processing_errors: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate event data."""
        if not self.event_id or not self.event_id.strip():
            raise ValueError("Event ID is required")

        if not self.session_id or not self.session_id.strip():
            raise ValueError("Session ID is required")

        if not self.user_id or not self.user_id.strip():
            raise ValueError("User ID is required")

        # Ensure timezone awareness
        if self.timestamp.tzinfo is None:
            object.__setattr__(self, "timestamp", self.timestamp.replace(tzinfo=timezone.utc))

        if self.processed_at and self.processed_at.tzinfo is None:
            object.__setattr__(self, "processed_at", self.processed_at.replace(tzinfo=timezone.utc))

    @classmethod
    def create(
        cls,
        session_id: str,
        user_id: str,
        event_type: SessionEventType,
        message: str | None = None,
        severity: EventSeverity = EventSeverity.LOW,
        metadata: SessionEventMetadata | None = None,
        **kwargs,
    ) -> SessionEvent:
        """Create a new session event."""
        return cls(
            event_id=generate_event_id(),
            session_id=session_id,
            user_id=user_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc),
            message=message,
            severity=severity,
            metadata=metadata or SessionEventMetadata(),
            **kwargs,
        )

    def mark_processed(self, processing_errors: list[str] | None = None) -> SessionEvent:
        """Mark event as processed."""
        return SessionEvent(
            event_id=self.event_id,
            session_id=self.session_id,
            user_id=self.user_id,
            event_type=self.event_type,
            timestamp=self.timestamp,
            message=self.message,
            severity=self.severity,
            metadata=self.metadata,
            correlation_id=self.correlation_id,
            parent_event_id=self.parent_event_id,
            before_state=self.before_state,
            after_state=self.after_state,
            event_data=self.event_data,
            processed=True,
            processed_at=datetime.now(timezone.utc),
            processing_errors=processing_errors or [],
        )

    def with_correlation_id(self, correlation_id: str) -> SessionEvent:
        """Add correlation ID to event."""
        return SessionEvent(
            event_id=self.event_id,
            session_id=self.session_id,
            user_id=self.user_id,
            event_type=self.event_type,
            timestamp=self.timestamp,
            message=self.message,
            severity=self.severity,
            metadata=self.metadata,
            correlation_id=correlation_id,
            parent_event_id=self.parent_event_id,
            before_state=self.before_state,
            after_state=self.after_state,
            event_data=self.event_data,
            processed=self.processed,
            processed_at=self.processed_at,
            processing_errors=self.processing_errors,
        )

    def with_state_change(
        self, before_state: dict[str, Any], after_state: dict[str, Any]
    ) -> SessionEvent:
        """Add state change information to event."""
        return SessionEvent(
            event_id=self.event_id,
            session_id=self.session_id,
            user_id=self.user_id,
            event_type=self.event_type,
            timestamp=self.timestamp,
            message=self.message,
            severity=self.severity,
            metadata=self.metadata,
            correlation_id=self.correlation_id,
            parent_event_id=self.parent_event_id,
            before_state=before_state,
            after_state=after_state,
            event_data=self.event_data,
            processed=self.processed,
            processed_at=self.processed_at,
            processing_errors=self.processing_errors,
        )

    def is_security_event(self) -> bool:
        """Check if this is a security-related event."""
        security_events = {
            SessionEventType.SECURITY_VIOLATION,
            SessionEventType.IP_ADDRESS_CHANGED,
            SessionEventType.USER_AGENT_CHANGED,
            SessionEventType.CONCURRENT_SESSION_DETECTED,
            SessionEventType.SUSPICIOUS_ACTIVITY,
            SessionEventType.AUTHENTICATION_FAILURE,
            SessionEventType.SESSION_TERMINATED,
        }
        return self.event_type in security_events

    def requires_immediate_attention(self) -> bool:
        """Check if event requires immediate attention."""
        return (
            self.severity in [EventSeverity.HIGH, EventSeverity.CRITICAL]
            or self.is_security_event()
        )


@dataclass(frozen=True)
class SessionCreatedEvent(SessionEvent):
    """Event for session creation."""

    def __post_init__(self):
        super().__post_init__()
        if self.event_type != SessionEventType.SESSION_CREATED:
            raise ValueError("Event type must be SESSION_CREATED")


@dataclass(frozen=True)
class SessionAccessedEvent(SessionEvent):
    """Event for session access."""

    def __post_init__(self):
        super().__post_init__()
        if self.event_type != SessionEventType.SESSION_ACCESSED:
            raise ValueError("Event type must be SESSION_ACCESSED")


@dataclass(frozen=True)
class SessionExpiredEvent(SessionEvent):
    """Event for session expiration."""

    expiry_reason: str = "timeout"  # timeout, absolute_timeout, manual

    def __post_init__(self):
        super().__post_init__()
        if self.event_type != SessionEventType.SESSION_EXPIRED:
            raise ValueError("Event type must be SESSION_EXPIRED")


@dataclass(frozen=True)
class SecurityViolationEvent(SessionEvent):
    """Event for security violations."""

    violation_type: str = ""
    risk_score: float = 0.0
    recommended_action: str = ""

    def __post_init__(self):
        super().__post_init__()
        if self.event_type != SessionEventType.SECURITY_VIOLATION:
            raise ValueError("Event type must be SECURITY_VIOLATION")

        # Security violations should have high severity by default
        if self.severity == EventSeverity.LOW:
            object.__setattr__(self, "severity", EventSeverity.HIGH)


@dataclass(frozen=True)
class AuthenticationEvent(SessionEvent):
    """Event for authentication-related activities."""

    auth_method: str = ""
    mfa_used: bool = False
    device_trusted: bool = False

    def __post_init__(self):
        super().__post_init__()
        auth_events = {
            SessionEventType.AUTHENTICATION_SUCCESS,
            SessionEventType.AUTHENTICATION_FAILURE,
            SessionEventType.MFA_COMPLETED,
        }
        if self.event_type not in auth_events:
            raise ValueError(f"Event type must be one of: {auth_events}")


@dataclass(frozen=True)
class SessionEventBatch(ValueObject):
    """
    Batch of session events for efficient processing.

    Used for bulk event processing and analytics.
    """

    batch_id: str
    events: list[SessionEvent]
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    processed: bool = False
    processed_at: datetime | None = None

    def __post_init__(self):
        """Validate batch data."""
        if not self.batch_id or not self.batch_id.strip():
            raise ValueError("Batch ID is required")

        if not self.events:
            raise ValueError("Batch must contain at least one event")

        # Ensure timezone awareness
        if self.created_at.tzinfo is None:
            object.__setattr__(self, "created_at", self.created_at.replace(tzinfo=timezone.utc))

        if self.processed_at and self.processed_at.tzinfo is None:
            object.__setattr__(self, "processed_at", self.processed_at.replace(tzinfo=timezone.utc))

    @classmethod
    def create(cls, events: list[SessionEvent]) -> SessionEventBatch:
        """Create a new event batch."""
        return cls(
            batch_id=generate_batch_id(), events=events, created_at=datetime.now(timezone.utc)
        )

    def mark_processed(self) -> SessionEventBatch:
        """Mark batch as processed."""
        return SessionEventBatch(
            batch_id=self.batch_id,
            events=self.events,
            created_at=self.created_at,
            processed=True,
            processed_at=datetime.now(timezone.utc),
        )

    def get_events_by_type(self, event_type: SessionEventType) -> list[SessionEvent]:
        """Get events of a specific type."""
        return [event for event in self.events if event.event_type == event_type]

    def get_security_events(self) -> list[SessionEvent]:
        """Get security-related events."""
        return [event for event in self.events if event.is_security_event()]

    def get_high_severity_events(self) -> list[SessionEvent]:
        """Get high severity events."""
        return [
            event
            for event in self.events
            if event.severity in [EventSeverity.HIGH, EventSeverity.CRITICAL]
        ]

    def get_unprocessed_events(self) -> list[SessionEvent]:
        """Get unprocessed events."""
        return [event for event in self.events if not event.processed]

    @property
    def event_count(self) -> int:
        """Get number of events in batch."""
        return len(self.events)

    @property
    def session_count(self) -> int:
        """Get number of unique sessions in batch."""
        return len({event.session_id for event in self.events})

    @property
    def user_count(self) -> int:
        """Get number of unique users in batch."""
        return len({event.user_id for event in self.events})


# Event factory functions


def create_session_created_event(
    session_id: str, user_id: str, metadata: SessionEventMetadata | None = None, **kwargs
) -> SessionCreatedEvent:
    """Create a session created event."""
    return SessionCreatedEvent(
        event_id=generate_event_id(),
        session_id=session_id,
        user_id=user_id,
        event_type=SessionEventType.SESSION_CREATED,
        timestamp=datetime.now(timezone.utc),
        message=f"Session created for user {user_id}",
        severity=EventSeverity.LOW,
        metadata=metadata or SessionEventMetadata(),
        **kwargs,
    )


def create_session_accessed_event(
    session_id: str,
    user_id: str,
    action: str = "accessed",
    metadata: SessionEventMetadata | None = None,
    **kwargs,
) -> SessionAccessedEvent:
    """Create a session accessed event."""
    return SessionAccessedEvent(
        event_id=generate_event_id(),
        session_id=session_id,
        user_id=user_id,
        event_type=SessionEventType.SESSION_ACCESSED,
        timestamp=datetime.now(timezone.utc),
        message=f"Session {action} by user {user_id}",
        severity=EventSeverity.LOW,
        metadata=metadata or SessionEventMetadata(),
        event_data={"action": action},
        **kwargs,
    )


def create_session_expired_event(
    session_id: str,
    user_id: str,
    expiry_reason: str = "timeout",
    metadata: SessionEventMetadata | None = None,
    **kwargs,
) -> SessionExpiredEvent:
    """Create a session expired event."""
    return SessionExpiredEvent(
        event_id=generate_event_id(),
        session_id=session_id,
        user_id=user_id,
        event_type=SessionEventType.SESSION_EXPIRED,
        timestamp=datetime.now(timezone.utc),
        message=f"Session expired for user {user_id} due to {expiry_reason}",
        severity=EventSeverity.MEDIUM,
        metadata=metadata or SessionEventMetadata(),
        expiry_reason=expiry_reason,
        **kwargs,
    )


def create_security_violation_event(
    session_id: str,
    user_id: str,
    violation_type: str,
    risk_score: float = 0.5,
    metadata: SessionEventMetadata | None = None,
    **kwargs,
) -> SecurityViolationEvent:
    """Create a security violation event."""
    return SecurityViolationEvent(
        event_id=generate_event_id(),
        session_id=session_id,
        user_id=user_id,
        event_type=SessionEventType.SECURITY_VIOLATION,
        timestamp=datetime.now(timezone.utc),
        message=f"Security violation detected: {violation_type}",
        severity=EventSeverity.HIGH,
        metadata=metadata or SessionEventMetadata(),
        violation_type=violation_type,
        risk_score=risk_score,
        **kwargs,
    )


def create_authentication_event(
    session_id: str,
    user_id: str,
    event_type: SessionEventType,
    auth_method: str = "",
    mfa_used: bool = False,
    metadata: SessionEventMetadata | None = None,
    **kwargs,
) -> AuthenticationEvent:
    """Create an authentication event."""
    severity = (
        EventSeverity.MEDIUM
        if event_type == SessionEventType.AUTHENTICATION_FAILURE
        else EventSeverity.LOW
    )

    return AuthenticationEvent(
        event_id=generate_event_id(),
        session_id=session_id,
        user_id=user_id,
        event_type=event_type,
        timestamp=datetime.now(timezone.utc),
        message=f"Authentication {event_type.value} for user {user_id}",
        severity=severity,
        metadata=metadata or SessionEventMetadata(),
        auth_method=auth_method,
        mfa_used=mfa_used,
        **kwargs,
    )


# Utility functions


def generate_event_id() -> str:
    """Generate a unique event ID."""
    return str(uuid4())


def generate_batch_id() -> str:
    """Generate a unique batch ID."""
    return f"batch_{uuid4()}"


def generate_correlation_id() -> str:
    """Generate a correlation ID for related events."""
    return f"corr_{uuid4()}"
