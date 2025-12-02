"""
Unit tests for Threat Detection module.
"""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from mmf.core.domain.audit_types import SecurityThreatLevel
from mmf.core.security.domain.config import ThreatDetectionConfig
from mmf.core.security.domain.models.threat import SecurityEvent, ThreatType
from mmf.framework.security.adapters.threat_detection.event_processor import (
    EventProcessorThreatDetector,
)
from mmf.framework.security.adapters.threat_detection.pattern_detector import (
    PatternBasedThreatDetector,
)
from mmf.framework.security.adapters.threat_detection.scanner import (
    VulnerabilityScanner,
)


@pytest.fixture
def pattern_detector():
    return PatternBasedThreatDetector("test-service")


@pytest.fixture
def scanner():
    return VulnerabilityScanner("test-service")


@pytest.fixture
def event_processor():
    config = ThreatDetectionConfig()
    return EventProcessorThreatDetector(config)


@pytest.mark.asyncio
async def test_pattern_detector_sql_injection(pattern_detector):
    event = SecurityEvent(
        event_id="evt-1",
        event_type="request",
        timestamp=datetime.now(timezone.utc),
        service_name="gateway",
        details={"payload": "SELECT * FROM users"},
        source_ip="1.2.3.4",
    )

    result = await pattern_detector.analyze_event(event)

    assert result.is_threat is True
    assert result.threat_level == SecurityThreatLevel.HIGH
    assert any("sql_injection_attempt" in t for t in result.detected_threats)


@pytest.mark.asyncio
async def test_pattern_detector_no_threat(pattern_detector):
    event = SecurityEvent(
        event_id="evt-2",
        event_type="request",
        timestamp=datetime.now(timezone.utc),
        service_name="gateway",
        details={"payload": "Hello World"},
        source_ip="1.2.3.4",
    )

    result = await pattern_detector.analyze_event(event)

    assert result.is_threat is False
    assert result.threat_level == SecurityThreatLevel.LOW


def test_scanner_sql_injection(scanner):
    code = """
    def get_user(id):
        query = "SELECT * FROM users WHERE id = " + id
        execute(query)
    """
    vulnerabilities = scanner.scan_code(code, "test.py")

    assert len(vulnerabilities) > 0
    assert any("Sql Injection" in v.title for v in vulnerabilities)
    assert vulnerabilities[0].severity == SecurityThreatLevel.HIGH


def test_scanner_hardcoded_secret(scanner):
    code = """
    API_KEY = "1234567890abcdef"
    """
    vulnerabilities = scanner.scan_code(code, "config.py")

    assert len(vulnerabilities) > 0
    assert any("Hardcoded Secret" in v.title for v in vulnerabilities)
    assert vulnerabilities[0].severity == SecurityThreatLevel.CRITICAL


def test_scanner_configuration(scanner):
    config = {"debug": True, "ssl_verify": False, "database": {"host": "localhost"}}

    vulnerabilities = scanner.scan_configuration(config)

    assert len(vulnerabilities) >= 2
    titles = [v.title for v in vulnerabilities]
    assert any("debug" in t for t in titles)
    assert any("ssl_verify" in t for t in titles)


@pytest.mark.asyncio
async def test_event_processor_initialization(event_processor):
    assert event_processor.config.enabled is True
    assert event_processor.processing_queue.maxsize == 50000
