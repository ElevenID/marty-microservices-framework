from datetime import datetime, timezone
from uuid import uuid4

import pytest

from mmf.core.domain.audit_models import (
    AuditEvent,
    ComplianceResult,
    SecurityEvent,
    SecurityPrincipal,
    ThreatIndicator,
)
from mmf.core.domain.audit_types import (
    ComplianceFramework,
    SecurityEventSeverity,
    SecurityEventStatus,
    SecurityEventType,
    SecurityThreatLevel,
)


class TestAuditEvent:
    def test_init_defaults(self):
        event = AuditEvent(
            event_id="1",
            event_type="test",
            timestamp=None,  # Should be set in post_init
        )
        assert event.timestamp is not None
        assert isinstance(event.timestamp, datetime)
        assert event.result == "unknown"
        assert event.details == {}

    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        event = AuditEvent(
            event_id="1",
            event_type="test",
            timestamp=now,
            result="success",
            details={"key": "value"},
        )
        data = event.to_dict()
        assert data["event_id"] == "1"
        assert data["event_type"] == "test"
        assert data["timestamp"] == now.isoformat()
        assert data["result"] == "success"
        assert data["details"] == {"key": "value"}


class TestSecurityEvent:
    def test_init_defaults(self):
        event = SecurityEvent(
            event_id="1",
            event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
            severity=SecurityEventSeverity.INFO,
            timestamp=None,
        )
        assert event.timestamp is not None
        assert event.status == SecurityEventStatus.NEW
        assert event.mitigation_applied is False

    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        event = SecurityEvent(
            event_id="1",
            event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
            severity=SecurityEventSeverity.INFO,
            timestamp=now,
            status=SecurityEventStatus.NEW,
        )
        data = event.to_dict()
        assert data["event_id"] == "1"
        assert data["event_type"] == SecurityEventType.AUTHENTICATION_SUCCESS.value
        assert data["severity"] == SecurityEventSeverity.INFO.value
        assert data["timestamp"] == now.isoformat()
        assert data["status"] == SecurityEventStatus.NEW.value

    def test_calculate_risk_score_info(self):
        event = SecurityEvent(
            event_id="1",
            event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
            severity=SecurityEventSeverity.INFO,
            timestamp=datetime.now(timezone.utc),
        )
        assert event.calculate_risk_score() == 1.0

    def test_calculate_risk_score_critical(self):
        event = SecurityEvent(
            event_id="1",
            event_type=SecurityEventType.AUTHENTICATION_FAILURE,
            severity=SecurityEventSeverity.CRITICAL,
            timestamp=datetime.now(timezone.utc),
        )
        assert event.calculate_risk_score() == 10.0

    def test_calculate_risk_score_high_risk_type(self):
        # PRIVILEGE_ESCALATION is high risk, base score for HIGH is 8.0
        # 8.0 * 1.5 = 12.0, capped at 10.0
        event = SecurityEvent(
            event_id="1",
            event_type=SecurityEventType.PRIVILEGE_ESCALATION,
            severity=SecurityEventSeverity.HIGH,
            timestamp=datetime.now(timezone.utc),
        )
        assert event.calculate_risk_score() == 10.0

        # MEDIUM (5.0) * 1.5 = 7.5
        event = SecurityEvent(
            event_id="1",
            event_type=SecurityEventType.PRIVILEGE_ESCALATION,
            severity=SecurityEventSeverity.MEDIUM,
            timestamp=datetime.now(timezone.utc),
        )
        assert event.calculate_risk_score() == 7.5


class TestComplianceResult:
    def test_init_defaults(self):
        result = ComplianceResult(framework=ComplianceFramework.GDPR, passed=True, score=100.0)
        assert result.timestamp is not None
        assert result.findings == []
        assert result.recommendations == []

    def test_to_dict(self):
        now = datetime.now(timezone.utc)
        result = ComplianceResult(
            framework=ComplianceFramework.GDPR, passed=True, score=100.0, timestamp=now
        )
        data = result.to_dict()
        assert data["framework"] == ComplianceFramework.GDPR.value
        assert data["passed"] is True
        assert data["score"] == 100.0
        assert data["timestamp"] == now.isoformat()


class TestSecurityPrincipal:
    def test_init_defaults(self):
        principal = SecurityPrincipal(id="1", name="user", type="user")
        assert principal.created_at is not None
        assert principal.is_active is True
        assert principal.roles == []


class TestThreatIndicator:
    def test_init_defaults(self):
        indicator = ThreatIndicator(
            indicator_id="1",
            indicator_type="ip",
            value="127.0.0.1",
            threat_level=SecurityThreatLevel.LOW,
            confidence=0.5,
            source="test",
        )
        assert indicator.first_seen is not None
        assert indicator.last_seen is not None
        assert indicator.is_active is True
