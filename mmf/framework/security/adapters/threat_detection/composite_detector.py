"""
Composite Threat Detector

Aggregates multiple threat detectors into a single interface.
"""

from __future__ import annotations

import builtins
import logging
from typing import Any

from mmf.core.domain.audit_types import SecurityThreatLevel
from mmf.core.security.domain.models.threat import (
    AnomalyDetectionResult,
    SecurityEvent,
    ServiceBehaviorProfile,
    ThreatDetectionResult,
    UserBehaviorProfile,
)
from mmf.core.security.ports.threat_detection import IThreatDetector

logger = logging.getLogger(__name__)


class CompositeThreatDetector(IThreatDetector):
    """
    Composite threat detector that delegates to multiple detectors
    and aggregates the results.
    """

    def __init__(self, detectors: list[IThreatDetector]):
        """Initialize with a list of detectors."""
        self.detectors = detectors

    async def analyze_event(self, event: SecurityEvent) -> ThreatDetectionResult:
        """
        Analyze a security event using all registered detectors.
        Returns the aggregated result with the highest severity.
        """
        if not self.detectors:
            # Return a safe default if no detectors are configured
            return ThreatDetectionResult(
                event=event,
                is_threat=False,
                threat_score=0.0,
                threat_level=SecurityThreatLevel.LOW,
                analyzed_at=event.timestamp,
            )

        results = []
        for detector in self.detectors:
            try:
                result = await detector.analyze_event(event)
                results.append(result)
            except Exception as e:
                logger.error(f"Error in threat detector {detector.__class__.__name__}: {e}")

        return self._aggregate_results(event, results)

    def _aggregate_results(
        self, event: SecurityEvent, results: list[ThreatDetectionResult]
    ) -> ThreatDetectionResult:
        """Aggregate multiple detection results."""
        if not results:
            return ThreatDetectionResult(
                event=event, is_threat=False, threat_score=0.0, threat_level=SecurityThreatLevel.LOW
            )

        # Start with base result
        is_threat = False
        max_score = 0.0
        max_level = SecurityThreatLevel.LOW
        detected_threats = set()
        risk_factors = set()
        recommended_actions = set()
        correlated_events = set()

        # Severity mapping for comparison
        severity_map = {
            SecurityThreatLevel.LOW: 1,
            SecurityThreatLevel.MEDIUM: 2,
            SecurityThreatLevel.HIGH: 3,
            SecurityThreatLevel.CRITICAL: 4,
        }

        for res in results:
            if res.is_threat:
                is_threat = True

            if res.threat_score > max_score:
                max_score = res.threat_score

            if severity_map.get(res.threat_level, 0) > severity_map.get(max_level, 0):
                max_level = res.threat_level

            detected_threats.update(res.detected_threats)
            risk_factors.update(res.risk_factors)
            recommended_actions.update(res.recommended_actions)
            correlated_events.update(res.correlated_events)

        return ThreatDetectionResult(
            event=event,
            is_threat=is_threat,
            threat_score=max_score,
            threat_level=max_level,
            detected_threats=list(detected_threats),
            risk_factors=list(risk_factors),
            recommended_actions=list(recommended_actions),
            correlated_events=list(correlated_events),
        )

    async def analyze_user_behavior(
        self, user_id: str, recent_events: builtins.list[SecurityEvent]
    ) -> UserBehaviorProfile:
        """Analyze user behavior using all detectors and return the most significant profile."""
        best_profile = None
        max_anomaly_score = -1.0

        for detector in self.detectors:
            try:
                profile = await detector.analyze_user_behavior(user_id, recent_events)
                if profile and profile.anomaly_score > max_anomaly_score:
                    max_anomaly_score = profile.anomaly_score
                    best_profile = profile
            except Exception as e:
                logger.error(f"Error in user behavior analysis {detector.__class__.__name__}: {e}")

        if best_profile:
            return best_profile

        # Return empty profile if no results
        return UserBehaviorProfile(user_id=user_id)

    async def analyze_service_behavior(
        self, service_name: str, recent_events: builtins.list[SecurityEvent]
    ) -> ServiceBehaviorProfile:
        """Analyze service behavior using all detectors."""
        best_profile = None
        max_anomaly_score = -1.0

        for detector in self.detectors:
            try:
                profile = await detector.analyze_service_behavior(service_name, recent_events)
                if profile and profile.anomaly_score > max_anomaly_score:
                    max_anomaly_score = profile.anomaly_score
                    best_profile = profile
            except Exception as e:
                logger.error(
                    f"Error in service behavior analysis {detector.__class__.__name__}: {e}"
                )

        if best_profile:
            return best_profile

        return ServiceBehaviorProfile(service_name=service_name)

    async def detect_anomalies(self, data: builtins.dict[str, Any]) -> AnomalyDetectionResult:
        """Detect anomalies using all detectors."""
        best_result = None
        max_score = -1.0

        for detector in self.detectors:
            try:
                result = await detector.detect_anomalies(data)
                if result and result.anomaly_score > max_score:
                    max_score = result.anomaly_score
                    best_result = result
            except Exception as e:
                logger.error(f"Error in anomaly detection {detector.__class__.__name__}: {e}")

        if best_result:
            return best_result

        return AnomalyDetectionResult(is_anomaly=False, anomaly_score=0.0, confidence=0.0)

    async def get_threat_statistics(self) -> builtins.dict[str, Any]:
        """Get aggregated threat detection statistics."""
        stats = {"total_events_analyzed": 0, "total_threats_detected": 0, "detectors": {}}

        for detector in self.detectors:
            try:
                det_stats = await detector.get_threat_statistics()
                detector_name = detector.__class__.__name__
                stats["detectors"][detector_name] = det_stats

                # Try to aggregate common metrics if available
                if isinstance(det_stats, dict):
                    stats["total_events_analyzed"] += det_stats.get("events_analyzed", 0)
                    stats["total_threats_detected"] += det_stats.get("threats_detected", 0)
            except Exception as e:
                logger.error(f"Error getting statistics from {detector.__class__.__name__}: {e}")

        return stats
