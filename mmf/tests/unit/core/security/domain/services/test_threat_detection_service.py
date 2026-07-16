from unittest.mock import AsyncMock, Mock

import pytest

from mmf.core.domain.audit_types import SecurityEventType, SecurityThreatLevel
from mmf.core.security.domain.models.threat import (
    AnomalyDetectionResult,
    SecurityEvent,
    ServiceBehaviorProfile,
    ThreatDetectionResult,
    UserBehaviorProfile,
)
from mmf.core.security.domain.services.threat_detection import ThreatDetectionService
from mmf.core.security.ports.threat_detection import IThreatDetector


class TestThreatDetectionService:
    @pytest.fixture
    def mock_detector(self):
        return Mock(spec=IThreatDetector)

    @pytest.fixture
    def service(self, mock_detector):
        return ThreatDetectionService(detector=mock_detector)

    @pytest.fixture
    def sample_event(self):
        return SecurityEvent(
            event_id="evt-123", event_type=SecurityEventType.AUTHENTICATION_SUCCESS
        )

    @pytest.mark.asyncio
    async def test_analyze_event_delegates_to_detector(self, service, mock_detector, sample_event):
        expected_result = ThreatDetectionResult(
            event=sample_event,
            is_threat=False,
            threat_score=0.0,
            threat_level=SecurityThreatLevel.LOW,
        )
        mock_detector.analyze_event = AsyncMock(return_value=expected_result)

        result = await service.analyze_event(sample_event)

        assert result == expected_result
        mock_detector.analyze_event.assert_called_once_with(sample_event)

    @pytest.mark.asyncio
    async def test_analyze_event_logs_threats(self, service, mock_detector, sample_event, caplog):
        expected_result = ThreatDetectionResult(
            event=sample_event,
            is_threat=True,
            threat_score=0.9,
            threat_level=SecurityThreatLevel.CRITICAL,
            detected_threats=["SQL Injection"],
        )
        mock_detector.analyze_event = AsyncMock(return_value=expected_result)

        await service.analyze_event(sample_event)

        assert "Threat detected: SQL Injection" in caplog.text
        assert "Score: 0.9" in caplog.text
        assert "Level: critical" in caplog.text

    @pytest.mark.asyncio
    async def test_analyze_event_propagates_exceptions(self, service, mock_detector, sample_event):
        mock_detector.analyze_event = AsyncMock(side_effect=ValueError("Analysis failed"))

        with pytest.raises(ValueError, match="Analysis failed"):
            await service.analyze_event(sample_event)

    @pytest.mark.asyncio
    async def test_analyze_user_behavior(self, service, mock_detector, sample_event):
        expected_profile = UserBehaviorProfile(user_id="user-123")
        mock_detector.analyze_user_behavior = AsyncMock(return_value=expected_profile)
        events = [sample_event]

        result = await service.analyze_user_behavior("user-123", events)

        assert result == expected_profile
        mock_detector.analyze_user_behavior.assert_called_once_with("user-123", events)

    @pytest.mark.asyncio
    async def test_analyze_service_behavior(self, service, mock_detector, sample_event):
        expected_profile = ServiceBehaviorProfile(service_name="auth-service")
        mock_detector.analyze_service_behavior = AsyncMock(return_value=expected_profile)
        events = [sample_event]

        result = await service.analyze_service_behavior("auth-service", events)

        assert result == expected_profile
        mock_detector.analyze_service_behavior.assert_called_once_with("auth-service", events)

    @pytest.mark.asyncio
    async def test_detect_anomalies(self, service, mock_detector):
        expected_result = AnomalyDetectionResult(is_anomaly=True, anomaly_score=0.8, confidence=0.9)
        mock_detector.detect_anomalies = AsyncMock(return_value=expected_result)
        data = {"metric": 100}

        result = await service.detect_anomalies(data)

        assert result == expected_result
        mock_detector.detect_anomalies.assert_called_once_with(data)
