import pytest

from mmf.core.domain.audit_types import (
    AuditEventType,
    AuditLevel,
    AuditOutcome,
    AuditSeverity,
    AuthenticationMethod,
    ComplianceFramework,
    SecurityEventSeverity,
    SecurityEventStatus,
    SecurityEventType,
    SecurityLevel,
    SecurityThreatLevel,
    ThreatCategory,
)


class TestAuditTypes:
    def test_compliance_framework_values(self):
        assert ComplianceFramework.GDPR.value == "gdpr"
        assert ComplianceFramework.HIPAA.value == "hipaa"
        assert ComplianceFramework.SOX.value == "sox"
        assert ComplianceFramework.PCI_DSS.value == "pci_dss"
        assert ComplianceFramework.ISO27001.value == "iso27001"
        assert ComplianceFramework.NIST.value == "nist"

    def test_security_event_type_values(self):
        assert SecurityEventType.AUTHENTICATION_SUCCESS.value == "authentication_success"
        assert SecurityEventType.AUTHENTICATION_FAILURE.value == "authentication_failure"
        assert SecurityEventType.AUTHORIZATION_GRANTED.value == "authorization_granted"
        assert SecurityEventType.AUTHORIZATION_DENIED.value == "authorization_denied"
        assert SecurityEventType.TOKEN_ISSUED.value == "token_issued"
        assert SecurityEventType.PERMISSION_CHECK.value == "permission_check"
        assert SecurityEventType.POLICY_EVALUATION.value == "policy_evaluation"
        assert SecurityEventType.DATA_ACCESS.value == "data_access"
        assert SecurityEventType.ADMIN_ACTION.value == "admin_action"
        assert SecurityEventType.RATE_LIMIT_HIT.value == "rate_limit_hit"
        assert SecurityEventType.COMPLIANCE_VIOLATION.value == "compliance_violation"
        assert SecurityEventType.NETWORK_ANOMALY.value == "network_anomaly"

    def test_security_event_severity_values(self):
        assert SecurityEventSeverity.INFO.value == "info"
        assert SecurityEventSeverity.LOW.value == "low"
        assert SecurityEventSeverity.MEDIUM.value == "medium"
        assert SecurityEventSeverity.HIGH.value == "high"
        assert SecurityEventSeverity.CRITICAL.value == "critical"

    def test_security_event_status_values(self):
        assert SecurityEventStatus.NEW.value == "new"
        assert SecurityEventStatus.INVESTIGATING.value == "investigating"
        assert SecurityEventStatus.CONFIRMED.value == "confirmed"
        assert SecurityEventStatus.FALSE_POSITIVE.value == "false_positive"
        assert SecurityEventStatus.RESOLVED.value == "resolved"

    def test_audit_level_values(self):
        assert AuditLevel.DEBUG.value == "debug"
        assert AuditLevel.INFO.value == "info"
        assert AuditLevel.WARNING.value == "warning"
        assert AuditLevel.ERROR.value == "error"
        assert AuditLevel.CRITICAL.value == "critical"

    def test_security_threat_level_values(self):
        assert SecurityThreatLevel.LOW.value == "low"
        assert SecurityThreatLevel.MEDIUM.value == "medium"
        assert SecurityThreatLevel.HIGH.value == "high"
        assert SecurityThreatLevel.CRITICAL.value == "critical"

    def test_security_level_values(self):
        assert SecurityLevel.PUBLIC.value == "public"
        assert SecurityLevel.INTERNAL.value == "internal"
        assert SecurityLevel.CONFIDENTIAL.value == "confidential"
        assert SecurityLevel.RESTRICTED.value == "restricted"
        assert SecurityLevel.TOP_SECRET.value == "top_secret"

    def test_authentication_method_values(self):
        assert AuthenticationMethod.PASSWORD.value == "password"
        assert AuthenticationMethod.API_KEY.value == "api_key"
        assert AuthenticationMethod.JWT_TOKEN.value == "jwt_token"
        assert AuthenticationMethod.OAUTH2.value == "oauth2"
        assert AuthenticationMethod.CERTIFICATE.value == "certificate"
        assert AuthenticationMethod.MULTI_FACTOR.value == "multi_factor"

    def test_audit_event_type_values(self):
        assert AuditEventType.AUTH_LOGIN_SUCCESS.value == "auth_login_success"
        assert AuditEventType.API_REQUEST.value == "api_request"
        assert AuditEventType.DATA_CREATE.value == "data_create"
        assert AuditEventType.DB_CONNECTION.value == "db_connection"
        assert AuditEventType.SECURITY_INTRUSION_ATTEMPT.value == "security_intrusion_attempt"
        assert AuditEventType.SYSTEM_STARTUP.value == "system_startup"
        assert AuditEventType.ADMIN_USER_CREATED.value == "admin_user_created"
        assert AuditEventType.COMPLIANCE_DATA_ACCESS.value == "compliance_data_access"
        assert AuditEventType.MIDDLEWARE_REQUEST_START.value == "middleware_request_start"

    def test_audit_severity_values(self):
        assert AuditSeverity.INFO.value == "info"
        assert AuditSeverity.LOW.value == "low"
        assert AuditSeverity.MEDIUM.value == "medium"
        assert AuditSeverity.HIGH.value == "high"
        assert AuditSeverity.CRITICAL.value == "critical"

    def test_audit_outcome_values(self):
        assert AuditOutcome.SUCCESS.value == "success"
        assert AuditOutcome.FAILURE.value == "failure"
        assert AuditOutcome.ERROR.value == "error"
        assert AuditOutcome.PARTIAL.value == "partial"
        assert AuditOutcome.UNKNOWN.value == "unknown"

    def test_threat_category_values(self):
        assert ThreatCategory.AUTHENTICATION_ATTACK.value == "authentication_attack"
        assert ThreatCategory.AUTHORIZATION_BYPASS.value == "authorization_bypass"
        assert ThreatCategory.DATA_EXFILTRATION.value == "data_exfiltration"
        assert ThreatCategory.INJECTION_ATTACK.value == "injection_attack"
        assert ThreatCategory.DDoS_ATTACK.value == "ddos_attack"
        assert ThreatCategory.MALWARE.value == "malware"
        assert ThreatCategory.INSIDER_THREAT.value == "insider_threat"
        assert ThreatCategory.APT.value == "advanced_persistent_threat"
        assert ThreatCategory.BRUTE_FORCE.value == "brute_force"
        assert ThreatCategory.ANOMALOUS_BEHAVIOR.value == "anomalous_behavior"
        assert ThreatCategory.PRIVILEGE_ESCALATION.value == "privilege_escalation"
        assert ThreatCategory.LATERAL_MOVEMENT.value == "lateral_movement"
