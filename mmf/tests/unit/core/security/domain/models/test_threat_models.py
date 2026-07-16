from datetime import datetime, timezone

import pytest

from mmf.core.domain.audit_types import SecurityEventType, SecurityThreatLevel
from mmf.core.security.domain.models.threat import (
    AnomalyDetectionResult,
    SecurityEvent,
    ServiceBehaviorProfile,
    ThreatDetectionResult,
    ThreatType,
    UserBehaviorProfile,
)


class TestThreatModels:
    def test_security_event_defaults(self):
        event = SecurityEvent(
            event_id="evt-123", event_type=SecurityEventType.AUTHENTICATION_SUCCESS
        )

        assert event.event_id == "evt-123"
        assert event.event_type == SecurityEventType.AUTHENTICATION_SUCCESS
        assert isinstance(event.timestamp, datetime)
        assert event.severity == SecurityThreatLevel.LOW
        assert event.details == {}
        assert event.metadata == {}

    def test_threat_detection_result_defaults(self):
        event = SecurityEvent(
            event_id="evt-123", event_type=SecurityEventType.AUTHENTICATION_SUCCESS
        )

        result = ThreatDetectionResult(
            event=event, is_threat=True, threat_score=0.8, threat_level=SecurityThreatLevel.HIGH
        )

        assert result.event == event
        assert result.is_threat is True
        assert result.threat_score == 0.8
        assert result.threat_level == SecurityThreatLevel.HIGH
        assert result.detected_threats == []
        assert isinstance(result.analyzed_at, datetime)

    def test_user_behavior_profile_defaults(self):
        profile = UserBehaviorProfile(user_id="user-123")

        assert profile.user_id == "user-123"
        assert isinstance(profile.created_at, datetime)
        assert isinstance(profile.updated_at, datetime)
        assert profile.typical_access_hours == []
        assert profile.avg_requests_per_hour == 0.0
        assert profile.anomaly_score == 0.0

    def test_service_behavior_profile_defaults(self):
        profile = ServiceBehaviorProfile(service_name="auth-service")

        assert profile.service_name == "auth-service"
        assert isinstance(profile.created_at, datetime)
        assert profile.typical_request_patterns == {}
        assert profile.avg_error_rate == 0.0
        assert profile.anomaly_score == 0.0

    def test_anomaly_detection_result_defaults(self):
        result = AnomalyDetectionResult(is_anomaly=True, anomaly_score=0.95, confidence=0.8)

        assert result.is_anomaly is True
        assert result.anomaly_score == 0.95
        assert result.confidence == 0.8
        assert result.detected_anomalies == []
        assert isinstance(result.analyzed_at, datetime)

    def test_threat_type_enum(self):
        assert ThreatType.INJECTION.value == "injection"
        assert ThreatType.XSS.value == "xss"
        assert ThreatType.INTRUSION.value == "intrusion"
