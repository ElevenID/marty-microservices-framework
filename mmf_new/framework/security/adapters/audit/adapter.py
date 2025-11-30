"""
Audit Adapter

Adapter for Audit Compliance Service.
"""

from __future__ import annotations

import logging
from typing import Any

from mmf_new.core.domain.audit_types import SecurityEventSeverity, SecurityEventType
from mmf_new.core.security.ports.common import IAuditor
from mmf_new.services.audit_compliance.service_factory import AuditComplianceService

logger = logging.getLogger(__name__)


class AuditServiceAdapter(IAuditor):
    """Adapter for Audit Compliance Service."""

    def __init__(self, audit_service: AuditComplianceService):
        self.audit_service = audit_service

    async def audit_event(self, event_type: str, details: dict[str, Any]) -> None:
        """Log audit event using Audit Compliance Service."""
        try:
            # Map string event type to enum if possible, or use generic
            try:
                security_event_type = SecurityEventType(event_type)
            except ValueError:
                security_event_type = SecurityEventType.SECURITY_VIOLATION

            await self.audit_service.log_audit_event(
                event_type=security_event_type,
                severity=SecurityEventSeverity.INFO,  # Default severity
                source="security_framework",
                description=details.get("description", f"Security event: {event_type}"),
                user_id=details.get("user_id"),
                metadata=details,
            )
        except Exception as e:
            logger.error(f"Audit logging failed: {e}")
