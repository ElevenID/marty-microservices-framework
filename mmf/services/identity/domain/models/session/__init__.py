"""
Session domain models.

This package contains all domain models related to session management,
including session state, configuration, and event tracking.
"""

# Configuration models
from .configuration import (
    SecurityPolicy,
    SessionCleanupConfiguration,
    SessionCleanupStrategy,
    SessionConfiguration,
    SessionSecurityPolicy,
    SessionStorageConfiguration,
    SessionStorageType,
    SessionTimeoutPolicy,
    create_security_policy,
    create_timeout_policy,
)

# Event models
from .events import (
    AuthenticationEvent,
    EventSeverity,
    SecurityViolationEvent,
    SessionAccessedEvent,
    SessionCreatedEvent,
    SessionEvent,
    SessionEventBatch,
    SessionEventMetadata,
    SessionEventType,
    SessionExpiredEvent,
    create_authentication_event,
    create_security_violation_event,
    create_session_accessed_event,
    create_session_created_event,
    create_session_expired_event,
    generate_batch_id,
    generate_correlation_id,
    generate_event_id,
)

# Core session models
from .session import (
    Session,
    SessionActivity,
    SessionData,
    SessionSecurityContext,
    SessionStatus,
    SessionTimeout,
    generate_session_id,
    generate_session_token,
)

# Export all public models and utilities
__all__ = [
    # Core session models
    "Session",
    "SessionStatus",
    "SessionTimeout",
    "SessionSecurityContext",
    "SessionActivity",
    "SessionData",
    "generate_session_id",
    "generate_session_token",
    # Configuration models
    "SessionConfiguration",
    "SessionTimeoutPolicy",
    "SessionSecurityPolicy",
    "SessionStorageConfiguration",
    "SessionCleanupConfiguration",
    "SessionStorageType",
    "SecurityPolicy",
    "SessionCleanupStrategy",
    "create_timeout_policy",
    "create_security_policy",
    # Event models
    "SessionEvent",
    "SessionEventType",
    "EventSeverity",
    "SessionEventMetadata",
    "SessionCreatedEvent",
    "SessionAccessedEvent",
    "SessionExpiredEvent",
    "SecurityViolationEvent",
    "AuthenticationEvent",
    "SessionEventBatch",
    "create_session_created_event",
    "create_session_accessed_event",
    "create_session_expired_event",
    "create_security_violation_event",
    "create_authentication_event",
    "generate_event_id",
    "generate_batch_id",
    "generate_correlation_id",
]
