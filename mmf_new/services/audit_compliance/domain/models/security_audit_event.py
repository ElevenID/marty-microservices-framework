"""Security audit event domain entity."""

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from mmf_new.core.domain import AuditLevel, Entity, SecurityEventType


@dataclass
class SecurityAuditEvent(Entity):
    """Domain entity for security audit events."""

    event_type: SecurityEventType
    principal_id: str | None = None
    resource: str | None = None
    action: str | None = None
    result: str | None = None  # "success", "failure", "denied", etc.
    details: dict[str, Any] = field(default_factory=dict)
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    service_name: str | None = None
    level: AuditLevel = AuditLevel.INFO

    def __post_init__(self):
        """Ensure entity is properly initialized."""
        if not hasattr(self, "id") or not self.id:
            super().__init__()

        # Ensure timestamp is set
        if not hasattr(self, "timestamp") or not self.timestamp:
            self.timestamp = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary for serialization."""
        base_dict = super().to_dict()
        event_dict = {
            "event_type": self.event_type.value if self.event_type else None,
            "principal_id": self.principal_id,
            "resource": self.resource,
            "action": self.action,
            "result": self.result,
            "details": self.details,
            "session_id": self.session_id,
            "ip_address": self.ip_address,
            "user_agent": self.user_agent,
            "correlation_id": self.correlation_id,
            "service_name": self.service_name,
            "level": self.level.value if self.level else None,
        }

        # Merge with base Entity fields
        return {**base_dict, **event_dict}

    def to_json(self) -> str:
        """Convert event to JSON string."""

        return json.dumps(self.to_dict(), default=str)

    def is_critical(self) -> bool:
        """Check if this is a critical security event."""
        critical_events = {
            SecurityEventType.SECURITY_VIOLATION,
            SecurityEventType.PRIVILEGE_ESCALATION,
            SecurityEventType.MALWARE_DETECTION,
            SecurityEventType.INTRUSION_ATTEMPT,
            SecurityEventType.THREAT_DETECTED,
        }

        return self.event_type in critical_events or self.level in [
            AuditLevel.ERROR,
            AuditLevel.CRITICAL,
        ]

    def requires_immediate_attention(self) -> bool:
        """Check if this event requires immediate attention."""
        return self.level == AuditLevel.CRITICAL or self.event_type in {
            SecurityEventType.MALWARE_DETECTION,
            SecurityEventType.INTRUSION_ATTEMPT,
            SecurityEventType.PRIVILEGE_ESCALATION,
        }
