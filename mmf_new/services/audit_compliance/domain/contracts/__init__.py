"""Domain contracts (port interfaces) for the audit compliance service."""

from .audit_event_repository import IAuditEventRepository
from .auditor import IAuditor
from .compliance_scanner import IComplianceScanner
from .siem_adapter import ISIEMAdapter

__all__ = [
    "IAuditor",
    "IAuditEventRepository",
    "IComplianceScanner",
    "ISIEMAdapter",
]
