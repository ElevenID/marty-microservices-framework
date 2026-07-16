"""
Threat Detection Factory

Factory for creating threat detection components.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mmf.core.security.domain.config import SecurityConfig
from mmf.core.security.ports.threat_detection import (
    IThreatDetector,
    IVulnerabilityScanner,
)
from mmf.framework.security.adapters.threat_detection.composite_detector import (
    CompositeThreatDetector,
)
from mmf.framework.security.adapters.threat_detection.event_processor import (
    EventProcessorThreatDetector,
)
from mmf.framework.security.adapters.threat_detection.ml_analyzer import (
    MLThreatDetector,
)
from mmf.framework.security.adapters.threat_detection.pattern_detector import (
    PatternBasedThreatDetector,
)
from mmf.framework.security.adapters.threat_detection.scanner import (
    VulnerabilityScanner,
)


@dataclass
class RegistrationEntry:
    """Service registration entry."""

    interface: type
    instance: Any


class ThreatDetectionFactory:
    """Factory for threat detection components."""

    @staticmethod
    def create_registrations(config: SecurityConfig) -> list[RegistrationEntry]:
        """Create all threat detection components and return registration entries."""
        td_config = config.threat_detection_config
        service_name = config.service_name
        entries = []
        detectors: list[IThreatDetector] = []

        # 1. Initialize Event Processor (Primary Detector)
        event_processor = EventProcessorThreatDetector(td_config)
        detectors.append(event_processor)
        entries.append(RegistrationEntry(EventProcessorThreatDetector, event_processor))

        # 2. Initialize ML Detector
        if td_config.enable_ml_detection:
            ml_detector = MLThreatDetector(td_config)
            detectors.append(ml_detector)
            entries.append(RegistrationEntry(MLThreatDetector, ml_detector))

        # 3. Initialize Pattern Detector
        pattern_detector = PatternBasedThreatDetector(service_name)
        detectors.append(pattern_detector)
        entries.append(RegistrationEntry(PatternBasedThreatDetector, pattern_detector))

        # 4. Create Composite Detector
        composite_detector = CompositeThreatDetector(detectors)
        entries.append(RegistrationEntry(IThreatDetector, composite_detector))

        # 5. Initialize Scanner
        scanner = VulnerabilityScanner(service_name)
        entries.append(RegistrationEntry(IVulnerabilityScanner, scanner))

        return entries
