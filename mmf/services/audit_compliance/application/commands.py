"""
Commands for Audit Compliance Service.

This module aggregates command requests from use cases to provide a unified
interface for the service factory.
"""

from .use_cases.analyze_threat_pattern import AnalyzeThreatPatternRequest
from .use_cases.collect_security_event import CollectSecurityEventRequest
from .use_cases.generate_security_report import GenerateSecurityReportRequest
from .use_cases.log_audit_event import LogAuditEventRequest
from .use_cases.scan_compliance import ScanComplianceRequest


class AnalyzeThreatPatternCommand:
    """Command for analyzing threat patterns."""

    Request = AnalyzeThreatPatternRequest


class CollectSecurityEventCommand:
    """Command for collecting security events."""

    Request = CollectSecurityEventRequest


class GenerateSecurityReportCommand:
    """Command for generating security reports."""

    Request = GenerateSecurityReportRequest


class LogAuditEventCommand:
    """Command for logging audit events."""

    Request = LogAuditEventRequest


class ScanComplianceCommand:
    """Command for scanning compliance."""

    Request = ScanComplianceRequest
