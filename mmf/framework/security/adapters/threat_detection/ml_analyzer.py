"""
ML Threat Detector Adapter

Machine Learning based threat detection adapter implementing IThreatDetector.
"""

import builtins
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Any

import joblib
import numpy as np
from sklearn.cluster import DBSCAN
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler

from mmf.core.domain.audit_types import SecurityThreatLevel
from mmf.core.security.domain.config import ThreatDetectionConfig
from mmf.core.security.domain.models.threat import (
    AnomalyDetectionResult,
    SecurityEvent,
    ServiceBehaviorProfile,
    ThreatDetectionResult,
    UserBehaviorProfile,
)
from mmf.core.security.ports.threat_detection import IThreatDetector

logger = logging.getLogger(__name__)

_placeholder_mode_logged = False

# Optional ML dependencies
try:
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False
    logger.warning("ML libraries not available. ML threat detection will be disabled.")


class MLThreatDetector(IThreatDetector):
    """
    Machine Learning Security Analytics Engine.

    Features:
    - Isolation Forest for anomaly detection
    - DBSCAN for clustering unusual behaviors
    - Random Forest for threat classification
    - Behavioral profiling
    """

    def __init__(self, config: ThreatDetectionConfig):
        self.config = config
        self.user_profiles: builtins.dict[str, UserBehaviorProfile] = {}
        self.service_profiles: builtins.dict[str, ServiceBehaviorProfile] = {}

        # ML Models
        self.anomaly_detector = None
        self.threat_classifier = None
        self.behavior_clusterer = None
        self.scaler = None

        if ML_AVAILABLE and config.enable_ml_detection:
            self._initialize_models()

    def _initialize_models(self):
        """Initialize ML models."""
        try:
            self.anomaly_detector = IsolationForest(
                contamination=1.0 - self.config.anomaly_threshold,
                random_state=42,
                n_estimators=100,
            )

            self.threat_classifier = RandomForestClassifier(
                n_estimators=100, random_state=42, max_depth=10
            )

            self.behavior_clusterer = DBSCAN(eps=0.5, min_samples=5)
            self.scaler = StandardScaler()

            logger.info("Initialized ML models for security analytics")
        except Exception as e:
            logger.error(f"Failed to initialize ML models: {e}")

    def _warn_placeholder_mode(self, operation: str) -> None:
        """Log once when fallback placeholder logic is being used."""
        global _placeholder_mode_logged
        if _placeholder_mode_logged:
            return
        _placeholder_mode_logged = True
        logger.warning(
            "ML threat detection placeholder mode active during %s; "
            "results are heuristic/default until feature extraction and model training are implemented",
            operation,
        )

    async def analyze_event(self, event: SecurityEvent) -> ThreatDetectionResult:
        """Analyze event using ML models (Placeholder)."""
        # ML detector focuses on behavioral analysis, not single event
        self._warn_placeholder_mode("analyze_event")
        return ThreatDetectionResult(
            event=event,
            is_threat=False,
            threat_score=0.0,
            threat_level=SecurityThreatLevel.LOW,
            analyzed_at=datetime.now(timezone.utc),
        )

    async def analyze_user_behavior(
        self, user_id: str, recent_events: builtins.list[SecurityEvent]
    ) -> UserBehaviorProfile:
        """Analyze user behavior and update profile."""
        if user_id not in self.user_profiles:
            self.user_profiles[user_id] = UserBehaviorProfile(user_id=user_id)

        profile = self.user_profiles[user_id]

        if not recent_events:
            return profile

        # Update metrics based on events
        # (Simplified logic for migration)
        timestamps = [e.timestamp for e in recent_events]
        if timestamps:
            profile.updated_at = max(timestamps)

        # ML Analysis
        if self.anomaly_detector and len(recent_events) > 10:
            # Extract features (mock)
            # features = np.array([[len(e.endpoint or "") for e in recent_events]])
            # In real impl, we would extract meaningful features and use the detector
            self._warn_placeholder_mode("analyze_user_behavior")
            pass

        return profile

    async def analyze_service_behavior(
        self, service_name: str, recent_events: builtins.list[SecurityEvent]
    ) -> ServiceBehaviorProfile:
        """Analyze service behavior."""
        # Mock implementation - recent_events unused for now
        self._warn_placeholder_mode("analyze_service_behavior")
        _ = recent_events
        if service_name not in self.service_profiles:
            self.service_profiles[service_name] = ServiceBehaviorProfile(service_name=service_name)

        return self.service_profiles[service_name]

    async def detect_anomalies(self, data: builtins.dict[str, Any]) -> AnomalyDetectionResult:
        """Detect anomalies in generic data."""
        # Mock implementation - data unused for now
        self._warn_placeholder_mode("detect_anomalies")
        _ = data
        if not self.anomaly_detector:
            return AnomalyDetectionResult(is_anomaly=False, anomaly_score=0.0, confidence=0.0)

        # Convert data to feature vector (simplified)
        try:
            # Mock feature extraction
            features = np.array([[0.0]])
            score = self.anomaly_detector.decision_function(features)[0]
            is_anomaly = score < 0

            return AnomalyDetectionResult(
                is_anomaly=is_anomaly,
                anomaly_score=float(score),
                confidence=0.8,
                analyzed_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error("Error detecting anomalies: %s", e)
            return AnomalyDetectionResult(is_anomaly=False, anomaly_score=0.0, confidence=0.0)

    async def get_threat_statistics(self) -> builtins.dict[str, Any]:
        """Get threat detection statistics."""
        return {
            "ml_enabled": ML_AVAILABLE and self.config.enable_ml_detection,
            "placeholder_mode": True,
            "user_profiles": len(self.user_profiles),
            "service_profiles": len(self.service_profiles),
        }
