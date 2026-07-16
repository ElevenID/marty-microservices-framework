import pytest

from mmf.core.domain import ComplianceFramework, SecurityEventType, AuditLevel, SecurityThreatLevel
from mmf.services.audit_compliance.domain.models.compliance_scan_result import (
    ComplianceScanResult,
    Finding,
)
from mmf.services.audit_compliance.domain.models.security_audit_event import (
    SecurityAuditEvent,
)
from mmf.services.audit_compliance.domain.models.threat_pattern import (
    ThreatIndicator,
    ThreatPattern,
)


# =============================================================================
# Finding
# =============================================================================


@pytest.mark.unit
class TestFinding:
    def test_finding_creation(self):
        f = Finding(
            rule_id="R001",
            rule_name="Encryption at rest",
            severity="high",
            status="fail",
            resource_id="db-1",
            resource_type="database",
            description="DB not encrypted",
            remediation="Enable encryption",
        )
        assert f.rule_id == "R001"
        assert f.severity == "high"
        assert f.status == "fail"
        assert f.evidence == {}

    def test_finding_defaults(self):
        f = Finding(rule_id="R002", rule_name="Test", severity="low", status="pass")
        assert f.resource_id is None
        assert f.description == ""
        assert f.evidence == {}


# =============================================================================
# ComplianceScanResult
# =============================================================================


@pytest.mark.unit
class TestComplianceScanResult:
    def test_scan_result_creation(self):
        result = ComplianceScanResult(
            framework=ComplianceFramework.ISO27001,
            scan_name="nightly-iso27001",
            target_resource="api-gateway",
            target_type="service",
            overall_status="compliant",
            score=95.0,
        )
        assert result.framework == ComplianceFramework.ISO27001
        assert result.score == 95.0
        assert result.overall_status == "compliant"
        assert result.findings == []

    def test_scan_result_with_findings(self):
        finding = Finding(
            rule_id="R001",
            rule_name="TLS check",
            severity="critical",
            status="fail",
        )
        result = ComplianceScanResult(
            framework=ComplianceFramework.ISO27001,
            scan_name="tls-check",
            target_resource="api-gateway",
            target_type="service",
            overall_status="non_compliant",
            score=40.0,
            findings=[finding],
            recommendations=["Enable TLS 1.3"],
        )
        assert len(result.findings) == 1
        assert result.findings[0].rule_id == "R001"
        assert result.recommendations == ["Enable TLS 1.3"]

    def test_scan_result_to_dict(self):
        result = ComplianceScanResult(
            framework=ComplianceFramework.ISO27001,
            scan_name="test",
            target_resource="svc",
            target_type="service",
            overall_status="compliant",
            score=100.0,
        )
        d = result.to_dict()
        assert "scan_name" in d or "id" in d  # Entity base provides id


# =============================================================================
# SecurityAuditEvent
# =============================================================================


@pytest.mark.unit
class TestSecurityAuditEvent:
    def test_event_creation(self):
        event = SecurityAuditEvent(
            event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
            principal_id="user-123",
            resource="/api/login",
            action="login",
            result="success",
        )
        assert event.event_type == SecurityEventType.AUTHENTICATION_SUCCESS
        assert event.principal_id == "user-123"
        assert event.result == "success"
        assert event.level == AuditLevel.INFO

    def test_event_defaults(self):
        event = SecurityAuditEvent(event_type=SecurityEventType.AUTHORIZATION_GRANTED)
        assert event.principal_id is None
        assert event.ip_address is None
        assert event.details == {}
        assert event.timestamp is not None

    def test_event_to_dict(self):
        event = SecurityAuditEvent(
            event_type=SecurityEventType.AUTHENTICATION_FAILURE,
            principal_id="user-1",
            action="login",
            result="failure",
            ip_address="10.0.0.1",
        )
        d = event.to_dict()
        assert d["principal_id"] == "user-1"
        assert d["result"] == "failure"


# =============================================================================
# ThreatPattern
# =============================================================================


@pytest.mark.unit
class TestThreatPattern:
    def test_pattern_creation(self):
        pattern = ThreatPattern(
            pattern_name="brute-force-login",
            pattern_type="brute_force",
            threat_level=SecurityThreatLevel.HIGH,
            confidence_threshold=0.8,
            time_window_minutes=15,
            minimum_events=5,
        )
        assert pattern.pattern_name == "brute-force-login"
        assert pattern.threat_level == SecurityThreatLevel.HIGH
        assert pattern.confidence_threshold == 0.8
        assert pattern.is_active is True
        assert pattern.trigger_count == 0

    def test_pattern_with_indicators(self):
        indicator = ThreatIndicator(
            indicator_type="ip",
            value="192.168.1.100",
            weight=0.9,
            description="suspicious IP",
        )
        pattern = ThreatPattern(
            pattern_name="anomalous-access",
            pattern_type="anomalous_access",
            threat_level=SecurityThreatLevel.MEDIUM,
            confidence_threshold=0.6,
            indicators=[indicator],
        )
        assert len(pattern.indicators) == 1
        assert pattern.indicators[0].weight == 0.9

    def test_threat_indicator_defaults(self):
        ind = ThreatIndicator(indicator_type="endpoint", value="/admin", weight=0.5)
        assert ind.description == ""

    def test_pattern_to_dict(self):
        pattern = ThreatPattern(
            pattern_name="test",
            pattern_type="brute_force",
            threat_level=SecurityThreatLevel.LOW,
            confidence_threshold=0.5,
        )
        d = pattern.to_dict()
        assert d["pattern_name"] == "test"
