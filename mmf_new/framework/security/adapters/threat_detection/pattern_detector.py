"""
Pattern-Based Threat Detector Adapter

Pattern-based threat detector implementing IThreatDetector.
"""

import builtins
import re
from collections import defaultdict, deque
from datetime import datetime, timezone
from typing import Any

from mmf_new.core.security.domain.models.threat import (
    SecurityEvent,
    ThreatDetectionResult,
    ThreatType,
)
from mmf_new.core.security.ports.threat_detection import IThreatDetector
from mmf_new.core.domain.audit_types import SecurityThreatLevel


class PatternBasedThreatDetector(IThreatDetector):
    """Pattern-based threat detector."""

    def __init__(self, service_name: str):
        """Initialize pattern-based detector."""
        self.service_name = service_name
        self.threat_patterns = self._load_threat_patterns()

        # Detection history
        self.detection_history: deque = deque(maxlen=1000)
        self.threat_counts: builtins.dict[str, int] = defaultdict(int)

    def _load_threat_patterns(self) -> builtins.dict[str, builtins.dict[str, Any]]:
        """Load threat detection patterns."""
        return {
            "sql_injection_attempt": {
                "pattern": r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION)\b|--\s)",
                "type": ThreatType.INJECTION,
                "severity": SecurityThreatLevel.HIGH,
                "description": "Potential SQL injection attempt detected",
            },
            "xss_attempt": {
                "pattern": r"(<script|javascript:|on\w+\s*=)",
                "type": ThreatType.INJECTION,
                "severity": SecurityThreatLevel.MEDIUM,
                "description": "Potential XSS attempt detected",
            },
            "path_traversal_attempt": {
                "pattern": r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e%5c)",
                "type": ThreatType.INTRUSION,
                "severity": SecurityThreatLevel.HIGH,
                "description": "Potential path traversal attempt detected",
            },
            "brute_force_attempt": {
                "pattern": r"(failed_login|invalid_password|auth_failure)",
                "type": ThreatType.BRUTE_FORCE,
                "severity": SecurityThreatLevel.MEDIUM,
                "description": "Potential brute force attempt detected",
            },
            "suspicious_user_agent": {
                "pattern": r"(sqlmap|nikto|burp|acunetix|nmap)",
                "type": ThreatType.RECONNAISSANCE,
                "severity": SecurityThreatLevel.LOW,
                "description": "Suspicious user agent detected",
            },
        }

    async def analyze_event(self, event: SecurityEvent) -> ThreatDetectionResult:
        """Analyze a security event for threats."""
        # Extract event data for analysis
        event_data = str(event.details)
        # source_ip = event.source_ip  # Unused in this method
        user_agent = event.user_agent or ""

        # Check against patterns
        for threat_name, pattern_info in self.threat_patterns.items():
            pattern = pattern_info["pattern"]

            # Check event details
            if re.search(pattern, event_data, re.IGNORECASE):
                return self._create_threat_result(
                    event, threat_name, pattern_info, "event_details"
                )

            # Check user agent if applicable
            if "user_agent" in threat_name and re.search(pattern, user_agent, re.IGNORECASE):
                return self._create_threat_result(
                    event, threat_name, pattern_info, "user_agent"
                )

        # No threat detected
        return ThreatDetectionResult(
            event=event,
            is_threat=False,
            threat_score=0.0,
            threat_level=SecurityThreatLevel.LOW,
            analyzed_at=datetime.now(timezone.utc),
        )

    async def analyze_user_behavior(
        self, user_id: str, recent_events: builtins.list[SecurityEvent]
    ) -> Any:
        """Analyze user behavior (Not implemented for pattern detector)."""
        # Pattern detector doesn't do behavioral analysis
        return None

    async def analyze_service_behavior(
        self, service_name: str, recent_events: builtins.list[SecurityEvent]
    ) -> Any:
        """Analyze service behavior (Not implemented for pattern detector)."""
        return None

    async def detect_anomalies(self, data: builtins.dict[str, Any]) -> Any:
        """Detect anomalies (Not implemented for pattern detector)."""
        return None

    async def get_threat_statistics(self) -> builtins.dict[str, Any]:
        """Get threat detection statistics."""
        return {
            "total_detections": len(self.detection_history),
            "by_type": dict(self.threat_counts),
            "active_patterns": len(self.threat_patterns),
        }

    def _create_threat_result(
        self,
        event: SecurityEvent,
        threat_name: str,
        pattern_info: builtins.dict[str, Any],
        source: str,
    ) -> ThreatDetectionResult:
        """Create threat detection result."""
        return ThreatDetectionResult(
            event=event,
            is_threat=True,
            threat_score=0.8,
            threat_level=pattern_info["severity"],
            detected_threats=[f"{threat_name} in {source}"],
            risk_factors=[pattern_info["description"]],
            recommended_actions=["Review logs", "Block IP if repeated"],
            analyzed_at=datetime.now(timezone.utc),
        )

    async def analyze_behavior(self, events: builtins.list[SecurityEvent]) -> builtins.list[ThreatDetectionResult]:
        """Analyze behavior patterns across multiple events."""
        threats = []

        # Group events by source IP
        events_by_ip = defaultdict(list)
        for event in events:
            if event.source_ip:
                events_by_ip[event.source_ip].append(event)

        # Analyze each IP's behavior
        for ip, ip_events in events_by_ip.items():
            # Check for high frequency of events (potential DoS or brute force)
            if len(ip_events) > 50:  # Threshold
                threat = ThreatDetectionResult(
                    event=ip_events[0],
                    is_threat=True,
                    threat_score=0.7,
                    threat_level=SecurityThreatLevel.HIGH,
                    detected_threats=[f"High event frequency from IP {ip}"],
                    risk_factors=["Potential DoS", "Brute Force"],
                    recommended_actions=["Rate limit IP", "Block IP"],
                    analyzed_at=datetime.now(timezone.utc),
                )
                threats.append(threat)

            # Check for multiple failed logins
            failed_logins = [
                e for e in ip_events
                if e.event_type == "authentication_failure"
            ]

            if len(failed_logins) > 5:
                threat = ThreatDetectionResult(
                    event=failed_logins[0],
                    is_threat=True,
                    threat_score=0.9,
                    threat_level=SecurityThreatLevel.MEDIUM,
                    detected_threats=[f"Multiple failed logins from IP {ip}"],
                    risk_factors=["Brute Force", "Credential Stuffing"],
                    recommended_actions=["Lock account", "Block IP"],
                    analyzed_at=datetime.now(timezone.utc),
                )
                threats.append(threat)

        return threats
