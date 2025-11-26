"""Outbound ports for the audit compliance application layer."""

from ...domain.contracts import (
    IAuditEventRepository,
    IAuditor,
    IComplianceScanner,
    ISecurityReportGenerator,
    ISIEMAdapter,
    IThreatAnalyzer,
)

# Type aliases for cleaner imports in use cases
AuditorPort = IAuditor
AuditEventRepositoryPort = IAuditEventRepository
ComplianceScannerPort = IComplianceScanner
SecurityReportGeneratorPort = ISecurityReportGenerator
SIEMAdapterPort = ISIEMAdapter
ThreatAnalyzerPort = IThreatAnalyzer

__all__ = [
    "AuditorPort",
    "AuditEventRepositoryPort",
    "ComplianceScannerPort",
    "SecurityReportGeneratorPort",
    "SIEMAdapterPort",
    "ThreatAnalyzerPort",
]
