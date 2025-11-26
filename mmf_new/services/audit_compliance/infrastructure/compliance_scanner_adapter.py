"""
Compliance Scanner Adapter

Implements IComplianceScanner interface by integrating with existing
compliance infrastructure while adapting to hexagonal architecture patterns.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional

from mmf_new.core.domain.audit_types import ComplianceFramework
from mmf_new.framework.infrastructure.database_manager import DatabaseManager
from mmf_new.framework.infrastructure.framework_metrics import FrameworkMetrics

from ..domain.contracts import IComplianceScanner
from ..domain.models import ComplianceScanResult, Finding

logger = logging.getLogger(__name__)


class ComplianceScannerAdapter(IComplianceScanner):
    """
    Compliance scanner adapter that integrates existing compliance infrastructure
    with hexagonal architecture patterns.
    """

    def __init__(
        self,
        database_manager: DatabaseManager,
        metrics: FrameworkMetrics,
        config: dict[str, Any] | None = None,
    ):
        self.database_manager = database_manager
        self.metrics = metrics
        self.config = config or {}

        # Supported compliance frameworks
        self.supported_frameworks = [
            ComplianceFramework.GDPR,
            ComplianceFramework.HIPAA,
            ComplianceFramework.SOX,
            ComplianceFramework.PCI_DSS,
            ComplianceFramework.ISO27001,
            ComplianceFramework.NIST,
        ]

        # Initialize compliance checkers
        self._framework_checkers = {
            ComplianceFramework.GDPR: self._scan_gdpr_compliance,
            ComplianceFramework.HIPAA: self._scan_hipaa_compliance,
            ComplianceFramework.SOX: self._scan_sox_compliance,
            ComplianceFramework.PCI_DSS: self._scan_pci_compliance,
            ComplianceFramework.ISO27001: self._scan_iso27001_compliance,
            ComplianceFramework.NIST: self._scan_nist_compliance,
        }

    async def scan_compliance(
        self, framework: ComplianceFramework, context: dict[str, Any]
    ) -> ComplianceScanResult:
        """
        Scan for compliance with a specific framework.

        Args:
            framework: Compliance framework to scan against
            context: Context for the compliance scan

        Returns:
            ComplianceScanResult with scan results
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Record scan attempt
            self.metrics.increment_counter(
                "compliance_scans_total", labels={"framework": framework.value}
            )

            # Validate framework support
            if framework not in self.supported_frameworks:
                result = ComplianceScanResult(
                    framework=framework,
                    scan_name=f"Scan {framework.value}",
                    target_resource="system",
                    target_type="system",
                    overall_status="non_compliant",
                    score=0.0,
                    findings=[
                        Finding(
                            rule_id="framework_support",
                            rule_name="Framework Support",
                            severity="critical",
                            status="fail",
                            description=f"Framework {framework.value} not supported",
                            remediation=f"Use one of: {[f.value for f in self.supported_frameworks]}",
                        )
                    ],
                    recommendations=[
                        f"Framework {framework.value} is not currently supported",
                        f"Supported frameworks: {', '.join(f.value for f in self.supported_frameworks)}",
                    ],
                    metadata=context or {},
                )

                # Record failed scan
                self.metrics.increment_counter(
                    "compliance_scan_failures_total",
                    labels={"framework": framework.value, "reason": "unsupported_framework"},
                )

                return result

            # Get framework-specific checker
            checker = self._framework_checkers[framework]

            # Perform compliance scan
            result = await checker(context, start_time)

            # Record compliance score
            self.metrics.set_gauge(
                "compliance_score", result.score, labels={"framework": framework.value}
            )

            # Record scan duration
            scan_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.metrics.observe_histogram(
                "compliance_scan_duration_seconds",
                scan_duration,
                labels={"framework": framework.value},
            )

            # Record scan status
            status = "passed" if result.overall_status == "compliant" else "failed"
            self.metrics.increment_counter(
                "compliance_scan_results_total",
                labels={"framework": framework.value, "status": status},
            )

            logger.info(
                f"Compliance scan completed for {framework.value}: "
                f"score={result.score:.2f}, status={result.overall_status}"
            )

            return result

        except Exception as e:
            # Record scan error
            self.metrics.increment_counter(
                "compliance_scan_errors_total", labels={"framework": framework.value}
            )

            logger.error(f"Compliance scan failed for {framework.value}: {e}")

            # Return error result
            return ComplianceScanResult(
                framework=framework,
                scan_name=f"Scan {framework.value}",
                target_resource="system",
                target_type="system",
                overall_status="non_compliant",
                score=0.0,
                findings=[
                    Finding(
                        rule_id="scan_execution",
                        rule_name="Scan Execution",
                        severity="critical",
                        status="fail",
                        description=f"Compliance scan failed: {str(e)}",
                        remediation="Review scan configuration and system status",
                    )
                ],
                recommendations=["Fix scan execution errors", "Review system logs"],
                metadata=context or {},
            )

    async def get_supported_frameworks(self) -> list[ComplianceFramework]:
        """
        Get list of supported compliance frameworks.

        Returns:
            List of supported frameworks
        """
        return self.supported_frameworks.copy()

    async def validate_context(self, context: dict[str, Any]) -> dict[str, Any]:
        """
        Validate and enrich compliance scan context.

        Args:
            context: Original scan context

        Returns:
            Validated and enriched context
        """
        try:
            enriched_context = context.copy()

            # Add system metadata
            enriched_context.update(
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "system_type": "microservices",
                    "framework": "marty_msf",
                    "scan_version": "1.0.0",
                }
            )

            # Validate required fields based on context
            if "security_configuration" in context:
                sec_config = context["security_configuration"]
                enriched_context["security_features"] = {
                    "authentication_enabled": bool(sec_config.get("auth_providers")),
                    "authorization_enabled": bool(sec_config.get("policy_engines")),
                    "encryption_enabled": bool(sec_config.get("encryption_config")),
                    "audit_logging_enabled": bool(sec_config.get("audit_config")),
                }

            return enriched_context

        except Exception as e:
            logger.warning(f"Context validation failed: {e}")
            return context

    # Framework-specific compliance checkers

    async def _scan_gdpr_compliance(
        self, context: dict[str, Any], start_time: datetime
    ) -> ComplianceScanResult:
        """Scan for GDPR compliance."""
        findings = []
        score = 1.0

        # Data processing consent
        if not context.get("consent_management", False):
            findings.append(
                {
                    "severity": "critical",
                    "requirement": "Article 6 - Lawfulness of processing",
                    "message": "No consent management system detected",
                    "recommendation": "Implement consent management for data processing",
                }
            )
            score -= 0.4

        # Data retention policies
        if not context.get("data_retention_policies", False):
            findings.append(
                {
                    "severity": "high",
                    "requirement": "Article 17 - Right to erasure",
                    "message": "No data retention policies configured",
                    "recommendation": "Define and implement data retention policies",
                }
            )
            score -= 0.3

        # Data portability
        if not context.get("data_portability", False):
            findings.append(
                {
                    "severity": "medium",
                    "requirement": "Article 20 - Right to data portability",
                    "message": "Data export functionality not implemented",
                    "recommendation": "Implement data export capabilities",
                }
            )
            score -= 0.2

        # Privacy by design
        if not context.get("privacy_by_design", False):
            findings.append(
                {
                    "severity": "medium",
                    "requirement": "Article 25 - Data protection by design",
                    "message": "Privacy by design principles not implemented",
                    "recommendation": "Integrate privacy controls into system design",
                }
            )
            score -= 0.1

        score = max(0.0, score)

        return ComplianceScanResult(
            framework=ComplianceFramework.GDPR,
            scan_name=f"GDPR Scan {int(start_time.timestamp())}",
            target_resource="system",
            target_type="system",
            overall_status="compliant" if score >= 0.8 else "non_compliant",
            score=score,
            findings=[
                Finding(
                    rule_id=f.get("requirement", "unknown"),
                    rule_name=f.get("requirement", "unknown"),
                    severity=f.get("severity", "medium"),
                    status="fail",
                    description=f.get("message", ""),
                    remediation=f.get("recommendation", ""),
                ) for f in findings
            ],
            recommendations=[
                "Implement comprehensive consent management",
                "Establish data retention and deletion policies",
                "Enable data portability features",
                "Apply privacy by design principles",
            ],
            metadata=context or {},
        )

    async def _scan_hipaa_compliance(
        self, context: dict[str, Any], start_time: datetime
    ) -> ComplianceScanResult:
        """Scan for HIPAA compliance."""
        findings = []
        score = 1.0

        # Encryption at rest
        if not context.get("encryption_at_rest", False):
            findings.append(
                {
                    "severity": "critical",
                    "requirement": "164.312(a)(2)(iv) - Encryption",
                    "message": "Data encryption at rest not enabled",
                    "recommendation": "Enable encryption for all stored PHI data",
                }
            )
            score -= 0.4

        # Encryption in transit
        if not context.get("encryption_in_transit", False):
            findings.append(
                {
                    "severity": "critical",
                    "requirement": "164.312(e)(1) - Transmission security",
                    "message": "Data encryption in transit not enabled",
                    "recommendation": "Enable TLS/SSL for all data transmission",
                }
            )
            score -= 0.4

        # Access controls
        if not context.get("access_controls", False):
            findings.append(
                {
                    "severity": "high",
                    "requirement": "164.312(a)(1) - Access control",
                    "message": "Proper access controls not implemented",
                    "recommendation": "Implement role-based access controls",
                }
            )
            score -= 0.2

        score = max(0.0, score)

        return ComplianceScanResult(
            framework=ComplianceFramework.HIPAA,
            scan_name=f"HIPAA Scan {int(start_time.timestamp())}",
            target_resource="system",
            target_type="system",
            overall_status="compliant" if score >= 0.8 else "non_compliant",
            score=score,
            findings=[
                Finding(
                    rule_id=f.get("requirement", "unknown"),
                    rule_name=f.get("requirement", "unknown"),
                    severity=f.get("severity", "medium"),
                    status="fail",
                    description=f.get("message", ""),
                    remediation=f.get("recommendation", ""),
                ) for f in findings
            ],
            recommendations=[
                "Enable encryption for all PHI data",
                "Implement secure transmission protocols",
                "Establish comprehensive access controls",
                "Regular security assessments",
            ],
            metadata=context or {},
        )

    async def _scan_sox_compliance(
        self, context: dict[str, Any], start_time: datetime
    ) -> ComplianceScanResult:
        """Scan for SOX compliance."""
        findings = []
        score = 1.0

        # Audit trails
        if not context.get("audit_logging", False):
            findings.append(
                {
                    "severity": "critical",
                    "requirement": "Section 302 - Corporate responsibility",
                    "message": "Comprehensive audit trails not implemented",
                    "recommendation": "Enable detailed audit logging for all financial operations",
                }
            )
            score -= 0.4

        # Segregation of duties
        if not context.get("segregation_of_duties", False):
            findings.append(
                {
                    "severity": "high",
                    "requirement": "Section 404 - Management assessment",
                    "message": "Segregation of duties not enforced",
                    "recommendation": "Implement role separation for critical operations",
                }
            )
            score -= 0.3

        # Change management
        if not context.get("change_management", False):
            findings.append(
                {
                    "severity": "medium",
                    "requirement": "Section 404 - Internal control assessment",
                    "message": "Change management controls not implemented",
                    "recommendation": "Establish formal change management processes",
                }
            )
            score -= 0.3

        score = max(0.0, score)

        return ComplianceScanResult(
            framework=ComplianceFramework.SOX,
            scan_name=f"SOX Scan {int(start_time.timestamp())}",
            target_resource="system",
            target_type="system",
            overall_status="compliant" if score >= 0.8 else "non_compliant",
            score=score,
            findings=[
                Finding(
                    rule_id=f.get("requirement", "unknown"),
                    rule_name=f.get("requirement", "unknown"),
                    severity=f.get("severity", "medium"),
                    status="fail",
                    description=f.get("message", ""),
                    remediation=f.get("recommendation", ""),
                ) for f in findings
            ],
            recommendations=[
                "Implement comprehensive audit trails",
                "Enforce segregation of duties",
                "Establish change management controls",
                "Regular internal assessments",
            ],
            metadata=context or {},
        )

    async def _scan_pci_compliance(
        self, context: dict[str, Any], start_time: datetime
    ) -> ComplianceScanResult:
        """Scan for PCI DSS compliance."""
        findings = []
        score = 1.0

        # Network security
        if not context.get("firewall_protection", False):
            findings.append(
                {
                    "severity": "critical",
                    "requirement": "Requirement 1 - Firewall configuration",
                    "message": "Firewall protection not properly configured",
                    "recommendation": "Implement and maintain firewall configuration",
                }
            )
            score -= 0.3

        # Encryption
        if not context.get("cardholder_data_encryption", False):
            findings.append(
                {
                    "severity": "critical",
                    "requirement": "Requirement 3 - Protect stored cardholder data",
                    "message": "Cardholder data encryption not implemented",
                    "recommendation": "Encrypt all stored cardholder data",
                }
            )
            score -= 0.4

        # Access controls
        if not context.get("access_restrictions", False):
            findings.append(
                {
                    "severity": "high",
                    "requirement": "Requirement 7 - Restrict access",
                    "message": "Access restrictions not properly implemented",
                    "recommendation": "Implement need-to-know access restrictions",
                }
            )
            score -= 0.2

        # Monitoring
        if not context.get("network_monitoring", False):
            findings.append(
                {
                    "severity": "medium",
                    "requirement": "Requirement 10 - Log and monitor",
                    "message": "Network monitoring not adequately implemented",
                    "recommendation": "Implement comprehensive network monitoring",
                }
            )
            score -= 0.1

        score = max(0.0, score)

        return ComplianceScanResult(
            framework=ComplianceFramework.PCI_DSS,
            scan_name=f"PCI Scan {int(start_time.timestamp())}",
            target_resource="system",
            target_type="system",
            overall_status="compliant" if score >= 0.8 else "non_compliant",
            score=score,
            findings=[
                Finding(
                    rule_id=f.get("requirement", "unknown"),
                    rule_name=f.get("requirement", "unknown"),
                    severity=f.get("severity", "medium"),
                    status="fail",
                    description=f.get("message", ""),
                    remediation=f.get("recommendation", ""),
                ) for f in findings
            ],
            recommendations=[
                "Maintain secure network architecture",
                "Protect cardholder data with encryption",
                "Implement strong access controls",
                "Monitor and test networks regularly",
            ],
            metadata=context or {},
        )

    async def _scan_iso27001_compliance(
        self, context: dict[str, Any], start_time: datetime
    ) -> ComplianceScanResult:
        """Scan for ISO 27001 compliance."""
        findings = []
        score = 1.0

        # Information security policy
        if not context.get("security_policy", False):
            findings.append(
                {
                    "severity": "high",
                    "requirement": "A.5.1.1 - Information security policies",
                    "message": "Information security policy not defined",
                    "recommendation": "Establish comprehensive information security policy",
                }
            )
            score -= 0.3

        # Risk management
        if not context.get("risk_assessment", False):
            findings.append(
                {
                    "severity": "high",
                    "requirement": "A.12.6.1 - Management of technical vulnerabilities",
                    "message": "Risk assessment process not implemented",
                    "recommendation": "Implement regular risk assessment procedures",
                }
            )
            score -= 0.3

        # Access management
        if not context.get("access_management", False):
            findings.append(
                {
                    "severity": "medium",
                    "requirement": "A.9.1.1 - Access control policy",
                    "message": "Access management not properly implemented",
                    "recommendation": "Implement comprehensive access management",
                }
            )
            score -= 0.2

        # Incident management
        if not context.get("incident_response", False):
            findings.append(
                {
                    "severity": "medium",
                    "requirement": "A.16.1.1 - Incident management responsibilities",
                    "message": "Incident response procedures not defined",
                    "recommendation": "Establish incident response procedures",
                }
            )
            score -= 0.2

        score = max(0.0, score)

        return ComplianceScanResult(
            framework=ComplianceFramework.ISO27001,
            scan_name=f"ISO27001 Scan {int(start_time.timestamp())}",
            target_resource="system",
            target_type="system",
            overall_status="compliant" if score >= 0.8 else "non_compliant",
            score=score,
            findings=[
                Finding(
                    rule_id=f.get("requirement", "unknown"),
                    rule_name=f.get("requirement", "unknown"),
                    severity=f.get("severity", "medium"),
                    status="fail",
                    description=f.get("message", ""),
                    remediation=f.get("recommendation", ""),
                ) for f in findings
            ],
            recommendations=[
                "Establish information security policies",
                "Implement risk assessment procedures",
                "Deploy comprehensive access management",
                "Define incident response procedures",
            ],
            metadata=context or {},
        )

    async def _scan_nist_compliance(
        self, context: dict[str, Any], start_time: datetime
    ) -> ComplianceScanResult:
        """Scan for NIST Cybersecurity Framework compliance."""
        findings = []
        score = 1.0

        # Identify function
        if not context.get("asset_inventory", False):
            findings.append(
                {
                    "severity": "high",
                    "requirement": "ID.AM - Asset Management",
                    "message": "Asset inventory not maintained",
                    "recommendation": "Maintain comprehensive asset inventory",
                }
            )
            score -= 0.2

        # Protect function
        if not context.get("access_controls", False):
            findings.append(
                {
                    "severity": "high",
                    "requirement": "PR.AC - Identity Management and Access Control",
                    "message": "Access controls not properly implemented",
                    "recommendation": "Implement robust access controls",
                }
            )
            score -= 0.2

        # Detect function
        if not context.get("security_monitoring", False):
            findings.append(
                {
                    "severity": "medium",
                    "requirement": "DE.CM - Security Continuous Monitoring",
                    "message": "Security monitoring not adequately implemented",
                    "recommendation": "Enable continuous security monitoring",
                }
            )
            score -= 0.2

        # Respond function
        if not context.get("incident_response", False):
            findings.append(
                {
                    "severity": "medium",
                    "requirement": "RS.RP - Response Planning",
                    "message": "Incident response procedures not defined",
                    "recommendation": "Develop incident response procedures",
                }
            )
            score -= 0.2

        # Recover function
        if not context.get("backup_recovery", False):
            findings.append(
                {
                    "severity": "medium",
                    "requirement": "RC.RP - Recovery Planning",
                    "message": "Backup and recovery capabilities not implemented",
                    "recommendation": "Establish backup and recovery procedures",
                }
            )
            score -= 0.2

        score = max(0.0, score)

        return ComplianceScanResult(
            framework=ComplianceFramework.NIST,
            scan_name=f"NIST Scan {int(start_time.timestamp())}",
            target_resource="system",
            target_type="system",
            overall_status="compliant" if score >= 0.8 else "non_compliant",
            score=score,
            findings=[
                Finding(
                    rule_id=f.get("requirement", "unknown"),
                    rule_name=f.get("requirement", "unknown"),
                    severity=f.get("severity", "medium"),
                    status="fail",
                    description=f.get("message", ""),
                    remediation=f.get("recommendation", ""),
                ) for f in findings
            ],
            recommendations=[
                "Maintain comprehensive asset inventory",
                "Implement robust access controls",
                "Enable security monitoring and detection",
                "Develop incident response procedures",
                "Establish backup and recovery procedures",
            ],
            metadata=context or {},
        )
