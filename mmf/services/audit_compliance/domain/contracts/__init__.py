"""Domain contracts (port interfaces) for the audit compliance service."""

from .audit_event_repository import IAuditEventRepository
from .auditor import IAuditor
from .compliance_scanner import IComplianceScanner
from .metrics_adapter import IMetricsAdapter
from .security_report_generator import ISecurityReportGenerator
from .siem_adapter import ISIEMAdapter
from .threat_analyzer import IThreatAnalyzer

__all__ = [
    "IAuditor",
    "IAuditEventRepository",
    "IComplianceScanner",
    "IMetricsAdapter",
    "ISecurityReportGenerator",
    "ISIEMAdapter",
    "IThreatAnalyzer",
]
