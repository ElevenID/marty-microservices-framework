"""Domain layer base classes and interfaces."""

from .audit_models import (
    AuditEvent,
    ComplianceResult,
    SecurityEvent,
    SecurityPrincipal,
    ThreatIndicator,
)

# Audit and security types and models
from .audit_types import (
    AuditLevel,
    AuthenticationMethod,
    ComplianceFramework,
    SecurityEventSeverity,
    SecurityEventStatus,
    SecurityEventType,
    SecurityLevel,
    SecurityThreatLevel,
)
from .entity import AggregateRoot, DomainEvent, Entity, ValueObject
from .ports.repository import (
    DomainRepository,
    EntityConflictError,
    EntityNotFoundError,
    Repository,
    RepositoryError,
    RepositoryValidationError,
)

__all__ = [
    # Base domain classes
    "Entity",
    "AggregateRoot",
    "ValueObject",
    "DomainEvent",
    "Repository",
    "DomainRepository",
    "RepositoryError",
    "EntityNotFoundError",
    "EntityConflictError",
    "RepositoryValidationError",
    # Audit and security types
    "AuditLevel",
    "AuthenticationMethod",
    "ComplianceFramework",
    "SecurityEventSeverity",
    "SecurityEventStatus",
    "SecurityEventType",
    "SecurityLevel",
    "SecurityThreatLevel",
    # Audit and security models
    "AuditEvent",
    "ComplianceResult",
    "SecurityEvent",
    "SecurityPrincipal",
    "ThreatIndicator",
]
