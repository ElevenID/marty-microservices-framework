"""
Audit Factory

Factory for creating audit components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mmf.core.security.ports.common import IAuditor
from mmf.framework.infrastructure.dependency_injection import get_service, has_service
from mmf.framework.security.adapters.audit.adapter import AuditServiceAdapter
from mmf.services.audit_compliance.di_config import get_container as get_audit_container
from mmf.services.audit_compliance.service_factory import AuditComplianceService


@dataclass
class RegistrationEntry:
    """Service registration entry."""

    interface: type
    instance: Any


class AuditFactory:
    """Factory for audit components."""

    @staticmethod
    def create_registrations() -> list[RegistrationEntry]:
        """Create audit components and return registration entries."""
        entries = []

        # Create AuditComplianceService
        if has_service(AuditComplianceService):
            audit_service = get_service(AuditComplianceService)
        else:
            # Pass the container to AuditComplianceService
            container = get_audit_container()
            audit_service = AuditComplianceService(container=container)
            entries.append(RegistrationEntry(AuditComplianceService, audit_service))

        auditor = AuditServiceAdapter(audit_service)
        entries.append(RegistrationEntry(IAuditor, auditor))

        return entries
