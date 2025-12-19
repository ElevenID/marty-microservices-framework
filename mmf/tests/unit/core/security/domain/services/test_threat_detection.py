from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock

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
from mmf.core.security.domain.services.threat_detection import ThreatDetectionService
from mmf.core.security.ports.threat_detection import IThreatDetector


@pytest.fixture
def mock_detector():
    return AsyncMock(spec=IThreatDetector)


@pytest.fixture
def service(mock_detector):
    return ThreatDetectionService(detector=mock_detector)


@pytest.mark.asyncio
class TestThreatDetectionService:
    async def test_analyze_event_no_threat(self, service, mock_detector):
        # Setup
        event = SecurityEvent(
            event_id="evt-123",
            event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
            timestamp=datetime.now(timezone.utc),
            user_id="user-123",
        )
        expected_result = ThreatDetectionResult(
            event=event, is_threat=False, threat_score=0.0, threat_level=SecurityThreatLevel.LOW
        )
        mock_detector.analyze_event.return_value = expected_result

        # Execute
        result = await service.analyze_event(event)

        # Verify
        assert result == expected_result
        mock_detector.analyze_event.assert_called_once_with(event)

    async def test_analyze_event_with_threat(self, service, mock_detector):
        # Setup
        event = SecurityEvent(
            event_id="evt-456",
            event_type=SecurityEventType.AUTHENTICATION_FAILURE,
            timestamp=datetime.now(timezone.utc),
            user_id="user-bad",
        )
        expected_result = ThreatDetectionResult(
            event=event,
            is_threat=True,
            threat_score=0.9,
            threat_level=SecurityThreatLevel.CRITICAL,
            detected_threats=[ThreatType.BRUTE_FORCE.value],
        )
        mock_detector.analyze_event.return_value = expected_result

        # Execute
        result = await service.analyze_event(event)

        # Verify
        assert result == expected_result
        mock_detector.analyze_event.assert_called_once_with(event)

    async def test_analyze_event_error(self, service, mock_detector):
        # Setup
        event = SecurityEvent(
            event_id="evt-err",
            event_type=SecurityEventType.SYSTEM_ERROR,
            timestamp=datetime.now(timezone.utc),
        )
        mock_detector.analyze_event.side_effect = Exception("Detection failed")

        # Execute & Verify
        with pytest.raises(Exception, match="Detection failed"):
            await service.analyze_event(event)

    async def test_analyze_user_behavior(self, service, mock_detector):
        # Setup
        user_id = "user-123"
        events = []
        expected_profile = UserBehaviorProfile(user_id=user_id)
        mock_detector.analyze_user_behavior.return_value = expected_profile

        # Execute
        result = await service.analyze_user_behavior(user_id, events)

        # Verify
        assert result == expected_profile
        mock_detector.analyze_user_behavior.assert_called_once_with(user_id, events)

    async def test_analyze_service_behavior(self, service, mock_detector):
        # Setup
        service_name = "payment-service"
        events = []
        expected_profile = ServiceBehaviorProfile(service_name=service_name)
        mock_detector.analyze_service_behavior.return_value = expected_profile

        # Execute
        result = await service.analyze_service_behavior(service_name, events)

        # Verify
        assert result == expected_profile
        mock_detector.analyze_service_behavior.assert_called_once_with(service_name, events)

    async def test_detect_anomalies(self, service, mock_detector):
        # Setup
        data = {"metric": 100}
        expected_result = AnomalyDetectionResult(is_anomaly=True, anomaly_score=0.8, confidence=0.9)
        mock_detector.detect_anomalies.return_value = expected_result

        # Execute
        result = await service.detect_anomalies(data)

        # Verify
        assert result == expected_result
        mock_detector.detect_anomalies.assert_called_once_with(data)

    async def test_get_threat_statistics(self, service, mock_detector):
        # Setup
        expected_stats = {"threats_detected": 10}
        mock_detector.get_threat_statistics.return_value = expected_stats

        # Execute
        result = await service.get_threat_statistics()

        # Verify
        assert result == expected_stats
        mock_detector.get_threat_statistics.assert_called_once()
