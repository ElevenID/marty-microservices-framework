"""
Threat Detection Domain Service

Service for managing threat detection and response.
"""

from __future__ import annotations

import logging
from typing import Any

from mmf.core.security.domain.models.threat import (
    AnomalyDetectionResult,
    SecurityEvent,
    ServiceBehaviorProfile,
    ThreatDetectionResult,
    UserBehaviorProfile,
)
from mmf.core.security.ports.threat_detection import IThreatDetector

logger = logging.getLogger(__name__)


class ThreatDetectionService:
    """
    Domain service for threat detection.

    Orchestrates threat analysis using configured detectors.
    """

    def __init__(self, detector: IThreatDetector):
        """
        Initialize threat detection service.

        Args:
            detector: The threat detector implementation to use
        """
        self.detector = detector

    async def analyze_event(self, event: SecurityEvent) -> ThreatDetectionResult:
        """
        Analyze a security event for threats.

        Args:
            event: The security event to analyze

        Returns:
            Threat detection result
        """
        try:
            result = await self.detector.analyze_event(event)

            if result.is_threat:
                threats = (
                    ", ".join(result.detected_threats) if result.detected_threats else "Unknown"
                )
                logger.warning(
                    f"Threat detected: {threats} "
                    f"(Score: {result.threat_score}, Level: {result.threat_level.value})"
                )

            return result
        except Exception as e:
            logger.error(f"Error analyzing event: {e}")
            # Return a safe default or re-raise depending on policy
            # For now, we re-raise to let the caller handle it
            raise

    async def analyze_user_behavior(
        self, user_id: str, recent_events: list[SecurityEvent]
    ) -> UserBehaviorProfile:
        """
        Analyze user behavior for anomalies.

        Args:
            user_id: User ID to analyze
            recent_events: List of recent security events for the user

        Returns:
            User behavior profile
        """
        return await self.detector.analyze_user_behavior(user_id, recent_events)

    async def analyze_service_behavior(
        self, service_name: str, recent_events: list[SecurityEvent]
    ) -> ServiceBehaviorProfile:
        """
        Analyze service behavior for anomalies.

        Args:
            service_name: Service name to analyze
            recent_events: List of recent security events for the service

        Returns:
            Service behavior profile
        """
        return await self.detector.analyze_service_behavior(service_name, recent_events)

    async def detect_anomalies(self, data: dict[str, Any]) -> AnomalyDetectionResult:
        """
        Detect anomalies in generic data.

        Args:
            data: Data to analyze

        Returns:
            Anomaly detection result
        """
        return await self.detector.detect_anomalies(data)

    async def get_threat_statistics(self) -> dict[str, Any]:
        """
        Get threat detection statistics.

        Returns:
            Dictionary of threat statistics
        """
        return await self.detector.get_threat_statistics()
