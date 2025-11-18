"""Outbound ports for the audit compliance application layer."""

from ...domain.contracts import (
    IAuditEventRepository,
    IAuditor,
    IComplianceScanner,
    ISIEMAdapter,
)

# Type aliases for cleaner imports in use cases
AuditorPort = IAuditor
AuditEventRepositoryPort = IAuditEventRepository
ComplianceScannerPort = IComplianceScanner
SIEMAdapterPort = ISIEMAdapter

__all__ = [
    "AuditorPort",
    "AuditEventRepositoryPort",
    "ComplianceScannerPort",
    "SIEMAdapterPort",
]
