"""
Audit Compliance Infrastructure Layer

This module provides all the infrastructure adapters that implement the domain contracts,
integrating with the mmf_new framework infrastructure services.
"""

from .adapters.audit_metrics_adapter import AuditComplianceMetricsAdapter
from .caching.audit_event_cache import AuditEventCache
from .repositories.audit_event_repository import AuditEventRepository
from .compliance_scanner_adapter import ComplianceScannerAdapter
from .adapters.elasticsearch_siem_adapter import ElasticsearchSIEMAdapter
from .security_report_generator_adapter import SecurityReportGeneratorAdapter
from .threat_analyzer_adapter import ThreatAnalyzerAdapter

__all__ = [
    # Repository adapters
    "AuditEventRepository",
    # Cache adapters
    "AuditEventCache",
    # External service adapters
    "ElasticsearchSIEMAdapter",
    # Metrics adapters
    "AuditComplianceMetricsAdapter",
    # Analysis adapters
    "ComplianceScannerAdapter",
    "ThreatAnalyzerAdapter",
    # Reporting adapters
    "SecurityReportGeneratorAdapter",
]
