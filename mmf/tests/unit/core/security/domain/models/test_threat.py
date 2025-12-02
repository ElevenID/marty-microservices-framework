from datetime import datetime, timezone

import pytest

from mmf.core.security.domain.models.threat import (
    AnomalyDetectionResult,
    SecurityEvent,
    SecurityThreatLevel,
    ServiceBehaviorProfile,
    ThreatDetectionResult,
    ThreatType,
    UserBehaviorProfile,
)


class TestThreatType:
    def test_threat_type_enum_values(self):
        """Test that ThreatType enum has expected values."""
        assert ThreatType.INJECTION.value == "injection"
        assert ThreatType.XSS.value == "xss"
        assert ThreatType.INTRUSION.value == "intrusion"
        assert ThreatType.BRUTE_FORCE.value == "brute_force"
        assert ThreatType.DOS.value == "dos"
        assert ThreatType.RECONNAISSANCE.value == "reconnaissance"
        assert ThreatType.MALWARE.value == "malware"
        assert ThreatType.DATA_LEAK.value == "data_leak"
        assert ThreatType.UNKNOWN.value == "unknown"


class TestSecurityEvent:
    def test_security_event_creation(self):
        """Test creating a SecurityEvent."""
        event = SecurityEvent(
            event_id="evt-123",
            event_type="login_failed",
            severity=SecurityThreatLevel.HIGH,
            source_ip="192.168.1.1",
            user_id="user-123",
            details={"reason": "bad_password"},
        )

        assert event.event_id == "evt-123"
        assert event.event_type == "login_failed"
        assert event.severity == SecurityThreatLevel.HIGH
        assert event.source_ip == "192.168.1.1"
        assert event.user_id == "user-123"
        assert event.details == {"reason": "bad_password"}
        assert isinstance(event.timestamp, datetime)

    def test_security_event_defaults(self):
        """Test SecurityEvent default values."""
        event = SecurityEvent(
            event_id="evt-123", event_type="login_failed", severity=SecurityThreatLevel.LOW
        )

        assert event.source_ip is None
        assert event.user_id is None
        assert event.details == {}
        assert isinstance(event.timestamp, datetime)


class TestThreatDetectionResult:
    def test_threat_detection_result_creation(self):
        """Test creating a ThreatDetectionResult."""
        event = SecurityEvent(
            event_id="evt-123", event_type="login_failed", severity=SecurityThreatLevel.HIGH
        )

        result = ThreatDetectionResult(
            event=event,
            is_threat=True,
            threat_score=0.85,
            threat_level=SecurityThreatLevel.CRITICAL,
            detected_threats=["brute_force"],
            risk_factors=["multiple_failures"],
            recommended_actions=["block_ip"],
            correlated_events=["evt-122"],
        )

        assert result.event == event
        assert result.is_threat is True
        assert result.threat_score == 0.85
        assert result.threat_level == SecurityThreatLevel.CRITICAL
        assert result.detected_threats == ["brute_force"]
        assert result.risk_factors == ["multiple_failures"]
        assert result.recommended_actions == ["block_ip"]
        assert result.correlated_events == ["evt-122"]
        assert isinstance(result.analyzed_at, datetime)

    def test_threat_detection_result_defaults(self):
        """Test ThreatDetectionResult default values."""
        event = SecurityEvent(
            event_id="evt-123", event_type="login_failed", severity=SecurityThreatLevel.HIGH
        )

        result = ThreatDetectionResult(
            event=event, is_threat=False, threat_score=0.0, threat_level=SecurityThreatLevel.LOW
        )

        assert result.detected_threats == []
        assert result.risk_factors == []
        assert result.recommended_actions == []
        assert result.correlated_events == []
        assert isinstance(result.analyzed_at, datetime)


class TestUserBehaviorProfile:
    def test_user_behavior_profile_creation(self):
        """Test creating a UserBehaviorProfile."""
        profile = UserBehaviorProfile(
            user_id="user-123",
            typical_access_hours=[9, 10, 11],
            typical_services=["auth-service"],
            typical_endpoints=["/login"],
            typical_ip_ranges=["192.168.1.0/24"],
            avg_requests_per_hour=50.0,
            avg_session_duration=3600.0,
            avg_response_time=0.2,
            failed_login_rate=0.01,
            privilege_escalation_attempts=0,
            unusual_access_count=0,
            feature_vector=[0.1, 0.2, 0.3],
            anomaly_score=0.05,
        )

        assert profile.user_id == "user-123"
        assert profile.typical_access_hours == [9, 10, 11]
        assert profile.typical_services == ["auth-service"]
        assert profile.typical_endpoints == ["/login"]
        assert profile.typical_ip_ranges == ["192.168.1.0/24"]
        assert profile.avg_requests_per_hour == 50.0
        assert profile.avg_session_duration == 3600.0
        assert profile.avg_response_time == 0.2
        assert profile.failed_login_rate == 0.01
        assert profile.privilege_escalation_attempts == 0
        assert profile.unusual_access_count == 0
        assert profile.feature_vector == [0.1, 0.2, 0.3]
        assert profile.anomaly_score == 0.05
        assert isinstance(profile.created_at, datetime)
        assert isinstance(profile.updated_at, datetime)

    def test_user_behavior_profile_defaults(self):
        """Test UserBehaviorProfile default values."""
        profile = UserBehaviorProfile(user_id="user-123")

        assert profile.typical_access_hours == []
        assert profile.typical_services == []
        assert profile.typical_endpoints == []
        assert profile.typical_ip_ranges == []
        assert profile.avg_requests_per_hour == 0.0
        assert profile.avg_session_duration == 0.0
        assert profile.avg_response_time == 0.0
        assert profile.failed_login_rate == 0.0
        assert profile.privilege_escalation_attempts == 0
        assert profile.unusual_access_count == 0
        assert profile.feature_vector == []
        assert profile.anomaly_score == 0.0


class TestServiceBehaviorProfile:
    def test_service_behavior_profile_creation(self):
        """Test creating a ServiceBehaviorProfile."""
        profile = ServiceBehaviorProfile(
            service_name="auth-service",
            avg_response_time=0.1,
            avg_throughput=100.0,
            avg_error_rate=0.001,
            avg_cpu_usage=45.0,
            avg_memory_usage=512.0,
            typical_request_patterns={"GET /login": 0.8},
            typical_user_agents=["Mozilla/5.0"],
            typical_source_countries=["US"],
            auth_failure_rate=0.02,
            suspicious_request_rate=0.0,
            malicious_ip_access_rate=0.0,
            feature_vector=[0.5, 0.6],
            anomaly_score=0.1,
        )

        assert profile.service_name == "auth-service"
        assert profile.avg_response_time == 0.1
        assert profile.avg_throughput == 100.0
        assert profile.avg_error_rate == 0.001
        assert profile.avg_cpu_usage == 45.0
        assert profile.avg_memory_usage == 512.0
        assert profile.typical_request_patterns == {"GET /login": 0.8}
        assert profile.typical_user_agents == ["Mozilla/5.0"]
        assert profile.typical_source_countries == ["US"]
        assert profile.auth_failure_rate == 0.02
        assert profile.suspicious_request_rate == 0.0
        assert profile.malicious_ip_access_rate == 0.0
        assert profile.feature_vector == [0.5, 0.6]
        assert profile.anomaly_score == 0.1
        assert isinstance(profile.created_at, datetime)
        assert isinstance(profile.updated_at, datetime)

    def test_service_behavior_profile_defaults(self):
        """Test ServiceBehaviorProfile default values."""
        profile = ServiceBehaviorProfile(service_name="auth-service")

        assert profile.avg_response_time == 0.0
        assert profile.avg_throughput == 0.0
        assert profile.avg_error_rate == 0.0
        assert profile.avg_cpu_usage == 0.0
        assert profile.avg_memory_usage == 0.0
        assert profile.typical_request_patterns == {}
        assert profile.typical_user_agents == []
        assert profile.typical_source_countries == []
        assert profile.auth_failure_rate == 0.0
        assert profile.suspicious_request_rate == 0.0
        assert profile.malicious_ip_access_rate == 0.0
        assert profile.feature_vector == []
        assert profile.anomaly_score == 0.0


class TestAnomalyDetectionResult:
    def test_anomaly_detection_result_creation(self):
        """Test creating an AnomalyDetectionResult."""
        result = AnomalyDetectionResult(
            is_anomaly=True,
            anomaly_score=-0.8,
            confidence=0.95,
            detected_anomalies=["high_cpu"],
            baseline_deviation={"cpu": 2.5},
        )

        assert result.is_anomaly is True
        assert result.anomaly_score == -0.8
        assert result.confidence == 0.95
        assert result.detected_anomalies == ["high_cpu"]
        assert result.baseline_deviation == {"cpu": 2.5}
        assert isinstance(result.analyzed_at, datetime)

    def test_anomaly_detection_result_defaults(self):
        """Test AnomalyDetectionResult default values."""
        result = AnomalyDetectionResult(is_anomaly=False, anomaly_score=0.1, confidence=0.5)

        assert result.detected_anomalies == []
        assert result.baseline_deviation == {}
        assert isinstance(result.analyzed_at, datetime)
