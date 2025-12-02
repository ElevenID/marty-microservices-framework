import asyncio
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from prometheus_client import REGISTRY

from mmf.core.domain.audit_types import SecurityEventType, SecurityThreatLevel
from mmf.core.security.domain.config import ThreatDetectionConfig
from mmf.core.security.domain.models.threat import (
    AnomalyDetectionResult,
    SecurityEvent,
    ThreatDetectionResult,
)
from mmf.framework.security.adapters.threat_detection.event_processor import (
    EventProcessorThreatDetector,
)


@pytest.fixture
def threat_config():
    return ThreatDetectionConfig(
        enabled=True,
    )


@pytest.fixture
def detector(threat_config):
    # Clear registry to avoid duplicate metrics error
    collectors = list(REGISTRY._collector_to_names.keys())
    for collector in collectors:
        REGISTRY.unregister(collector)

    return EventProcessorThreatDetector(threat_config)


@pytest.mark.asyncio
async def test_initialization(detector):
    assert detector.processing_queue is not None
    assert len(detector.filters) > 0
    assert len(detector.rules) > 0


@pytest.mark.asyncio
async def test_analyze_event_high_severity(detector):
    # Create a mock event that should trigger a rule
    event = SecurityEvent(
        event_id="evt-1",
        timestamp=datetime.now(timezone.utc),
        event_type=SecurityEventType.AUTHENTICATION_FAILURE,
        severity=SecurityThreatLevel.HIGH,
        service_name="gateway",
        details={"description": "Multiple failed login attempts"},
        metadata={"source_ip": "192.168.1.100", "user": "admin"},
    )

    result = await detector.analyze_event(event)

    assert isinstance(result, ThreatDetectionResult)


@pytest.mark.asyncio
async def test_analyze_event_low_severity(detector):
    event = SecurityEvent(
        event_id="evt-2",
        timestamp=datetime.now(timezone.utc),
        event_type=SecurityEventType.AUTHENTICATION_SUCCESS,  # Changed to valid type
        severity=SecurityThreatLevel.LOW,
        service_name="frontend",
        details={"description": "User login success"},
        metadata={"user": "user1"},
    )

    result = await detector.analyze_event(event)
    assert isinstance(result, ThreatDetectionResult)


@pytest.mark.asyncio
async def test_detect_anomalies(detector):
    # This method takes a dict, not service_id/time_window
    result = await detector.detect_anomalies(data={"some": "data"})
    # It returns AnomalyDetectionResult, not list
    assert isinstance(result, AnomalyDetectionResult)
    assert result.is_anomaly is False


@pytest.mark.asyncio
async def test_get_threat_statistics(detector):
    # Replaced update_service_profile with get_threat_statistics which exists
    stats = await detector.get_threat_statistics()
    assert isinstance(stats, dict)
    assert "events_processed" in stats
