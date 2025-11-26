"""
Threat Analyzer Adapter

Implements IThreatAnalyzer interface by integrating with existing
ML-based threat detection infrastructure and analytics engines.
"""

import logging
import re
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from mmf_new.core.domain.audit_types import SecurityEventSeverity, ThreatCategory
from mmf_new.framework.infrastructure.database_manager import DatabaseManager
from mmf_new.framework.infrastructure.framework_metrics import FrameworkMetrics

from ..domain.contracts import IThreatAnalyzer
from ..domain.models import SecurityAuditEvent, ThreatPattern

logger = logging.getLogger(__name__)


class ThreatAnalyzerAdapter(IThreatAnalyzer):
    """
    Threat analyzer adapter that integrates existing ML-based threat detection
    infrastructure with hexagonal architecture patterns.
    """

    def __init__(
        self,
        database_manager: DatabaseManager,
        metrics: FrameworkMetrics,
        config: dict[str, Any] | None = None,
    ):
        self.database_manager = database_manager
        self.metrics = metrics
        self.config = config or {}

        # Initialize threat detection patterns
        self._initialize_threat_patterns()

        # Threat analysis configuration
        self.confidence_threshold = self.config.get("confidence_threshold", 0.7)
        self.max_events_to_analyze = self.config.get("max_events_to_analyze", 1000)

        # Pattern matching cache
        self._pattern_cache: dict[str, list[tuple[str, str]]] = {}

        # ML feature extractors
        self._feature_extractors = {
            "temporal": self._extract_temporal_features,
            "behavioral": self._extract_behavioral_features,
            "content": self._extract_content_features,
            "network": self._extract_network_features,
        }

    async def analyze_threat_patterns(
        self, events: list[SecurityAuditEvent], time_window_hours: int = 24
    ) -> list[ThreatPattern]:
        """
        Analyze security events to identify threat patterns.

        Args:
            events: List of security events to analyze
            time_window_hours: Time window for pattern analysis

        Returns:
            List of identified threat patterns
        """
        start_time = datetime.now(timezone.utc)

        try:
            # Record analysis attempt
            self.metrics.increment_counter(
                "threat_analysis_attempts_total", labels={"window_hours": str(time_window_hours)}
            )

            # Filter events by time window
            cutoff_time = start_time - timedelta(hours=time_window_hours)
            filtered_events = [event for event in events if event.timestamp >= cutoff_time]

            logger.info(f"Analyzing {len(filtered_events)} events for threat patterns")

            # Extract patterns using multiple analysis techniques
            patterns = []

            # 1. Signature-based pattern detection
            signature_patterns = await self._detect_signature_patterns(filtered_events)
            patterns.extend(signature_patterns)

            # 2. Anomaly-based pattern detection
            anomaly_patterns = await self._detect_anomaly_patterns(filtered_events)
            patterns.extend(anomaly_patterns)

            # 3. Behavioral analysis patterns
            behavioral_patterns = await self._detect_behavioral_patterns(filtered_events)
            patterns.extend(behavioral_patterns)

            # 4. Correlation analysis patterns
            correlation_patterns = await self._detect_correlation_patterns(filtered_events)
            patterns.extend(correlation_patterns)

            # Filter by confidence threshold
            high_confidence_patterns = [
                pattern for pattern in patterns if pattern.confidence >= self.confidence_threshold
            ]

            # Record analysis metrics
            analysis_duration = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.metrics.observe_histogram(
                "threat_analysis_duration_seconds",
                analysis_duration,
                labels={"pattern_count": str(len(high_confidence_patterns))},
            )

            self.metrics.increment_counter(
                "threat_patterns_detected_total",
                labels={"analysis_type": "comprehensive"},
                value=len(high_confidence_patterns),
            )

            # Update threat level gauge
            max_severity = max(
                (
                    self._severity_to_numeric(pattern.severity)
                    for pattern in high_confidence_patterns
                ),
                default=0,
            )
            self.metrics.set_gauge("threat_level_gauge", max_severity)

            logger.info(
                f"Threat analysis completed: {len(high_confidence_patterns)} patterns detected "
                f"from {len(filtered_events)} events in {analysis_duration:.2f}s"
            )

            return high_confidence_patterns

        except Exception as e:
            # Record analysis error
            self.metrics.increment_counter(
                "threat_analysis_errors_total", labels={"error_type": type(e).__name__}
            )

            logger.error(f"Threat pattern analysis failed: {e}")
            return []

    async def calculate_risk_score(
        self, patterns: list[ThreatPattern], context: dict[str, Any]
    ) -> float:
        """
        Calculate overall risk score based on detected threat patterns.

        Args:
            patterns: List of threat patterns
            context: Additional context for risk calculation

        Returns:
            Risk score between 0.0 and 1.0
        """
        try:
            if not patterns:
                return 0.0

            # Base score calculation
            total_score = 0.0
            total_weight = 0.0

            for pattern in patterns:
                # Pattern weight based on severity and confidence
                severity_weight = self._severity_to_numeric(pattern.severity)
                confidence_weight = pattern.confidence
                pattern_weight = severity_weight * confidence_weight

                # Pattern score based on frequency and recency
                frequency_factor = min(1.0, pattern.frequency / 100.0)  # Cap at 100
                recency_hours = (
                    datetime.now(timezone.utc) - pattern.last_seen
                ).total_seconds() / 3600
                recency_factor = max(0.1, 1.0 - (recency_hours / 24.0))  # Decay over 24 hours

                pattern_score = pattern_weight * frequency_factor * recency_factor

                total_score += pattern_score
                total_weight += pattern_weight

            # Normalize by total weight
            base_risk = total_score / total_weight if total_weight > 0 else 0.0

            # Apply context modifiers
            context_modifier = self._calculate_context_modifier(context)
            final_risk = min(1.0, base_risk * context_modifier)

            # Record risk score
            self.metrics.set_gauge(
                "calculated_risk_score", final_risk, labels={"pattern_count": str(len(patterns))}
            )

            logger.debug(f"Risk score calculated: {final_risk:.3f} from {len(patterns)} patterns")

            return final_risk

        except Exception as e:
            logger.error(f"Risk score calculation failed: {e}")
            return 0.0

    async def get_threat_indicators(self, threat_type: ThreatCategory) -> list[dict[str, Any]]:
        """
        Get threat indicators for a specific threat type.

        Args:
            threat_type: Type of threat to get indicators for

        Returns:
            List of threat indicators
        """
        try:
            indicators = []

            # Get patterns from threat pattern definitions
            if threat_type in self.threat_patterns:
                patterns = self.threat_patterns[threat_type]

                for pattern in patterns:
                    indicators.append(
                        {
                            "type": "regex",
                            "pattern": pattern,
                            "threat_category": threat_type.value,
                            "confidence": 0.8,
                            "description": f"Pattern indicating {threat_type.value}",
                            "mitigation": self._get_threat_mitigation(threat_type),
                        }
                    )

            # Add ML-based indicators
            ml_indicators = await self._get_ml_threat_indicators(threat_type)
            indicators.extend(ml_indicators)

            # Add network-based indicators
            network_indicators = await self._get_network_threat_indicators(threat_type)
            indicators.extend(network_indicators)

            logger.debug(f"Retrieved {len(indicators)} indicators for {threat_type.value}")

            return indicators

        except Exception as e:
            logger.error(f"Failed to get threat indicators for {threat_type.value}: {e}")
            return []

    def _initialize_threat_patterns(self):
        """Initialize threat detection patterns."""
        self.threat_patterns = {
            ThreatCategory.INJECTION_ATTACK: [
                r"(?i)(union\s+select|select\s+.*\s+from|drop\s+table)",
                r"(?i)(or\s+1\s*=\s*1|'.*'.*=.*'.*')",
                r"(?i)(;.*drop|;.*delete|;.*insert|;.*update)",
                r"(?i)(<script.*?>|javascript:|vbscript:|onload=)",
                r"(?i)(\.\.\/|\.\.\\|path\s*=|file\s*=)",
            ],
            ThreatCategory.BRUTE_FORCE: [
                r"(?i)(multiple.*login.*attempts|repeated.*authentication)",
                r"(?i)(password.*brute|dictionary.*attack)",
                r"(?i)(403.*forbidden.*repeated|401.*unauthorized.*multiple)",
            ],
            ThreatCategory.DATA_EXFILTRATION: [
                r"(?i)(bulk.*download|mass.*export|large.*query)",
                r"(?i)(select\s+\*\s+from.*users|dump.*database)",
                r"(?i)(backup.*download|export.*sensitive)",
            ],
            ThreatCategory.PRIVILEGE_ESCALATION: [
                r"(?i)(admin.*access|root.*privilege|sudo|su\s+)",
                r"(?i)(elevate.*privilege|escalate.*permission)",
                r"(?i)(\/admin\/|\/management\/|\/superuser\/)",
            ],
            ThreatCategory.MALWARE: [
                r"(?i)(virus.*detected|malware.*found|trojan.*identified)",
                r"(?i)(suspicious.*executable|unknown.*binary)",
                r"(?i)(backdoor.*installed|rootkit.*detected)",
            ],
        }

    async def _detect_signature_patterns(
        self, events: list[SecurityAuditEvent]
    ) -> list[ThreatPattern]:
        """Detect threat patterns using signature matching."""
        patterns = []
        pattern_matches = defaultdict(list)

        try:
            for event in events:
                # Extract searchable content from event
                content = self._extract_event_content(event)

                # Check against all threat patterns
                for threat_type, regex_patterns in self.threat_patterns.items():
                    for regex_pattern in regex_patterns:
                        if re.search(regex_pattern, content, re.IGNORECASE):
                            pattern_matches[threat_type].append(
                                {
                                    "event": event,
                                    "pattern": regex_pattern,
                                    "content": content[:200],  # Truncate for storage
                                }
                            )

            # Create ThreatPattern objects from matches
            for threat_type, matches in pattern_matches.items():
                if matches:
                    # Calculate pattern metrics
                    frequency = len(matches)
                    confidence = min(
                        0.95, 0.7 + (frequency * 0.05)
                    )  # Confidence increases with frequency

                    # Determine severity based on threat type and frequency
                    severity = self._determine_pattern_severity(threat_type, frequency)

                    # Get latest and earliest timestamps
                    timestamps = [match["event"].timestamp for match in matches]
                    first_seen = min(timestamps)
                    last_seen = max(timestamps)

                    pattern = ThreatPattern(
                        pattern_id=f"sig_{threat_type.value}_{int(last_seen.timestamp())}",
                        threat_category=threat_type,
                        pattern_description=f"Signature-based detection of {threat_type.value}",
                        confidence=confidence,
                        severity=severity,
                        frequency=frequency,
                        first_seen=first_seen,
                        last_seen=last_seen,
                        indicators=[match["pattern"] for match in matches[:5]],  # Top 5 patterns
                        affected_resources=[match["event"].resource for match in matches],
                        recommended_actions=self._get_threat_recommendations(threat_type),
                    )

                    patterns.append(pattern)

            logger.debug(f"Detected {len(patterns)} signature-based threat patterns")
            return patterns

        except Exception as e:
            logger.error(f"Signature pattern detection failed: {e}")
            return []

    async def _detect_anomaly_patterns(
        self, events: list[SecurityAuditEvent]
    ) -> list[ThreatPattern]:
        """Detect threat patterns using anomaly detection."""
        patterns = []

        try:
            # Group events by various dimensions for anomaly detection

            # 1. Temporal anomalies
            temporal_anomalies = await self._detect_temporal_anomalies(events)
            patterns.extend(temporal_anomalies)

            # 2. Volume anomalies
            volume_anomalies = await self._detect_volume_anomalies(events)
            patterns.extend(volume_anomalies)

            # 3. User behavior anomalies
            behavior_anomalies = await self._detect_user_behavior_anomalies(events)
            patterns.extend(behavior_anomalies)

            logger.debug(f"Detected {len(patterns)} anomaly-based threat patterns")
            return patterns

        except Exception as e:
            logger.error(f"Anomaly pattern detection failed: {e}")
            return []

    async def _detect_behavioral_patterns(
        self, events: list[SecurityAuditEvent]
    ) -> list[ThreatPattern]:
        """Detect behavioral threat patterns."""
        patterns = []

        try:
            # Group events by user/source for behavioral analysis
            user_events = defaultdict(list)

            for event in events:
                user_key = event.user_id or event.source_ip or "unknown"
                user_events[user_key].append(event)

            # Analyze each user's behavior
            for _user_key, user_event_list in user_events.items():
                if len(user_event_list) < 5:  # Need sufficient events for pattern
                    continue

                # Look for suspicious behavioral patterns

                # 1. Rapid succession of different event types
                rapid_patterns = self._detect_rapid_event_succession(user_event_list)
                patterns.extend(rapid_patterns)

                # 2. Unusual access patterns
                access_patterns = self._detect_unusual_access_patterns(user_event_list)
                patterns.extend(access_patterns)

                # 3. Privilege escalation attempts
                escalation_patterns = self._detect_escalation_attempts(user_event_list)
                patterns.extend(escalation_patterns)

            logger.debug(f"Detected {len(patterns)} behavioral threat patterns")
            return patterns

        except Exception as e:
            logger.error(f"Behavioral pattern detection failed: {e}")
            return []

    async def _detect_correlation_patterns(
        self, events: list[SecurityAuditEvent]
    ) -> list[ThreatPattern]:
        """Detect correlated threat patterns across multiple events."""
        patterns = []

        try:
            # Time-based correlation windows
            correlation_windows = [300, 900, 3600]  # 5min, 15min, 1hour

            for window_seconds in correlation_windows:
                window_patterns = await self._detect_time_correlated_patterns(
                    events, window_seconds
                )
                patterns.extend(window_patterns)

            # Cross-service correlation
            cross_service_patterns = await self._detect_cross_service_patterns(events)
            patterns.extend(cross_service_patterns)

            logger.debug(f"Detected {len(patterns)} correlation-based threat patterns")
            return patterns

        except Exception as e:
            logger.error(f"Correlation pattern detection failed: {e}")
            return []

    def _extract_event_content(self, event: SecurityAuditEvent) -> str:
        """Extract searchable content from security event."""
        content_parts = [
            str(event.event_type.value),
            str(event.message),
            str(event.details),
            str(event.resource or ""),
            str(event.action or ""),
        ]
        return " ".join(filter(None, content_parts))

    def _determine_pattern_severity(
        self, threat_type: ThreatCategory, frequency: int
    ) -> SecurityEventSeverity:
        """Determine pattern severity based on threat type and frequency."""
        # High-impact threats
        if threat_type in [
            ThreatCategory.DATA_EXFILTRATION,
            ThreatCategory.PRIVILEGE_ESCALATION,
            ThreatCategory.MALWARE,
        ]:
            return SecurityEventSeverity.CRITICAL if frequency > 5 else SecurityEventSeverity.HIGH

        # Medium-impact threats
        elif threat_type in [ThreatCategory.INJECTION_ATTACK]:
            return SecurityEventSeverity.HIGH if frequency > 10 else SecurityEventSeverity.MEDIUM

        # Lower-impact but volume-sensitive threats
        elif threat_type in [ThreatCategory.BRUTE_FORCE]:
            if frequency > 20:
                return SecurityEventSeverity.HIGH
            elif frequency > 5:
                return SecurityEventSeverity.MEDIUM
            else:
                return SecurityEventSeverity.LOW

        return SecurityEventSeverity.MEDIUM

    def _severity_to_numeric(self, severity: SecurityEventSeverity) -> float:
        """Convert severity to numeric value for calculations."""
        severity_map = {
            SecurityEventSeverity.CRITICAL: 1.0,
            SecurityEventSeverity.HIGH: 0.8,
            SecurityEventSeverity.MEDIUM: 0.6,
            SecurityEventSeverity.LOW: 0.4,
            SecurityEventSeverity.INFO: 0.2,
        }
        return severity_map.get(severity, 0.5)

    def _calculate_context_modifier(self, context: dict[str, Any]) -> float:
        """Calculate context modifier for risk score."""
        modifier = 1.0

        # System criticality
        if context.get("system_criticality") == "high":
            modifier += 0.3
        elif context.get("system_criticality") == "low":
            modifier -= 0.2

        # Time of day (higher risk during off-hours)
        current_hour = datetime.now().hour
        if current_hour < 6 or current_hour > 22:  # Off-hours
            modifier += 0.2

        # Network context
        if context.get("external_network", False):
            modifier += 0.3

        # User privilege level
        if context.get("user_privilege") == "admin":
            modifier += 0.4

        return max(0.5, min(2.0, modifier))  # Clamp between 0.5 and 2.0

    def _get_threat_mitigation(self, threat_type: ThreatCategory) -> list[str]:
        """Get mitigation recommendations for threat type."""
        mitigations = {
            ThreatCategory.INJECTION_ATTACK: [
                "Implement input validation and sanitization",
                "Use parameterized queries",
                "Apply principle of least privilege",
                "Deploy Web Application Firewall (WAF)",
            ],
            ThreatCategory.BRUTE_FORCE: [
                "Implement account lockout policies",
                "Enable multi-factor authentication",
                "Use CAPTCHA for repeated attempts",
                "Monitor and alert on failed login patterns",
            ],
            ThreatCategory.DATA_EXFILTRATION: [
                "Implement data loss prevention (DLP)",
                "Monitor unusual data access patterns",
                "Encrypt sensitive data at rest and in transit",
                "Apply access controls and audit trails",
            ],
            ThreatCategory.PRIVILEGE_ESCALATION: [
                "Regular privilege audits and reviews",
                "Implement principle of least privilege",
                "Monitor admin account activities",
                "Use privileged access management (PAM)",
            ],
            ThreatCategory.MALWARE: [
                "Deploy endpoint detection and response (EDR)",
                "Keep systems and software updated",
                "Implement application whitelisting",
                "Regular security scanning and monitoring",
            ],
        }

        return mitigations.get(
            threat_type,
            [
                "Monitor system activities closely",
                "Review and update security policies",
                "Investigate suspicious activities",
                "Contact security team for analysis",
            ],
        )

    def _get_threat_recommendations(self, threat_type: ThreatCategory) -> list[str]:
        """Get action recommendations for threat type."""
        return [
            f"Investigate {threat_type.value} indicators immediately",
            "Review affected systems and users",
            "Apply appropriate security controls",
            "Monitor for continued suspicious activity",
        ]

    # Placeholder methods for advanced pattern detection
    # These would be implemented with more sophisticated ML algorithms

    async def _detect_temporal_anomalies(
        self, events: list[SecurityAuditEvent]
    ) -> list[ThreatPattern]:
        """Detect temporal anomalies in event patterns."""
        # Implementation would use time series analysis
        return []

    async def _detect_volume_anomalies(
        self, events: list[SecurityAuditEvent]
    ) -> list[ThreatPattern]:
        """Detect volume-based anomalies."""
        # Implementation would use statistical analysis
        return []

    async def _detect_user_behavior_anomalies(
        self, events: list[SecurityAuditEvent]
    ) -> list[ThreatPattern]:
        """Detect user behavior anomalies."""
        # Implementation would use behavioral modeling
        return []

    def _detect_rapid_event_succession(
        self, events: list[SecurityAuditEvent]
    ) -> list[ThreatPattern]:
        """Detect rapid succession of events."""
        # Implementation would analyze event timing
        return []

    def _detect_unusual_access_patterns(
        self, events: list[SecurityAuditEvent]
    ) -> list[ThreatPattern]:
        """Detect unusual access patterns."""
        # Implementation would analyze access patterns
        return []

    def _detect_escalation_attempts(self, events: list[SecurityAuditEvent]) -> list[ThreatPattern]:
        """Detect privilege escalation attempts."""
        # Implementation would analyze privilege changes
        return []

    async def _detect_time_correlated_patterns(
        self, events: list[SecurityAuditEvent], window_seconds: int
    ) -> list[ThreatPattern]:
        """Detect time-correlated patterns."""
        # Implementation would use correlation analysis
        return []

    async def _detect_cross_service_patterns(
        self, events: list[SecurityAuditEvent]
    ) -> list[ThreatPattern]:
        """Detect cross-service attack patterns."""
        # Implementation would analyze multi-service attacks
        return []

    async def _get_ml_threat_indicators(self, threat_type: ThreatCategory) -> list[dict[str, Any]]:
        """Get ML-based threat indicators."""
        # Implementation would integrate with ML models
        return []

    async def _get_network_threat_indicators(
        self, threat_type: ThreatCategory
    ) -> list[dict[str, Any]]:
        """Get network-based threat indicators."""
        # Implementation would integrate with network monitoring
        return []

    def _extract_temporal_features(self, events: list[SecurityAuditEvent]) -> dict[str, float]:
        """Extract temporal features from events."""
        # Implementation would extract time-based features
        return {}

    def _extract_behavioral_features(self, events: list[SecurityAuditEvent]) -> dict[str, float]:
        """Extract behavioral features from events."""
        # Implementation would extract behavior-based features
        return {}

    def _extract_content_features(self, events: list[SecurityAuditEvent]) -> dict[str, float]:
        """Extract content-based features from events."""
        # Implementation would extract content features
        return {}

    def _extract_network_features(self, events: list[SecurityAuditEvent]) -> dict[str, float]:
        """Extract network-based features from events."""
        # Implementation would extract network features
        return {}
