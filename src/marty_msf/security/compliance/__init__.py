"""
Compliance Automation Framework for Marty Microservices Framework

Provides comprehensive compliance monitoring and automation including:
- Automated policy enforcement and validation
- Regulatory compliance frameworks (SOX, GDPR, HIPAA, PCI DSS)
- Continuous compliance monitoring and reporting
- Audit trail management and retention
- Risk assessment and remediation
- Compliance dashboard and alerting
"""

import asyncio
import builtins
import json
import re
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from prometheus_client import Counter

from ..interfaces import ComplianceFramework

# External dependencies
try:

    ASYNC_AVAILABLE = True
    REDIS_AVAILABLE = True
except ImportError:
    ASYNC_AVAILABLE = False
    REDIS_AVAILABLE = False


# Import the unified ComplianceFramework from interfaces


class ComplianceStatus(Enum):
    """Compliance status levels"""

    COMPLIANT = "compliant"
    NON_COMPLIANT = "non_compliant"
    PARTIALLY_COMPLIANT = "partially_compliant"
    NOT_ASSESSED = "not_assessed"
    REMEDIATION_REQUIRED = "remediation_required"


class RiskLevel(Enum):
    """Risk assessment levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEventType(Enum):
    """Types of audit events"""

    USER_ACCESS = "user_access"
    DATA_ACCESS = "data_access"
    SYSTEM_CHANGE = "system_change"
    CONFIGURATION_CHANGE = "configuration_change"
    SECURITY_EVENT = "security_event"
    COMPLIANCE_VIOLATION = "compliance_violation"
    POLICY_CHANGE = "policy_change"
    ADMIN_ACTION = "admin_action"


@dataclass
class ComplianceRule:
    """Compliance rule definition"""

    rule_id: str
    name: str
    description: str
    framework: ComplianceFramework
    category: str
    severity: RiskLevel

    # Rule logic
    conditions: builtins.dict[str, Any]
    remediation_steps: builtins.list[str]

    # Metadata
    control_id: str
    references: builtins.list[str] = field(default_factory=list)
    tags: builtins.set[str] = field(default_factory=set)

    # Status
    is_active: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class ComplianceViolation:
    """Compliance violation record"""

    violation_id: str
    rule_id: str
    framework: ComplianceFramework
    severity: RiskLevel

    # Violation details
    description: str
    detected_at: datetime
    source_system: str
    affected_resources: builtins.list[str] = field(default_factory=list)

    # Context
    evidence: builtins.dict[str, Any] = field(default_factory=dict)
    impact_assessment: str = ""

    # Remediation
    status: ComplianceStatus = ComplianceStatus.NON_COMPLIANT
    remediation_actions: builtins.list[str] = field(default_factory=list)
    remediated_at: datetime | None = None
    assigned_to: str | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "detected_at": self.detected_at.isoformat(),
            "remediated_at": self.remediated_at.isoformat() if self.remediated_at else None,
            "framework": self.framework.value,
            "severity": self.severity.value,
            "status": self.status.value,
        }


@dataclass
class AuditEvent:
    """Audit trail event"""

    event_id: str
    event_type: AuditEventType
    timestamp: datetime

    # Event details
    user_id: str | None
    session_id: str | None
    source_ip: str
    user_agent: str

    # Action details
    action: str
    resource: str
    resource_id: str | None

    # Context
    details: builtins.dict[str, Any] = field(default_factory=dict)
    outcome: str = "success"  # success, failure, error

    # Compliance relevance
    compliance_frameworks: builtins.set[ComplianceFramework] = field(default_factory=set)
    sensitive_data_involved: bool = False

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "compliance_frameworks": [f.value for f in self.compliance_frameworks],
        }


@dataclass
class ComplianceReport:
    """Compliance assessment report"""

    report_id: str
    framework: ComplianceFramework
    generated_at: datetime

    # Assessment results
    overall_status: ComplianceStatus
    compliance_score: float  # 0.0 - 1.0

    # Rule assessments
    total_rules: int
    compliant_rules: int
    non_compliant_rules: int
    not_assessed_rules: int

    # Violations
    violations: builtins.list[ComplianceViolation] = field(default_factory=list)
    critical_violations: int = 0
    high_violations: int = 0
    medium_violations: int = 0
    low_violations: int = 0

    # Recommendations
    remediation_recommendations: builtins.list[str] = field(default_factory=list)
    next_assessment_date: datetime = field(
        default_factory=lambda: datetime.now() + timedelta(days=30)
    )

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "generated_at": self.generated_at.isoformat(),
            "next_assessment_date": self.next_assessment_date.isoformat(),
            "framework": self.framework.value,
            "overall_status": self.overall_status.value,
            "violations": [v.to_dict() for v in self.violations],
        }


class ComplianceRuleEngine:
    """
    Compliance rule engine for automated policy enforcement

    Features:
    - Dynamic rule evaluation
    - Framework-specific rule sets
    - Real-time compliance monitoring
    - Automated violation detection
    """

    def __init__(self):
        self.rules: builtins.dict[str, ComplianceRule] = {}
        self.violations: builtins.dict[str, ComplianceViolation] = {}

        # Initialize framework-specific rules
        self._initialize_compliance_rules()

        # Metrics
        if ASYNC_AVAILABLE:
            self.rule_evaluations = Counter(
                "marty_compliance_rule_evaluations_total",
                "Compliance rule evaluations",
                ["framework", "rule_id", "result"],
            )
            self.compliance_violations = Counter(
                "marty_compliance_violations_total",
                "Compliance violations detected",
                ["framework", "severity"],
            )

    def _initialize_compliance_rules(self):
        """Initialize compliance rules for different frameworks"""

        # GDPR Rules
        self.add_rule(
            ComplianceRule(
                rule_id="gdpr_data_encryption",
                name="Personal Data Encryption",
                description="All personal data must be encrypted at rest and in transit",
                framework=ComplianceFramework.GDPR,
                category="data_protection",
                severity=RiskLevel.HIGH,
                control_id="GDPR.32",
                conditions={
                    "data_classification": "personal",
                    "encryption_required": True,
                    "encryption_algorithm": ["AES-256", "RSA-2048"],
                },
                remediation_steps=[
                    "Enable encryption for personal data storage",
                    "Implement TLS 1.3 for data in transit",
                    "Review and update encryption policies",
                ],
            )
        )

        self.add_rule(
            ComplianceRule(
                rule_id="gdpr_data_retention",
                name="Data Retention Limits",
                description="Personal data retention must not exceed business necessity",
                framework=ComplianceFramework.GDPR,
                category="data_retention",
                severity=RiskLevel.MEDIUM,
                control_id="GDPR.5",
                conditions={
                    "data_classification": "personal",
                    "retention_period_defined": True,
                    "automatic_deletion": True,
                },
                remediation_steps=[
                    "Define data retention policies",
                    "Implement automatic data deletion",
                    "Regular review of stored personal data",
                ],
            )
        )

        self.add_rule(
            ComplianceRule(
                rule_id="gdpr_consent_management",
                name="Consent Management",
                description="Valid consent must be obtained for personal data processing",
                framework=ComplianceFramework.GDPR,
                category="consent",
                severity=RiskLevel.HIGH,
                control_id="GDPR.7",
                conditions={
                    "consent_required": True,
                    "consent_documented": True,
                    "consent_withdrawable": True,
                },
                remediation_steps=[
                    "Implement consent management system",
                    "Document all consent records",
                    "Provide consent withdrawal mechanisms",
                ],
            )
        )

        # HIPAA Rules
        self.add_rule(
            ComplianceRule(
                rule_id="hipaa_access_controls",
                name="Access Control Requirements",
                description="PHI access must be restricted to authorized personnel only",
                framework=ComplianceFramework.HIPAA,
                category="access_control",
                severity=RiskLevel.CRITICAL,
                control_id="HIPAA.164.312(a)(1)",
                conditions={
                    "phi_access": True,
                    "role_based_access": True,
                    "access_audit_logs": True,
                    "minimum_necessary": True,
                },
                remediation_steps=[
                    "Implement role-based access controls",
                    "Enable comprehensive access logging",
                    "Regular access reviews and audits",
                    "Enforce minimum necessary principle",
                ],
            )
        )

        self.add_rule(
            ComplianceRule(
                rule_id="hipaa_audit_logs",
                name="Audit Log Requirements",
                description="All PHI access must be logged and monitored",
                framework=ComplianceFramework.HIPAA,
                category="audit_logging",
                severity=RiskLevel.HIGH,
                control_id="HIPAA.164.312(b)",
                conditions={
                    "phi_access_logged": True,
                    "log_retention_period": 6,  # years
                    "log_integrity_protection": True,
                    "regular_log_review": True,
                },
                remediation_steps=[
                    "Enable comprehensive audit logging",
                    "Implement log integrity protection",
                    "Establish log review procedures",
                    "Ensure 6-year log retention",
                ],
            )
        )

        # SOX Rules
        self.add_rule(
            ComplianceRule(
                rule_id="sox_change_management",
                name="Change Management Controls",
                description="All system changes must be documented and approved",
                framework=ComplianceFramework.SOX,
                category="change_management",
                severity=RiskLevel.HIGH,
                control_id="SOX.404",
                conditions={
                    "change_approval_required": True,
                    "change_documentation": True,
                    "segregation_of_duties": True,
                    "change_testing": True,
                },
                remediation_steps=[
                    "Implement change approval workflow",
                    "Document all system changes",
                    "Enforce segregation of duties",
                    "Require testing before deployment",
                ],
            )
        )

        self.add_rule(
            ComplianceRule(
                rule_id="sox_financial_controls",
                name="Financial System Controls",
                description="Financial systems must have appropriate access controls",
                framework=ComplianceFramework.SOX,
                category="financial_controls",
                severity=RiskLevel.CRITICAL,
                control_id="SOX.302",
                conditions={
                    "financial_system": True,
                    "privileged_access_controls": True,
                    "regular_access_reviews": True,
                    "audit_trail": True,
                },
                remediation_steps=[
                    "Implement privileged access management",
                    "Conduct regular access reviews",
                    "Maintain comprehensive audit trails",
                    "Establish financial system monitoring",
                ],
            )
        )

        # PCI DSS Rules
        self.add_rule(
            ComplianceRule(
                rule_id="pci_cardholder_data_protection",
                name="Cardholder Data Protection",
                description="Cardholder data must be protected with strong encryption",
                framework=ComplianceFramework.PCI_DSS,
                category="data_protection",
                severity=RiskLevel.CRITICAL,
                control_id="PCI.3",
                conditions={
                    "cardholder_data": True,
                    "encryption_at_rest": True,
                    "encryption_in_transit": True,
                    "key_management": True,
                },
                remediation_steps=[
                    "Implement strong encryption for cardholder data",
                    "Establish secure key management",
                    "Regular encryption validation",
                    "Minimize cardholder data storage",
                ],
            )
        )

        self.add_rule(
            ComplianceRule(
                rule_id="pci_network_security",
                name="Network Security Controls",
                description="Payment networks must be properly segmented and protected",
                framework=ComplianceFramework.PCI_DSS,
                category="network_security",
                severity=RiskLevel.HIGH,
                control_id="PCI.1",
                conditions={
                    "network_segmentation": True,
                    "firewall_configured": True,
                    "default_passwords_changed": True,
                    "wireless_security": True,
                },
                remediation_steps=[
                    "Implement network segmentation",
                    "Configure and maintain firewalls",
                    "Change all default passwords",
                    "Secure wireless networks",
                ],
            )
        )

    def add_rule(self, rule: ComplianceRule):
        """Add compliance rule"""
        self.rules[rule.rule_id] = rule
        print(f"Added compliance rule: {rule.name} ({rule.framework.value})")

    async def evaluate_rule(
        self, rule_id: str, context: builtins.dict[str, Any]
    ) -> builtins.tuple[bool, ComplianceViolation | None]:
        """Evaluate single compliance rule"""

        if rule_id not in self.rules:
            return False, None

        rule = self.rules[rule_id]

        if not rule.is_active:
            return True, None

        # Evaluate rule conditions
        is_compliant = await self._evaluate_conditions(rule.conditions, context)

        # Update metrics
        if ASYNC_AVAILABLE:
            result = "compliant" if is_compliant else "non_compliant"
            self.rule_evaluations.labels(
                framework=rule.framework.value, rule_id=rule_id, result=result
            ).inc()

        if not is_compliant:
            # Create violation
            violation = ComplianceViolation(
                violation_id=str(uuid.uuid4()),
                rule_id=rule_id,
                framework=rule.framework,
                severity=rule.severity,
                description=f"Violation of {rule.name}: {rule.description}",
                detected_at=datetime.now(),
                source_system=context.get("source_system", "unknown"),
                affected_resources=context.get("affected_resources", []),
                evidence=context,
                impact_assessment=self._assess_impact(rule, context),
                remediation_actions=rule.remediation_steps,
            )

            self.violations[violation.violation_id] = violation

            # Update metrics
            if ASYNC_AVAILABLE:
                self.compliance_violations.labels(
                    framework=rule.framework.value, severity=rule.severity.value
                ).inc()

            return False, violation

        return True, None

    async def _evaluate_conditions(
        self, conditions: builtins.dict[str, Any], context: builtins.dict[str, Any]
    ) -> bool:
        """Evaluate rule conditions against context"""

        for condition_key, expected_value in conditions.items():
            context_value = context.get(condition_key)

            # Handle different condition types
            if isinstance(expected_value, bool):
                if context_value != expected_value:
                    return False

            elif isinstance(expected_value, list):
                if context_value not in expected_value:
                    return False

            elif isinstance(expected_value, dict):
                # Complex condition evaluation
                if not await self._evaluate_complex_condition(expected_value, context_value):
                    return False

            elif isinstance(expected_value, int | float):
                # Numeric comparison
                if not self._evaluate_numeric_condition(expected_value, context_value):
                    return False

            # String or exact match
            elif context_value != expected_value:
                return False

        return True

    async def _evaluate_complex_condition(
        self, condition: builtins.dict[str, Any], value: Any
    ) -> bool:
        """Evaluate complex conditions with operators"""

        operator = condition.get("operator", "equals")
        expected = condition.get("value")

        if operator == "equals":
            return value == expected
        if operator == "not_equals":
            return value != expected
        if operator == "in":
            return value in expected
        if operator == "not_in":
            return value not in expected
        if operator == "contains":
            return expected in str(value)
        if operator == "regex":
            return bool(re.search(expected, str(value)))
        if operator == "greater_than":
            return float(value) > float(expected)
        if operator == "less_than":
            return float(value) < float(expected)
        if operator == "exists":
            return value is not None

        return False

    def _evaluate_numeric_condition(self, expected: float, actual: Any) -> bool:
        """Evaluate numeric conditions"""
        try:
            return float(actual) >= expected
        except (ValueError, TypeError):
            return False

    def _assess_impact(self, rule: ComplianceRule, context: builtins.dict[str, Any]) -> str:
        """Assess impact of compliance violation"""

        impact_factors = []

        # Data sensitivity
        if context.get("data_classification") in [
            "personal",
            "sensitive",
            "confidential",
        ]:
            impact_factors.append("Sensitive data involved")

        # System criticality
        if context.get("system_criticality") in ["critical", "high"]:
            impact_factors.append("Critical system affected")

        # User count
        user_count = context.get("affected_users", 0)
        if user_count > 1000:
            impact_factors.append(f"Large user base affected ({user_count} users)")

        # Financial impact
        if rule.framework in [ComplianceFramework.SOX, ComplianceFramework.PCI_DSS]:
            impact_factors.append("Potential financial/regulatory penalties")

        # Reputation impact
        if rule.framework == ComplianceFramework.GDPR and rule.severity in [
            RiskLevel.HIGH,
            RiskLevel.CRITICAL,
        ]:
            impact_factors.append("Potential reputation damage and GDPR fines")

        return "; ".join(impact_factors) if impact_factors else "Standard compliance violation"

    async def evaluate_all_rules(
        self, framework: ComplianceFramework, context: builtins.dict[str, Any]
    ) -> builtins.list[ComplianceViolation]:
        """Evaluate all rules for a specific framework"""

        violations = []
        framework_rules = [rule for rule in self.rules.values() if rule.framework == framework]

        for rule in framework_rules:
            is_compliant, violation = await self.evaluate_rule(rule.rule_id, context)
            if not is_compliant and violation:
                violations.append(violation)

        return violations

    def get_rules_by_framework(
        self, framework: ComplianceFramework
    ) -> builtins.list[ComplianceRule]:
        """Get all rules for specific framework"""
        return [rule for rule in self.rules.values() if rule.framework == framework]

    def get_violation_summary(self) -> builtins.dict[str, Any]:
        """Get summary of all violations"""
        if not self.violations:
            return {"total": 0, "by_severity": {}, "by_framework": {}}

        by_severity = defaultdict(int)
        by_framework = defaultdict(int)

        for violation in self.violations.values():
            by_severity[violation.severity.value] += 1
            by_framework[violation.framework.value] += 1

        return {
            "total": len(self.violations),
            "by_severity": dict(by_severity),
            "by_framework": dict(by_framework),
        }


class AuditTrailManager:
    """
    Comprehensive audit trail management

    Features:
    - Tamper-evident audit logging
    - Long-term retention and archival
    - Compliance-aware event classification
    - Advanced search and reporting
    """

    def __init__(self, retention_years: int = 7):
        self.retention_years = retention_years
        self.audit_events: deque = deque(maxlen=1000000)  # In-memory for demo
        self.archived_events: builtins.dict[str, builtins.list[AuditEvent]] = {}

        # Event classification
        self.sensitive_actions = {
            "user_create",
            "user_delete",
            "role_assign",
            "permission_grant",
            "data_export",
            "configuration_change",
            "security_policy_change",
        }

        # Compliance framework mapping
        self.framework_event_mapping = {
            ComplianceFramework.GDPR: {
                AuditEventType.DATA_ACCESS,
                AuditEventType.USER_ACCESS,
                AuditEventType.ADMIN_ACTION,
            },
            ComplianceFramework.HIPAA: {
                AuditEventType.DATA_ACCESS,
                AuditEventType.USER_ACCESS,
                AuditEventType.SYSTEM_CHANGE,
            },
            ComplianceFramework.SOX: {
                AuditEventType.CONFIGURATION_CHANGE,
                AuditEventType.ADMIN_ACTION,
                AuditEventType.SYSTEM_CHANGE,
            },
            ComplianceFramework.PCI_DSS: {
                AuditEventType.DATA_ACCESS,
                AuditEventType.SECURITY_EVENT,
                AuditEventType.SYSTEM_CHANGE,
            },
        }

        # Metrics
        if ASYNC_AVAILABLE:
            self.audit_events_logged = Counter(
                "marty_audit_events_total",
                "Audit events logged",
                ["event_type", "outcome"],
            )
            self.sensitive_events = Counter(
                "marty_sensitive_audit_events_total",
                "Sensitive audit events",
                ["event_type"],
            )

    async def log_event(
        self,
        event_type: AuditEventType,
        user_id: str | None,
        action: str,
        resource: str,
        source_ip: str = "",
        user_agent: str = "",
        session_id: str | None = None,
        resource_id: str | None = None,
        details: builtins.dict[str, Any] | None = None,
        outcome: str = "success",
    ) -> AuditEvent:
        """Log audit event"""

        event = AuditEvent(
            event_id=str(uuid.uuid4()),
            event_type=event_type,
            timestamp=datetime.now(),
            user_id=user_id,
            session_id=session_id,
            source_ip=source_ip,
            user_agent=user_agent,
            action=action,
            resource=resource,
            resource_id=resource_id,
            details=details or {},
            outcome=outcome,
        )

        # Determine compliance relevance
        event.compliance_frameworks = self._determine_compliance_frameworks(event)

        # Check for sensitive data involvement
        event.sensitive_data_involved = self._is_sensitive_action(
            action
        ) or self._contains_sensitive_data(details or {})

        # Store event
        self.audit_events.append(event)

        # Update metrics
        if ASYNC_AVAILABLE:
            self.audit_events_logged.labels(event_type=event_type.value, outcome=outcome).inc()

            if event.sensitive_data_involved:
                self.sensitive_events.labels(event_type=event_type.value).inc()

        print(f"Logged audit event: {action} by {user_id or 'system'}")
        return event

    def _determine_compliance_frameworks(
        self, event: AuditEvent
    ) -> builtins.set[ComplianceFramework]:
        """Determine which compliance frameworks apply to event"""
        applicable_frameworks = set()

        for framework, event_types in self.framework_event_mapping.items():
            if event.event_type in event_types:
                applicable_frameworks.add(framework)

        # Additional logic based on event details
        if event.sensitive_data_involved:
            applicable_frameworks.add(ComplianceFramework.GDPR)

        if "payment" in event.resource.lower() or "card" in event.action.lower():
            applicable_frameworks.add(ComplianceFramework.PCI_DSS)

        if "financial" in event.resource.lower():
            applicable_frameworks.add(ComplianceFramework.SOX)

        if "health" in event.resource.lower() or "medical" in event.resource.lower():
            applicable_frameworks.add(ComplianceFramework.HIPAA)

        return applicable_frameworks

    def _is_sensitive_action(self, action: str) -> bool:
        """Check if action is considered sensitive"""
        return action.lower() in self.sensitive_actions

    def _contains_sensitive_data(self, details: builtins.dict[str, Any]) -> bool:
        """Check if event details contain sensitive data"""
        sensitive_patterns = [
            r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b",  # Credit card
            r"\b\d{3}-\d{2}-\d{4}\b",  # SSN
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",  # Email
            r"\b\d{10,15}\b",  # Phone number
        ]

        details_str = json.dumps(details)
        for pattern in sensitive_patterns:
            if re.search(pattern, details_str):
                return True

        # Check for explicit sensitive data markers
        sensitive_keys = ["ssn", "credit_card", "password", "personal_data", "phi"]
        for key in sensitive_keys:
            if key in details_str.lower():
                return True

        return False

    async def search_events(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        user_id: str | None = None,
        event_type: AuditEventType | None = None,
        action: str | None = None,
        resource: str | None = None,
        compliance_framework: ComplianceFramework | None = None,
        sensitive_only: bool = False,
        limit: int = 1000,
    ) -> builtins.list[AuditEvent]:
        """Search audit events with filters"""

        results = []

        for event in self.audit_events:
            # Apply filters
            if start_date and event.timestamp < start_date:
                continue
            if end_date and event.timestamp > end_date:
                continue
            if user_id and event.user_id != user_id:
                continue
            if event_type and event.event_type != event_type:
                continue
            if action and action.lower() not in event.action.lower():
                continue
            if resource and resource.lower() not in event.resource.lower():
                continue
            if compliance_framework and compliance_framework not in event.compliance_frameworks:
                continue
            if sensitive_only and not event.sensitive_data_involved:
                continue

            results.append(event)

            if len(results) >= limit:
                break

        return results

    def get_compliance_audit_trail(
        self, framework: ComplianceFramework, days: int = 30
    ) -> builtins.list[AuditEvent]:
        """Get audit trail for specific compliance framework"""

        cutoff_date = datetime.now() - timedelta(days=days)

        return [
            event
            for event in self.audit_events
            if (event.timestamp >= cutoff_date and framework in event.compliance_frameworks)
        ]

    def get_audit_statistics(self) -> builtins.dict[str, Any]:
        """Get audit trail statistics"""

        if not self.audit_events:
            return {"total_events": 0}

        total_events = len(self.audit_events)
        sensitive_events = sum(1 for event in self.audit_events if event.sensitive_data_involved)

        by_type = defaultdict(int)
        by_outcome = defaultdict(int)
        by_framework = defaultdict(int)

        for event in self.audit_events:
            by_type[event.event_type.value] += 1
            by_outcome[event.outcome] += 1
            for framework in event.compliance_frameworks:
                by_framework[framework.value] += 1

        return {
            "total_events": total_events,
            "sensitive_events": sensitive_events,
            "events_by_type": dict(by_type),
            "events_by_outcome": dict(by_outcome),
            "events_by_framework": dict(by_framework),
            "retention_period_years": self.retention_years,
        }


class ComplianceReportGenerator:
    """
    Automated compliance reporting

    Features:
    - Framework-specific reports
    - Executive summaries
    - Detailed violation analysis
    - Remediation tracking
    """

    def __init__(self, rule_engine: ComplianceRuleEngine, audit_manager: AuditTrailManager):
        self.rule_engine = rule_engine
        self.audit_manager = audit_manager

    async def generate_compliance_report(
        self,
        framework: ComplianceFramework,
        assessment_context: builtins.dict[str, Any],
    ) -> ComplianceReport:
        """Generate comprehensive compliance report"""

        # Get framework rules
        framework_rules = self.rule_engine.get_rules_by_framework(framework)

        # Evaluate all rules
        violations = await self.rule_engine.evaluate_all_rules(framework, assessment_context)

        # Calculate compliance metrics
        total_rules = len(framework_rules)
        non_compliant_rules = len(violations)
        compliant_rules = total_rules - non_compliant_rules

        # Calculate compliance score
        compliance_score = compliant_rules / total_rules if total_rules > 0 else 0.0

        # Determine overall status
        if compliance_score >= 0.95:
            overall_status = ComplianceStatus.COMPLIANT
        elif compliance_score >= 0.80:
            overall_status = ComplianceStatus.PARTIALLY_COMPLIANT
        else:
            overall_status = ComplianceStatus.NON_COMPLIANT

        # Count violations by severity
        violation_counts = {
            RiskLevel.CRITICAL: 0,
            RiskLevel.HIGH: 0,
            RiskLevel.MEDIUM: 0,
            RiskLevel.LOW: 0,
        }

        for violation in violations:
            violation_counts[violation.severity] += 1

        # Generate remediation recommendations
        recommendations = self._generate_remediation_recommendations(violations)

        report = ComplianceReport(
            report_id=str(uuid.uuid4()),
            framework=framework,
            generated_at=datetime.now(),
            overall_status=overall_status,
            compliance_score=compliance_score,
            total_rules=total_rules,
            compliant_rules=compliant_rules,
            non_compliant_rules=non_compliant_rules,
            not_assessed_rules=0,  # All rules assessed
            violations=violations,
            critical_violations=violation_counts[RiskLevel.CRITICAL],
            high_violations=violation_counts[RiskLevel.HIGH],
            medium_violations=violation_counts[RiskLevel.MEDIUM],
            low_violations=violation_counts[RiskLevel.LOW],
            remediation_recommendations=recommendations,
        )

        print(f"Generated {framework.value} compliance report: {compliance_score:.1%} compliant")
        return report

    def _generate_remediation_recommendations(
        self, violations: builtins.list[ComplianceViolation]
    ) -> builtins.list[str]:
        """Generate prioritized remediation recommendations"""

        recommendations = []

        # Prioritize by severity
        critical_violations = [v for v in violations if v.severity == RiskLevel.CRITICAL]
        high_violations = [v for v in violations if v.severity == RiskLevel.HIGH]

        if critical_violations:
            recommendations.append(
                f"URGENT: Address {len(critical_violations)} critical violations immediately"
            )

            # Add specific recommendations for critical violations
            for violation in critical_violations[:3]:  # Top 3
                recommendations.extend(violation.remediation_actions[:2])  # Top 2 actions

        if high_violations:
            recommendations.append(
                f"HIGH PRIORITY: Address {len(high_violations)} high-severity violations within 30 days"
            )

        # General recommendations
        violation_categories = defaultdict(int)
        for violation in violations:
            # Extract category from rule
            rule = self.rule_engine.rules.get(violation.rule_id)
            if rule:
                violation_categories[rule.category] += 1

        # Recommend systemic improvements for common violation categories
        for category, count in violation_categories.items():
            if count >= 3:
                recommendations.append(
                    f"Consider systemic improvements in {category.replace('_', ' ')} "
                    f"({count} related violations)"
                )

        # Add monitoring recommendations
        recommendations.extend(
            [
                "Implement continuous compliance monitoring",
                "Schedule quarterly compliance assessments",
                "Establish compliance training programs",
                "Review and update compliance policies annually",
            ]
        )

        return recommendations[:10]  # Limit to top 10 recommendations

    async def generate_executive_summary(
        self, reports: builtins.list[ComplianceReport]
    ) -> builtins.dict[str, Any]:
        """Generate executive summary across multiple frameworks"""

        if not reports:
            return {"message": "No compliance reports available"}

        total_violations = sum(len(report.violations) for report in reports)
        avg_compliance_score = sum(report.compliance_score for report in reports) / len(reports)

        # Risk assessment
        risk_level = RiskLevel.LOW
        if any(report.critical_violations > 0 for report in reports):
            risk_level = RiskLevel.CRITICAL
        elif any(report.high_violations > 5 for report in reports):
            risk_level = RiskLevel.HIGH
        elif any(report.overall_status == ComplianceStatus.NON_COMPLIANT for report in reports):
            risk_level = RiskLevel.MEDIUM

        # Framework status
        framework_status = {}
        for report in reports:
            framework_status[report.framework.value] = {
                "status": report.overall_status.value,
                "score": report.compliance_score,
                "violations": len(report.violations),
            }

        # Top recommendations across all frameworks
        all_recommendations = []
        for report in reports:
            all_recommendations.extend(report.remediation_recommendations)

        # Count and prioritize recommendations
        recommendation_counts = defaultdict(int)
        for rec in all_recommendations:
            recommendation_counts[rec] += 1

        top_recommendations = sorted(
            recommendation_counts.items(), key=lambda x: x[1], reverse=True
        )[:5]

        return {
            "assessment_date": datetime.now().isoformat(),
            "frameworks_assessed": len(reports),
            "overall_compliance_score": avg_compliance_score,
            "overall_risk_level": risk_level.value,
            "total_violations": total_violations,
            "framework_status": framework_status,
            "top_recommendations": [rec[0] for rec in top_recommendations],
            "next_assessment_recommended": (datetime.now() + timedelta(days=90)).isoformat(),
        }


class ComplianceManager:
    """
    Complete compliance automation and management system

    Orchestrates all compliance components:
    - Rule engine and policy enforcement
    - Audit trail management
    - Compliance reporting
    - Violation tracking and remediation
    """

    def __init__(self):
        self.rule_engine = ComplianceRuleEngine()
        self.audit_manager = AuditTrailManager()
        self.report_generator = ComplianceReportGenerator(self.rule_engine, self.audit_manager)

        # Automated monitoring
        self.monitoring_enabled = True
        self.monitoring_interval = timedelta(hours=1)
        self.last_assessment = {}

        # Real-time violation tracking
        self.active_violations: builtins.dict[str, ComplianceViolation] = {}

    async def assess_compliance(
        self, framework: ComplianceFramework, system_context: builtins.dict[str, Any]
    ) -> ComplianceReport:
        """Perform comprehensive compliance assessment"""

        print(f"Starting {framework.value} compliance assessment...")

        # Log assessment start
        await self.audit_manager.log_event(
            event_type=AuditEventType.ADMIN_ACTION,
            user_id="system",
            action="compliance_assessment_start",
            resource=f"compliance_{framework.value}",
            details={"framework": framework.value, "context": system_context},
        )

        # Generate report
        report = await self.report_generator.generate_compliance_report(framework, system_context)

        # Track violations
        for violation in report.violations:
            self.active_violations[violation.violation_id] = violation

        # Update last assessment
        self.last_assessment[framework] = datetime.now()

        # Log assessment completion
        await self.audit_manager.log_event(
            event_type=AuditEventType.ADMIN_ACTION,
            user_id="system",
            action="compliance_assessment_complete",
            resource=f"compliance_{framework.value}",
            details={
                "report_id": report.report_id,
                "compliance_score": report.compliance_score,
                "violations": len(report.violations),
            },
        )

        return report

    async def start_continuous_monitoring(self):
        """Start continuous compliance monitoring"""

        print("Starting continuous compliance monitoring...")

        while self.monitoring_enabled:
            try:
                # Monitor each framework
                for framework in ComplianceFramework:
                    # Check if assessment is due
                    last_check = self.last_assessment.get(framework)
                    if not last_check or datetime.now() - last_check > self.monitoring_interval:
                        # Simulate system context (in real implementation, this would
                        # collect actual system state)
                        context = await self._collect_system_context()

                        # Perform assessment
                        await self.assess_compliance(framework, context)

                # Wait before next monitoring cycle
                await asyncio.sleep(300)  # 5 minutes

            except Exception as e:
                print(f"Error in compliance monitoring: {e}")
                await asyncio.sleep(60)  # Wait 1 minute before retry

    async def _collect_system_context(self) -> builtins.dict[str, Any]:
        """Collect current system context for compliance evaluation"""

        # In a real implementation, this would collect actual system state
        # from various sources (databases, configs, etc.)

        return {
            "data_classification": "personal",
            "encryption_at_rest": True,
            "encryption_in_transit": True,
            "encryption_algorithm": "AES-256",
            "role_based_access": True,
            "access_audit_logs": True,
            "minimum_necessary": True,
            "phi_access_logged": True,
            "log_retention_period": 7,
            "log_integrity_protection": True,
            "regular_log_review": True,
            "change_approval_required": True,
            "change_documentation": True,
            "segregation_of_duties": True,
            "change_testing": True,
            "financial_system": False,
            "privileged_access_controls": True,
            "regular_access_reviews": True,
            "audit_trail": True,
            "cardholder_data": False,
            "network_segmentation": True,
            "firewall_configured": True,
            "default_passwords_changed": True,
            "wireless_security": True,
            "consent_required": True,
            "consent_documented": True,
            "consent_withdrawable": True,
            "retention_period_defined": True,
            "automatic_deletion": True,
            "system_criticality": "high",
            "affected_users": 5000,
            "source_system": "marty_framework",
        }

    async def remediate_violation(
        self, violation_id: str, remediation_notes: str, remediated_by: str
    ) -> bool:
        """Mark violation as remediated"""

        if violation_id not in self.active_violations:
            return False

        violation = self.active_violations[violation_id]
        violation.status = ComplianceStatus.COMPLIANT
        violation.remediated_at = datetime.now()
        violation.assigned_to = remediated_by

        # Log remediation
        await self.audit_manager.log_event(
            event_type=AuditEventType.COMPLIANCE_VIOLATION,
            user_id=remediated_by,
            action="violation_remediated",
            resource=f"compliance_violation_{violation_id}",
            details={
                "violation_id": violation_id,
                "rule_id": violation.rule_id,
                "framework": violation.framework.value,
                "notes": remediation_notes,
            },
        )

        # Remove from active violations
        del self.active_violations[violation_id]

        print(f"Remediated violation {violation_id}")
        return True

    def get_compliance_dashboard(self) -> builtins.dict[str, Any]:
        """Get compliance dashboard data"""

        # Framework status
        framework_status = {}
        for framework in ComplianceFramework:
            framework_rules = self.rule_engine.get_rules_by_framework(framework)
            framework_violations = [
                v for v in self.active_violations.values() if v.framework == framework
            ]

            framework_status[framework.value] = {
                "total_rules": len(framework_rules),
                "active_violations": len(framework_violations),
                "last_assessment": self.last_assessment.get(framework, {}).isoformat()
                if self.last_assessment.get(framework)
                else None,
            }

        # Violation summary
        violation_summary = self.rule_engine.get_violation_summary()

        # Audit statistics
        audit_stats = self.audit_manager.get_audit_statistics()

        return {
            "frameworks": framework_status,
            "violations": violation_summary,
            "audit_trail": audit_stats,
            "monitoring_enabled": self.monitoring_enabled,
            "total_active_violations": len(self.active_violations),
        }


# Example usage
async def main():
    """Example usage of compliance automation system"""

    # Initialize compliance manager
    compliance_manager = ComplianceManager()

    print("=== Compliance Automation Demo ===")

    # Perform compliance assessments
    frameworks_to_assess = [
        ComplianceFramework.GDPR,
        ComplianceFramework.HIPAA,
        ComplianceFramework.SOX,
        ComplianceFramework.PCI_DSS,
    ]

    reports = []
    for framework in frameworks_to_assess:
        # Simulate system context
        context = await compliance_manager._collect_system_context()

        # Perform assessment
        report = await compliance_manager.assess_compliance(framework, context)
        reports.append(report)

        print(
            f"{framework.value}: {report.compliance_score:.1%} compliant, "
            f"{len(report.violations)} violations"
        )

    # Generate executive summary
    executive_summary = await compliance_manager.report_generator.generate_executive_summary(
        reports
    )
    print("\nExecutive Summary:")
    print(f"Overall Compliance Score: {executive_summary['overall_compliance_score']:.1%}")
    print(f"Overall Risk Level: {executive_summary['overall_risk_level']}")
    print(f"Total Violations: {executive_summary['total_violations']}")

    # Show compliance dashboard
    dashboard = compliance_manager.get_compliance_dashboard()
    print("\nCompliance Dashboard:")
    print(f"Active Violations: {dashboard['total_active_violations']}")
    print(f"Audit Events: {dashboard['audit_trail']['total_events']}")

    # Simulate violation remediation
    if compliance_manager.active_violations:
        first_violation_id = list(compliance_manager.active_violations.keys())[0]
        await compliance_manager.remediate_violation(
            first_violation_id, "Implemented required security controls", "admin"
        )
        print(f"Remediated violation: {first_violation_id}")


if __name__ == "__main__":
    asyncio.run(main())
