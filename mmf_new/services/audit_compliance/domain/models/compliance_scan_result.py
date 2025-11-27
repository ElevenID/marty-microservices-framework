"""Compliance scan result domain entity."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from mmf_new.core.domain import ComplianceFramework, Entity


@dataclass
class Finding:
    """A compliance finding within a scan result."""

    rule_id: str
    rule_name: str
    severity: str  # "low", "medium", "high", "critical"
    status: str  # "pass", "fail", "warning", "info"
    resource_id: str | None = None
    resource_type: str | None = None
    description: str = ""
    remediation: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


@dataclass
class ComplianceScanResult(Entity):
    """Domain entity for compliance scan results."""

    framework: ComplianceFramework
    scan_name: str
    target_resource: str
    target_type: str  # "service", "database", "api", etc.
    overall_status: str  # "compliant", "non_compliant", "partially_compliant"
    score: float  # 0.0 to 100.0
    findings: list[Finding] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    scan_duration_seconds: float | None = None
    scanned_by: str | None = None
    scan_configuration: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Ensure entity is properly initialized."""
        if not hasattr(self, "id") or not self.id:
            super().__init__()

    def to_dict(self) -> dict[str, Any]:
        """Convert scan result to dictionary."""
        base_dict = super().to_dict()
        scan_dict = {
            "framework": self.framework.value,
            "scan_name": self.scan_name,
            "target_resource": self.target_resource,
            "target_type": self.target_type,
            "overall_status": self.overall_status,
            "score": self.score,
            "findings": [
                {
                    "rule_id": f.rule_id,
                    "rule_name": f.rule_name,
                    "severity": f.severity,
                    "status": f.status,
                    "resource_id": f.resource_id,
                    "resource_type": f.resource_type,
                    "description": f.description,
                    "remediation": f.remediation,
                    "evidence": f.evidence,
                }
                for f in self.findings
            ],
            "recommendations": self.recommendations,
            "scan_duration_seconds": self.scan_duration_seconds,
            "scanned_by": self.scanned_by,
            "scan_configuration": self.scan_configuration,
            "metadata": self.metadata,
        }

        return {**base_dict, **scan_dict}

    def get_critical_findings(self) -> list[Finding]:
        """Get all critical severity findings."""
        return [f for f in self.findings if f.severity == "critical"]

    def get_failed_findings(self) -> list[Finding]:
        """Get all failed findings."""
        return [f for f in self.findings if f.status == "fail"]

    def get_compliance_percentage(self) -> float:
        """Calculate compliance percentage based on findings."""
        if not self.findings:
            return 100.0

        passed_findings = len([f for f in self.findings if f.status == "pass"])
        return (passed_findings / len(self.findings)) * 100.0

    def is_compliant(self) -> bool:
        """Check if the scan result indicates compliance."""
        return self.overall_status == "compliant"

    def has_critical_issues(self) -> bool:
        """Check if there are any critical compliance issues."""
        return len(self.get_critical_findings()) > 0

    def add_finding(
        self,
        rule_id: str,
        rule_name: str,
        severity: str,
        status: str,
        resource_id: str | None = None,
        resource_type: str | None = None,
        description: str = "",
        remediation: str = "",
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Add a finding to the scan result."""
        finding = Finding(
            rule_id=rule_id,
            rule_name=rule_name,
            severity=severity,
            status=status,
            resource_id=resource_id,
            resource_type=resource_type,
            description=description,
            remediation=remediation,
            evidence=evidence or {},
        )
        self.findings.append(finding)
        self.mark_updated()
