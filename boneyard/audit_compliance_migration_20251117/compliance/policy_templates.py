"""
Regulatory Compliance Templates and Policies for Marty Microservices Framework

Provides pre-configured compliance templates and policies for major regulatory frameworks:
- GDPR (General Data Protection Regulation)
- HIPAA (Health Insurance Portability and Accountability Act)
- SOX (Sarbanes-Oxley Act)
- PCI DSS (Payment Card Industry Data Security Standard)
- ISO 27001 (Information Security Management)
- NIST Cybersecurity Framework
"""

import builtins
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, list


@dataclass
class CompliancePolicy:
    """Compliance policy template"""

    policy_id: str
    name: str
    framework: str
    version: str
    effective_date: datetime

    # Policy content
    description: str
    scope: str
    requirements: builtins.list[str]
    implementation_guidance: builtins.list[str]

    # Controls and procedures
    controls: builtins.list[builtins.dict[str, Any]]
    procedures: builtins.list[builtins.dict[str, Any]]

    # Compliance details
    regulatory_references: builtins.list[str]
    risk_level: str
    compliance_frequency: str  # daily, weekly, monthly, quarterly, annually

    # Responsibility
    responsible_roles: builtins.list[str]
    approval_required: bool = True

    def to_dict(self) -> builtins.dict[str, Any]:
        return {**asdict(self), "effective_date": self.effective_date.isoformat()}


class GDPRComplianceTemplates:
    """GDPR compliance templates and policies"""

    @staticmethod
    def get_data_protection_policy() -> CompliancePolicy:
        """Data Protection and Privacy Policy (GDPR Article 32)"""
        return CompliancePolicy(
            policy_id="GDPR_DP_001",
            name="Data Protection and Privacy Policy",
            framework="GDPR",
            version="1.0",
            effective_date=datetime.now(),
            description="Comprehensive data protection policy ensuring GDPR compliance for personal data processing",
            scope="All systems, applications, and processes that handle personal data of EU residents",
            requirements=[
                "Implement appropriate technical and organizational measures for data protection",
                "Ensure data processing is lawful, fair, and transparent",
                "Collect personal data only for specified, explicit, and legitimate purposes",
                "Ensure data accuracy and keep data up to date",
                "Limit data retention to what is necessary for the purposes",
                "Implement security measures including encryption and access controls",
                "Conduct Data Protection Impact Assessments (DPIAs) when required",
                "Maintain records of processing activities",
                "Implement breach notification procedures",
                "Respect data subject rights including access, rectification, and erasure",
            ],
            implementation_guidance=[
                "Deploy end-to-end encryption for all personal data transmission",
                "Implement role-based access controls with regular reviews",
                "Establish automated data retention and deletion policies",
                "Create user-friendly consent management interfaces",
                "Develop incident response procedures for data breaches",
                "Train staff on GDPR requirements and data handling procedures",
                "Implement privacy by design in all new systems",
                "Establish vendor management procedures for data processors",
            ],
            controls=[
                {
                    "control_id": "GDPR_DP_001_C01",
                    "name": "Data Encryption",
                    "description": "All personal data must be encrypted at rest and in transit",
                    "implementation": "AES-256 encryption for data at rest, TLS 1.3 for data in transit",
                    "testing_frequency": "quarterly",
                    "responsible_role": "Security Engineer",
                },
                {
                    "control_id": "GDPR_DP_001_C02",
                    "name": "Access Controls",
                    "description": "Implement role-based access controls for personal data",
                    "implementation": "RBAC system with principle of least privilege",
                    "testing_frequency": "monthly",
                    "responsible_role": "Identity Administrator",
                },
                {
                    "control_id": "GDPR_DP_001_C03",
                    "name": "Data Retention",
                    "description": "Automated deletion of personal data after retention period",
                    "implementation": "Automated data lifecycle management system",
                    "testing_frequency": "monthly",
                    "responsible_role": "Data Protection Officer",
                },
            ],
            procedures=[
                {
                    "procedure_id": "GDPR_DP_001_P01",
                    "name": "Data Subject Access Request",
                    "description": "Process for handling data subject access requests",
                    "steps": [
                        "Verify identity of data subject",
                        "Search all systems for personal data",
                        "Compile comprehensive data report",
                        "Review for third-party data or trade secrets",
                        "Provide data in machine-readable format within 30 days",
                    ],
                },
                {
                    "procedure_id": "GDPR_DP_001_P02",
                    "name": "Data Breach Response",
                    "description": "Response procedure for personal data breaches",
                    "steps": [
                        "Identify and contain the breach immediately",
                        "Assess the risk to data subjects",
                        "Notify supervisory authority within 72 hours if high risk",
                        "Notify affected data subjects if high risk to rights and freedoms",
                        "Document the breach and response actions",
                        "Review and improve security measures",
                    ],
                },
            ],
            regulatory_references=[
                "GDPR Article 32 - Security of processing",
                "GDPR Article 25 - Data protection by design and by default",
                "GDPR Article 33 - Notification of a personal data breach to the supervisory authority",
                "GDPR Article 34 - Communication of a personal data breach to the data subject",
            ],
            risk_level="High",
            compliance_frequency="continuous",
            responsible_roles=[
                "Data Protection Officer",
                "Security Officer",
                "System Administrator",
            ],
        )

    @staticmethod
    def get_consent_management_policy() -> CompliancePolicy:
        """Consent Management Policy (GDPR Article 7)"""
        return CompliancePolicy(
            policy_id="GDPR_CM_001",
            name="Consent Management Policy",
            framework="GDPR",
            version="1.0",
            effective_date=datetime.now(),
            description="Policy for obtaining, recording, and managing user consent for data processing",
            scope="All systems that process personal data based on consent",
            requirements=[
                "Obtain explicit consent before processing personal data",
                "Ensure consent is freely given, specific, informed, and unambiguous",
                "Maintain records of when and how consent was obtained",
                "Provide easy mechanisms for consent withdrawal",
                "Regularly review and refresh consent where necessary",
                "Implement granular consent for different processing purposes",
            ],
            implementation_guidance=[
                "Implement consent banners with clear opt-in mechanisms",
                "Maintain consent databases with audit trails",
                "Provide user dashboards for consent management",
                "Implement API endpoints for consent verification",
                "Regular consent refresh campaigns for existing users",
            ],
            controls=[
                {
                    "control_id": "GDPR_CM_001_C01",
                    "name": "Consent Recording",
                    "description": "All consent must be recorded with timestamp and proof",
                    "implementation": "Consent management system with audit logging",
                    "testing_frequency": "monthly",
                    "responsible_role": "Privacy Engineer",
                }
            ],
            procedures=[
                {
                    "procedure_id": "GDPR_CM_001_P01",
                    "name": "Consent Withdrawal",
                    "description": "Process for handling consent withdrawal requests",
                    "steps": [
                        "Receive and acknowledge withdrawal request",
                        "Stop processing based on withdrawn consent immediately",
                        "Update consent records",
                        "Confirm withdrawal to data subject",
                    ],
                }
            ],
            regulatory_references=["GDPR Article 7 - Conditions for consent"],
            risk_level="High",
            compliance_frequency="continuous",
            responsible_roles=["Data Protection Officer", "Privacy Engineer"],
        )


class HIPAAComplianceTemplates:
    """HIPAA compliance templates and policies"""

    @staticmethod
    def get_phi_access_policy() -> CompliancePolicy:
        """PHI Access Control Policy (HIPAA 164.312(a))"""
        return CompliancePolicy(
            policy_id="HIPAA_AC_001",
            name="Protected Health Information Access Control Policy",
            framework="HIPAA",
            version="1.0",
            effective_date=datetime.now(),
            description="Policy for controlling access to Protected Health Information (PHI)",
            scope="All systems, applications, and personnel that handle PHI",
            requirements=[
                "Implement role-based access controls for PHI",
                "Ensure access is limited to minimum necessary for job function",
                "Maintain audit logs of all PHI access",
                "Implement user authentication and authorization",
                "Regular access reviews and certifications",
                "Immediate access revocation upon termination",
                "Emergency access procedures for patient care",
            ],
            implementation_guidance=[
                "Deploy identity and access management (IAM) system",
                "Implement multi-factor authentication for PHI access",
                "Create role-based access matrices",
                "Establish automated access provisioning and deprovisioning",
                "Implement session management and timeout controls",
                "Deploy privileged access management for administrative accounts",
            ],
            controls=[
                {
                    "control_id": "HIPAA_AC_001_C01",
                    "name": "User Authentication",
                    "description": "Multi-factor authentication required for PHI access",
                    "implementation": "MFA with at least two authentication factors",
                    "testing_frequency": "quarterly",
                    "responsible_role": "Security Administrator",
                },
                {
                    "control_id": "HIPAA_AC_001_C02",
                    "name": "Access Logging",
                    "description": "All PHI access must be logged and monitored",
                    "implementation": "Comprehensive audit logging with SIEM integration",
                    "testing_frequency": "monthly",
                    "responsible_role": "Security Analyst",
                },
            ],
            procedures=[
                {
                    "procedure_id": "HIPAA_AC_001_P01",
                    "name": "User Access Provisioning",
                    "description": "Process for granting PHI access to new users",
                    "steps": [
                        "Receive access request with business justification",
                        "Verify job role and minimum necessary requirements",
                        "Obtain manager approval",
                        "Provision access with appropriate role assignment",
                        "Notify user and provide training on PHI handling",
                        "Document access grant in audit log",
                    ],
                }
            ],
            regulatory_references=[
                "45 CFR 164.312(a)(1) - Access control",
                "45 CFR 164.312(d) - Person or entity authentication",
            ],
            risk_level="Critical",
            compliance_frequency="continuous",
            responsible_roles=[
                "HIPAA Security Officer",
                "System Administrator",
                "Privacy Officer",
            ],
        )

    @staticmethod
    def get_audit_logging_policy() -> CompliancePolicy:
        """Audit Logging Policy (HIPAA 164.312(b))"""
        return CompliancePolicy(
            policy_id="HIPAA_AL_001",
            name="Audit Logging and Monitoring Policy",
            framework="HIPAA",
            version="1.0",
            effective_date=datetime.now(),
            description="Policy for audit logging and monitoring of PHI access and system activities",
            scope="All systems that process, store, or transmit PHI",
            requirements=[
                "Log all access to PHI including read, write, modify, and delete operations",
                "Log user authentication and authorization events",
                "Log system and application events affecting PHI",
                "Maintain audit logs for minimum 6 years",
                "Protect audit log integrity and prevent tampering",
                "Regular review and analysis of audit logs",
                "Automated alerting for suspicious activities",
            ],
            implementation_guidance=[
                "Deploy centralized log management system",
                "Implement log aggregation from all PHI systems",
                "Establish log retention and archival procedures",
                "Create automated monitoring rules and alerts",
                "Implement log integrity protection mechanisms",
                "Establish incident response procedures for log anomalies",
            ],
            controls=[
                {
                    "control_id": "HIPAA_AL_001_C01",
                    "name": "Comprehensive Logging",
                    "description": "All PHI-related activities must be logged",
                    "implementation": "Centralized logging with structured log format",
                    "testing_frequency": "monthly",
                    "responsible_role": "Security Engineer",
                }
            ],
            procedures=[],
            regulatory_references=["45 CFR 164.312(b) - Audit controls"],
            risk_level="High",
            compliance_frequency="continuous",
            responsible_roles=["HIPAA Security Officer", "Security Analyst"],
        )


class SOXComplianceTemplates:
    """SOX compliance templates and policies"""

    @staticmethod
    def get_change_management_policy() -> CompliancePolicy:
        """IT Change Management Policy (SOX 404)"""
        return CompliancePolicy(
            policy_id="SOX_CM_001",
            name="IT Change Management Policy",
            framework="SOX",
            version="1.0",
            effective_date=datetime.now(),
            description="Policy for managing changes to IT systems that support financial reporting",
            scope="All IT systems that support financial reporting processes",
            requirements=[
                "All changes must be formally documented and approved",
                "Implement segregation of duties in change process",
                "Require testing before production deployment",
                "Maintain change logs and evidence",
                "Emergency change procedures with post-implementation review",
                "Regular review of change management effectiveness",
            ],
            implementation_guidance=[
                "Deploy change management workflow system",
                "Establish change advisory board (CAB)",
                "Implement automated testing and deployment pipelines",
                "Create change templates and documentation standards",
                "Establish emergency change procedures",
                "Regular training on change management procedures",
            ],
            controls=[
                {
                    "control_id": "SOX_CM_001_C01",
                    "name": "Change Approval",
                    "description": "All changes require documented approval",
                    "implementation": "Electronic change approval workflow",
                    "testing_frequency": "quarterly",
                    "responsible_role": "Change Manager",
                }
            ],
            procedures=[],
            regulatory_references=["SOX Section 404 - Management Assessment of Internal Controls"],
            risk_level="High",
            compliance_frequency="continuous",
            responsible_roles=[
                "Change Manager",
                "IT Operations",
                "Financial Systems Manager",
            ],
        )


class PCIDSSComplianceTemplates:
    """PCI DSS compliance templates and policies"""

    @staticmethod
    def get_cardholder_data_protection_policy() -> CompliancePolicy:
        """Cardholder Data Protection Policy (PCI DSS Requirement 3)"""
        return CompliancePolicy(
            policy_id="PCI_CDP_001",
            name="Cardholder Data Protection Policy",
            framework="PCI DSS",
            version="1.0",
            effective_date=datetime.now(),
            description="Policy for protecting stored cardholder data",
            scope="All systems that store, process, or transmit cardholder data",
            requirements=[
                "Minimize cardholder data storage and retention",
                "Encrypt stored cardholder data using strong cryptography",
                "Mask PAN (Primary Account Number) when displayed",
                "Secure cardholder data transmission over public networks",
                "Implement secure key management procedures",
                "Regular testing of encryption systems",
            ],
            implementation_guidance=[
                "Implement data classification and discovery tools",
                "Deploy strong encryption for cardholder data storage",
                "Establish secure key management infrastructure",
                "Implement tokenization where possible",
                "Regular penetration testing of payment systems",
            ],
            controls=[
                {
                    "control_id": "PCI_CDP_001_C01",
                    "name": "Data Encryption",
                    "description": "All stored cardholder data must be encrypted",
                    "implementation": "AES-256 encryption with secure key management",
                    "testing_frequency": "quarterly",
                    "responsible_role": "Payment Security Manager",
                }
            ],
            procedures=[],
            regulatory_references=["PCI DSS Requirement 3 - Protect stored cardholder data"],
            risk_level="Critical",
            compliance_frequency="continuous",
            responsible_roles=["Payment Security Manager", "Security Engineer"],
        )


class ISO27001ComplianceTemplates:
    """ISO 27001 compliance templates and policies"""

    @staticmethod
    def get_information_security_policy() -> CompliancePolicy:
        """Information Security Management Policy (ISO 27001)"""
        return CompliancePolicy(
            policy_id="ISO_ISM_001",
            name="Information Security Management Policy",
            framework="ISO 27001",
            version="1.0",
            effective_date=datetime.now(),
            description="Comprehensive information security management policy",
            scope="All information systems and assets within the organization",
            requirements=[
                "Establish information security management system (ISMS)",
                "Conduct regular risk assessments",
                "Implement appropriate security controls",
                "Provide security awareness training",
                "Monitor and measure security effectiveness",
                "Continual improvement of security posture",
            ],
            implementation_guidance=[
                "Establish security governance structure",
                "Implement risk management framework",
                "Deploy security monitoring and incident response",
                "Create security policies and procedures",
                "Regular security audits and assessments",
            ],
            controls=[],
            procedures=[],
            regulatory_references=["ISO/IEC 27001:2013 - Information security management systems"],
            risk_level="High",
            compliance_frequency="annually",
            responsible_roles=[
                "Chief Information Security Officer",
                "Security Manager",
            ],
        )


class CompliancePolicyLibrary:
    """Centralized compliance policy library"""

    def __init__(self):
        self.policies: builtins.dict[str, CompliancePolicy] = {}
        self._initialize_policies()

    def _initialize_policies(self):
        """Initialize all compliance policies"""

        # GDPR Policies
        gdpr_policies = [
            GDPRComplianceTemplates.get_data_protection_policy(),
            GDPRComplianceTemplates.get_consent_management_policy(),
        ]

        # HIPAA Policies
        hipaa_policies = [
            HIPAAComplianceTemplates.get_phi_access_policy(),
            HIPAAComplianceTemplates.get_audit_logging_policy(),
        ]

        # SOX Policies
        sox_policies = [SOXComplianceTemplates.get_change_management_policy()]

        # PCI DSS Policies
        pci_policies = [PCIDSSComplianceTemplates.get_cardholder_data_protection_policy()]

        # ISO 27001 Policies
        iso_policies = [ISO27001ComplianceTemplates.get_information_security_policy()]

        # Add all policies to library
        all_policies = gdpr_policies + hipaa_policies + sox_policies + pci_policies + iso_policies

        for policy in all_policies:
            self.policies[policy.policy_id] = policy

        print(f"Initialized {len(all_policies)} compliance policies")

    def get_policy(self, policy_id: str) -> CompliancePolicy | None:
        """Get policy by ID"""
        return self.policies.get(policy_id)

    def get_policies_by_framework(self, framework: str) -> builtins.list[CompliancePolicy]:
        """Get all policies for a specific framework"""
        return [policy for policy in self.policies.values() if policy.framework == framework]

    def get_all_policies(self) -> builtins.list[CompliancePolicy]:
        """Get all policies"""
        return list(self.policies.values())

    def export_policies(self, framework: str | None = None) -> str:
        """Export policies to JSON"""
        if framework:
            policies = self.get_policies_by_framework(framework)
        else:
            policies = self.get_all_policies()

        export_data = {
            "exported_at": datetime.now().isoformat(),
            "framework": framework,
            "policy_count": len(policies),
            "policies": [policy.to_dict() for policy in policies],
        }

        return json.dumps(export_data, indent=2)

    def get_compliance_summary(self) -> builtins.dict[str, Any]:
        """Get summary of all compliance policies"""

        frameworks = {}
        total_controls = 0
        total_procedures = 0

        for policy in self.policies.values():
            framework = policy.framework
            if framework not in frameworks:
                frameworks[framework] = {
                    "policy_count": 0,
                    "controls": 0,
                    "procedures": 0,
                    "risk_levels": {},
                }

            frameworks[framework]["policy_count"] += 1
            frameworks[framework]["controls"] += len(policy.controls)
            frameworks[framework]["procedures"] += len(policy.procedures)

            risk_level = policy.risk_level
            if risk_level not in frameworks[framework]["risk_levels"]:
                frameworks[framework]["risk_levels"][risk_level] = 0
            frameworks[framework]["risk_levels"][risk_level] += 1

            total_controls += len(policy.controls)
            total_procedures += len(policy.procedures)

        return {
            "total_policies": len(self.policies),
            "total_controls": total_controls,
            "total_procedures": total_procedures,
            "frameworks": frameworks,
        }


# Example usage
def main():
    """Example usage of compliance policy library"""

    print("=== Compliance Policy Library Demo ===")

    # Initialize policy library
    policy_library = CompliancePolicyLibrary()

    # Get compliance summary
    summary = policy_library.get_compliance_summary()
    print(f"Total Policies: {summary['total_policies']}")
    print(f"Total Controls: {summary['total_controls']}")
    print(f"Total Procedures: {summary['total_procedures']}")

    print("\nFramework Summary:")
    for framework, details in summary["frameworks"].items():
        print(
            f"{framework}: {details['policy_count']} policies, "
            f"{details['controls']} controls, {details['procedures']} procedures"
        )

    # Show GDPR policies
    gdpr_policies = policy_library.get_policies_by_framework("GDPR")
    print(f"\nGDPR Policies ({len(gdpr_policies)}):")
    for policy in gdpr_policies:
        print(f"- {policy.name} ({policy.policy_id})")
        print(f"  Risk Level: {policy.risk_level}")
        print(f"  Controls: {len(policy.controls)}")
        print(f"  Requirements: {len(policy.requirements)}")

    # Export GDPR policies
    gdpr_export = policy_library.export_policies("GDPR")
    print(f"\nGDPR Export Size: {len(gdpr_export)} characters")


if __name__ == "__main__":
    main()
