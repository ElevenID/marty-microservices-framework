"""
Shared audit and security domain models.

This module contains base domain models that can be extended by services
in the audit and compliance domain.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from .audit_types import (
    AuditLevel,
    ComplianceFramework,
    SecurityEventSeverity,
    SecurityEventStatus,
    SecurityEventType,
    SecurityThreatLevel,
)


@dataclass
class AuditEvent:
    """Base audit event structure for cross-service use."""

    event_id: str
    event_type: str
    timestamp: datetime
    principal_id: str | None = None
    resource: str | None = None
    action: str | None = None
    result: str = "unknown"  # "success", "failure", "error", etc.
    details: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    source_ip: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    service_name: str | None = None

    def __post_init__(self):
        """Ensure timestamp is set if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert audit event to dictionary for serialization."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                else:
                    result[key] = value
        return result


@dataclass
class SecurityEvent:
    """Base security event structure for cross-service use."""

    event_id: str
    event_type: SecurityEventType
    severity: SecurityEventSeverity
    timestamp: datetime
    source_ip: str | None = None
    user_id: str | None = None
    service_name: str | None = None
    resource: str | None = None
    action: str | None = None
    user_agent: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None
    raw_data: dict[str, Any] = field(default_factory=dict)
    normalized_data: dict[str, Any] = field(default_factory=dict)
    enrichment_data: dict[str, Any] = field(default_factory=dict)
    status: SecurityEventStatus = SecurityEventStatus.NEW
    assigned_analyst: str | None = None
    investigation_notes: list[str] = field(default_factory=list)
    related_events: list[str] = field(default_factory=list)
    response_actions: list[str] = field(default_factory=list)
    mitigation_applied: bool = False

    def __post_init__(self):
        """Ensure timestamp is set if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert security event to dictionary for serialization."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif hasattr(value, "value"):  # Enum
                    result[key] = value.value
                else:
                    result[key] = value
        return result

    def calculate_risk_score(self) -> float:
        """Calculate risk score for the event."""
        base_scores = {
            SecurityEventSeverity.INFO: 1.0,
            SecurityEventSeverity.LOW: 2.0,
            SecurityEventSeverity.MEDIUM: 5.0,
            SecurityEventSeverity.HIGH: 8.0,
            SecurityEventSeverity.CRITICAL: 10.0,
        }

        base_score = base_scores.get(self.severity, 1.0)

        # Adjust based on event type
        high_risk_events = {
            SecurityEventType.PRIVILEGE_ESCALATION,
            SecurityEventType.MALWARE_DETECTION,
            SecurityEventType.INTRUSION_ATTEMPT,
            SecurityEventType.THREAT_DETECTED,
        }

        if self.event_type in high_risk_events:
            base_score *= 1.5

        return min(base_score, 10.0)


@dataclass
class ComplianceResult:
    """Base compliance scan result structure."""

    framework: ComplianceFramework
    passed: bool
    score: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    findings: list[dict[str, Any]] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    scan_id: str | None = None
    resource_id: str | None = None
    resource_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert compliance result to dictionary."""
        result = {}
        for key, value in self.__dict__.items():
            if value is not None:
                if isinstance(value, datetime):
                    result[key] = value.isoformat()
                elif hasattr(value, "value"):  # Enum
                    result[key] = value.value
                else:
                    result[key] = value
        return result


@dataclass
class SecurityPrincipal:
    """Base security principal representation."""

    id: str
    name: str
    type: str  # "user", "service", "system"
    roles: list[str] = field(default_factory=list)
    permissions: list[str] = field(default_factory=list)
    attributes: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_access: datetime | None = None
    is_active: bool = True


@dataclass
class ThreatIndicator:
    """Base threat indicator structure."""

    indicator_id: str
    indicator_type: str  # "ip", "domain", "hash", "url", etc.
    value: str
    threat_level: SecurityThreatLevel
    confidence: float  # 0.0 to 1.0
    source: str
    first_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    tags: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
