"""
Unified Compliance Scanner

Integrates with existing compliance infrastructure to provide automated
scanning and validation of security policies and configurations.
"""

import logging
from datetime import datetime, timezone
from typing import Any, Optional, Protocol, runtime_checkable

from ..compliance import ComplianceFramework as ExistingFramework
from ..compliance import ComplianceManager
from ..unified_framework import ComplianceFramework, ComplianceScanner

logger = logging.getLogger(__name__)


class UnifiedComplianceScanner(ComplianceScanner):
    """Unified compliance scanner that integrates existing compliance infrastructure"""

    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.enabled_frameworks = config.get("frameworks", [])

        # Import existing compliance infrastructure
        try:
            self.compliance_manager = ComplianceManager()
            self.existing_framework_mapping = {
                ComplianceFramework.GDPR: ExistingFramework.GDPR,
                ComplianceFramework.HIPAA: ExistingFramework.HIPAA,
                ComplianceFramework.SOX: ExistingFramework.SOX,
                ComplianceFramework.PCI_DSS: ExistingFramework.PCI_DSS,
                ComplianceFramework.ISO27001: ExistingFramework.ISO27001,
                ComplianceFramework.NIST: ExistingFramework.NIST,
            }
        except ImportError:
            logger.warning("Existing compliance infrastructure not available")
            self.compliance_manager = None
            self.existing_framework_mapping = {}

    async def scan_compliance(
        self,
        framework: ComplianceFramework,
        scope: dict[str, Any]
    ) -> dict[str, Any]:
        """Scan for compliance violations"""
        try:
            if self.compliance_manager and framework in self.existing_framework_mapping:
                # Use existing compliance infrastructure
                existing_framework = self.existing_framework_mapping[framework]

                # Collect system context
                context = await self._collect_system_context(scope)

                # Perform compliance assessment
                report = await self.compliance_manager.assess_compliance(existing_framework, context)

                # Convert to unified format
                return self._convert_to_unified_format(report)
            else:
                # Fallback to basic compliance check
                return await self._basic_compliance_scan(framework, scope)

        except Exception as e:
            logger.error(f"Compliance scan error for {framework.value}: {e}")
            return {
                "framework": framework.value,
                "status": "error",
                "error": str(e),
                "violations": [],
                "compliance_score": 0.0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

    async def generate_compliance_report(
        self,
        scan_results: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Generate comprehensive compliance report"""
        try:
            if self.compliance_manager:
                # Use existing report generation infrastructure
                reports = []
                for result in scan_results:
                    # Convert back to existing format if needed
                    reports.append(result)

                # Generate executive summary
                executive_summary = await self.compliance_manager.report_generator.generate_executive_summary(reports)

                return {
                    "executive_summary": executive_summary,
                    "detailed_results": scan_results,
                    "total_frameworks_scanned": len(scan_results),
                    "overall_compliance_score": self._calculate_overall_score(scan_results),
                    "critical_violations": self._extract_critical_violations(scan_results),
                    "generated_at": datetime.now(timezone.utc).isoformat()
                }
            else:
                # Generate basic report
                return self._generate_basic_report(scan_results)

        except Exception as e:
            logger.error(f"Compliance report generation error: {e}")
            return {
                "error": str(e),
                "scan_results": scan_results,
                "generated_at": datetime.now(timezone.utc).isoformat()
            }

    # Private methods

    async def _collect_system_context(self, scope: dict[str, Any]) -> dict[str, Any]:
        """Collect system context for compliance scanning"""
        try:
            # Base context
            context = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "scan_scope": scope,
                "system_type": "microservices",
                "framework": "marty_msf"
            }

            # Add security framework context
            if "security_framework" in scope:
                security_framework = scope["security_framework"]
                context.update({
                    "authentication_methods": getattr(security_framework, "identity_providers", {}).keys(),
                    "policy_engines": getattr(security_framework, "policy_engines", {}).keys(),
                    "service_mesh_enabled": getattr(security_framework, "service_mesh_manager", None) is not None,
                    "active_sessions": len(getattr(security_framework, "active_sessions", {})),
                    "policies_cached": len(getattr(security_framework, "policy_cache", {}))
                })

            # Add service mesh context
            if "service_mesh" in scope:
                mesh_status = scope["service_mesh"]
                context.update({
                    "mesh_type": mesh_status.get("mesh_type"),
                    "mtls_enabled": mesh_status.get("mtls_status", {}).get("enabled", False),
                    "policies_applied": mesh_status.get("policies_applied", 0)
                })

            # Add application context
            if "services" in scope:
                services = scope["services"]
                context.update({
                    "total_services": len(services),
                    "service_types": list({s.get("type", "unknown") for s in services}),
                    "security_enabled_services": len([s for s in services if s.get("security_enabled", False)])
                })

            return context

        except Exception as e:
            logger.error(f"Error collecting system context: {e}")
            return {"error": str(e)}

    async def _basic_compliance_scan(
        self,
        framework: ComplianceFramework,
        scope: dict[str, Any]
    ) -> dict[str, Any]:
        """Perform basic compliance scan without existing infrastructure"""
        try:
            violations = []

            # Basic security checks
            if "security_framework" in scope:
                security_framework = scope["security_framework"]

                # Check authentication
                if not getattr(security_framework, "identity_providers", {}):
                    violations.append({
                        "rule_id": "AUTH_001",
                        "severity": "high",
                        "description": "No identity providers configured",
                        "recommendation": "Configure at least one identity provider"
                    })

                # Check policy engines
                if not getattr(security_framework, "policy_engines", {}):
                    violations.append({
                        "rule_id": "AUTHZ_001",
                        "severity": "high",
                        "description": "No policy engines configured",
                        "recommendation": "Configure at least one policy engine"
                    })

                # Check service mesh security
                if not getattr(security_framework, "service_mesh_manager", None):
                    violations.append({
                        "rule_id": "MESH_001",
                        "severity": "medium",
                        "description": "Service mesh security not enabled",
                        "recommendation": "Enable service mesh security for traffic-level protection"
                    })

            # Framework-specific checks
            if framework == ComplianceFramework.GDPR:
                violations.extend(self._gdpr_specific_checks(scope))
            elif framework == ComplianceFramework.HIPAA:
                violations.extend(self._hipaa_specific_checks(scope))
            elif framework == ComplianceFramework.PCI_DSS:
                violations.extend(self._pci_dss_specific_checks(scope))

            # Calculate compliance score
            total_checks = 10  # Simplified
            compliance_score = max(0.0, (total_checks - len(violations)) / total_checks)

            return {
                "framework": framework.value,
                "status": "completed",
                "violations": violations,
                "compliance_score": compliance_score,
                "total_checks": total_checks,
                "passed_checks": total_checks - len(violations),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }

        except Exception as e:
            logger.error(f"Basic compliance scan error: {e}")
            return {
                "framework": framework.value,
                "status": "error",
                "error": str(e),
                "violations": [],
                "compliance_score": 0.0
            }

    def _gdpr_specific_checks(self, scope: dict[str, Any]) -> list[dict[str, Any]]:
        """Perform GDPR-specific compliance checks"""
        violations = []

        # Data processing consent
        if not scope.get("consent_management", False):
            violations.append({
                "rule_id": "GDPR_001",
                "severity": "critical",
                "description": "No consent management system detected",
                "recommendation": "Implement consent management for data processing"
            })

        # Data retention policies
        if not scope.get("data_retention_policies", False):
            violations.append({
                "rule_id": "GDPR_002",
                "severity": "high",
                "description": "No data retention policies configured",
                "recommendation": "Define and implement data retention policies"
            })

        return violations

    def _hipaa_specific_checks(self, scope: dict[str, Any]) -> list[dict[str, Any]]:
        """Perform HIPAA-specific compliance checks"""
        violations = []

        # Access controls for PHI
        if not scope.get("phi_access_controls", False):
            violations.append({
                "rule_id": "HIPAA_001",
                "severity": "critical",
                "description": "PHI access controls not properly configured",
                "recommendation": "Implement role-based access controls for PHI"
            })

        # Audit logging
        if not scope.get("audit_logging", False):
            violations.append({
                "rule_id": "HIPAA_002",
                "severity": "high",
                "description": "Audit logging not enabled",
                "recommendation": "Enable comprehensive audit logging for PHI access"
            })

        return violations

    def _pci_dss_specific_checks(self, scope: dict[str, Any]) -> list[dict[str, Any]]:
        """Perform PCI DSS-specific compliance checks"""
        violations = []

        # Network segmentation
        if not scope.get("network_segmentation", False):
            violations.append({
                "rule_id": "PCI_001",
                "severity": "critical",
                "description": "Network segmentation not properly implemented",
                "recommendation": "Implement network segmentation for cardholder data environment"
            })

        # Encryption in transit
        if not scope.get("encryption_in_transit", False):
            violations.append({
                "rule_id": "PCI_002",
                "severity": "high",
                "description": "Encryption in transit not enforced",
                "recommendation": "Enforce encryption for all cardholder data transmission"
            })

        return violations

    def _convert_to_unified_format(self, existing_report: Any) -> dict[str, Any]:
        """Convert existing compliance report to unified format"""
        try:
            return {
                "framework": getattr(existing_report, "framework", "unknown"),
                "status": "completed",
                "violations": getattr(existing_report, "violations", []),
                "compliance_score": getattr(existing_report, "compliance_score", 0.0),
                "total_checks": getattr(existing_report, "total_rules_evaluated", 0),
                "passed_checks": getattr(existing_report, "passed_rules", 0),
                "timestamp": getattr(existing_report, "timestamp", datetime.now(timezone.utc).isoformat())
            }
        except Exception:
            return {
                "framework": "unknown",
                "status": "error",
                "error": "Failed to convert existing report format",
                "violations": [],
                "compliance_score": 0.0
            }

    def _calculate_overall_score(self, scan_results: list[dict[str, Any]]) -> float:
        """Calculate overall compliance score across all frameworks"""
        if not scan_results:
            return 0.0

        total_score = sum(result.get("compliance_score", 0.0) for result in scan_results)
        return total_score / len(scan_results)

    def _extract_critical_violations(self, scan_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Extract critical violations from all scan results"""
        critical_violations = []

        for result in scan_results:
            framework = result.get("framework", "unknown")
            violations = result.get("violations", [])

            for violation in violations:
                if violation.get("severity") == "critical":
                    violation["framework"] = framework
                    critical_violations.append(violation)

        return critical_violations

    def _generate_basic_report(self, scan_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Generate basic compliance report"""
        return {
            "executive_summary": {
                "total_frameworks": len(scan_results),
                "overall_compliance_score": self._calculate_overall_score(scan_results),
                "critical_violations": len(self._extract_critical_violations(scan_results)),
                "status": "completed"
            },
            "detailed_results": scan_results,
            "recommendations": [
                "Review and address all critical violations immediately",
                "Implement missing security controls",
                "Regular compliance monitoring and assessment"
            ],
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
