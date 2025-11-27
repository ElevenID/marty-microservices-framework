"""
Event Processor Adapter

Real-time security event processing adapter implementing IThreatDetector.
"""

import asyncio
import builtins
import logging
import re
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from prometheus_client import Counter, Histogram

from mmf_new.core.domain.audit_types import SecurityEventType, SecurityThreatLevel
from mmf_new.core.security.domain.config import ThreatDetectionConfig
from mmf_new.core.security.domain.models.threat import (
    AnomalyDetectionResult,
    SecurityEvent,
    ServiceBehaviorProfile,
    ThreatDetectionResult,
    UserBehaviorProfile,
)
from mmf_new.core.security.ports.threat_detection import IThreatDetector

logger = logging.getLogger(__name__)


@dataclass
class SecurityEventFilter:
    """Security event filter configuration."""

    name: str
    service_patterns: builtins.list[str] | None = None
    event_types: builtins.list[str] | None = None
    severity_levels: builtins.list[str] | None = None
    source_ip_patterns: builtins.list[str] | None = None
    user_patterns: builtins.list[str] | None = None
    enabled: bool = True


@dataclass
class SecurityEventRule:
    """Security event processing rule."""

    rule_id: str
    name: str
    description: str
    conditions: builtins.dict[str, Any]
    actions: builtins.list[str]
    severity: str
    category: str
    enabled: bool = True
    priority: int = 1


class EventProcessorThreatDetector(IThreatDetector):
    """
    Real-time security event processing engine.

    Features:
    - High-throughput event processing
    - Real-time filtering and enrichment
    - Rule-based analysis
    - Threat scoring
    """

    def __init__(self, config: ThreatDetectionConfig):
        self.config = config
        self.processing_queue: asyncio.Queue = asyncio.Queue(maxsize=50000)
        self.processed_events: deque = deque(maxlen=10000)

        # Event filters and rules
        self.filters: builtins.dict[str, SecurityEventFilter] = {}
        self.rules: builtins.dict[str, SecurityEventRule] = {}

        # Event processors and enrichers
        self.processors: builtins.list[Callable] = []
        self.enrichers: builtins.list[Callable] = []

        # Processing metrics
        self.events_received = 0
        self.events_processed = 0
        self.events_filtered = 0
        self.processing_errors = 0

        # Rate limiting (in-memory for now, should use cache backend)
        self.rate_limiter = defaultdict(lambda: deque(maxlen=1000))

        # Initialize default filters and rules
        self._initialize_default_config()

        # Metrics
        self.event_ingestion_rate = Counter(
            "mmf_security_threat_events_total",
            "Security events ingested",
            ["service", "event_type", "severity"],
        )
        self.event_processing_time = Histogram(
            "mmf_security_threat_processing_seconds",
            "Security event processing time",
        )
        self.threat_score_distribution = Histogram(
            "mmf_security_threat_score_distribution",
            "Security threat scores",
            buckets=[0.1, 0.3, 0.5, 0.7, 0.9, 1.0],
        )

    def _initialize_default_config(self):
        """Initialize default filters and rules."""
        # Default filters
        self.add_filter(
            SecurityEventFilter(
                name="high_severity_filter",
                severity_levels=["high", "critical"],
            )
        )

        self.add_filter(
            SecurityEventFilter(
                name="authentication_filter",
                event_types=[
                    "authentication_failure",
                    "authentication_success",
                    "password_change",
                ],
            )
        )

        # Default rules
        self.add_rule(
            SecurityEventRule(
                rule_id="multiple_auth_failures",
                name="Multiple Authentication Failures",
                description="Detect multiple authentication failures from same source",
                conditions={
                    "event_type": "authentication_failure",
                    "time_window": 300,
                    "count_threshold": 5,
                },
                actions=["create_incident", "block_ip"],
                severity="high",
                category="brute_force",
            )
        )

        self.add_rule(
            SecurityEventRule(
                rule_id="injection_attack",
                name="Injection Attack",
                description="Detect SQL/Command injection attempts",
                conditions={
                    "request_patterns": [
                        r"(\bUNION\b|\bSELECT\b|\bINSERT\b|\bDELETE\b|\bDROP\b)",
                        r"(\<script\>|\<\/script\>)",
                        r"(\.\.\/|\.\.\\)",
                    ]
                },
                actions=["block_request", "alert_security_team"],
                severity="high",
                category="injection",
            )
        )

    def add_filter(self, filter_config: SecurityEventFilter):
        """Add event filter."""
        self.filters[filter_config.name] = filter_config

    def add_rule(self, rule: SecurityEventRule):
        """Add processing rule."""
        self.rules[rule.rule_id] = rule

    async def analyze_event(self, event: SecurityEvent) -> ThreatDetectionResult:
        """Analyze a security event for threats."""
        start_time = time.time()

        # 1. Apply filters
        if not self._apply_filters(event):
            self.events_filtered += 1
            return ThreatDetectionResult(
                event=event,
                is_threat=False,
                threat_score=0.0,
                threat_level=SecurityThreatLevel.LOW,
                analyzed_at=datetime.now(timezone.utc),
            )

        # 2. Enrich event
        enrichments = await self._enrich_event(event)
        event.metadata.update(enrichments)

        # 3. Apply rules
        triggered_rules, recommended_actions = await self._apply_rules(event)

        # 4. Calculate threat score
        threat_score = self._calculate_threat_score(event, triggered_rules, enrichments)

        # Determine threat level based on score
        if threat_score >= 0.9:
            threat_level = SecurityThreatLevel.CRITICAL
        elif threat_score >= 0.7:
            threat_level = SecurityThreatLevel.HIGH
        elif threat_score >= 0.4:
            threat_level = SecurityThreatLevel.MEDIUM
        else:
            threat_level = SecurityThreatLevel.LOW

        is_threat = threat_score >= 0.5

        result = ThreatDetectionResult(
            event=event,
            is_threat=is_threat,
            threat_score=threat_score,
            threat_level=threat_level,
            detected_threats=[r.name for r in triggered_rules],
            risk_factors=[f"Rule: {r.name}" for r in triggered_rules],
            recommended_actions=recommended_actions,
            analyzed_at=datetime.now(timezone.utc),
        )

        # Update metrics
        self.events_processed += 1
        self.event_processing_time.observe(time.time() - start_time)
        self.threat_score_distribution.observe(threat_score)

        # Add to history
        self.processed_events.append(result)

        return result

    async def analyze_user_behavior(
        self, user_id: str, recent_events: builtins.list[SecurityEvent]
    ) -> UserBehaviorProfile:
        """Analyze user behavior (Placeholder for EventProcessor)."""
        # EventProcessor focuses on single-event analysis.
        # MLAnalyzer handles behavioral profiling.
        return UserBehaviorProfile(user_id=user_id)

    async def analyze_service_behavior(
        self, service_name: str, recent_events: builtins.list[SecurityEvent]
    ) -> ServiceBehaviorProfile:
        """Analyze service behavior (Placeholder for EventProcessor)."""
        return ServiceBehaviorProfile(service_name=service_name)

    async def detect_anomalies(self, data: builtins.dict[str, Any]) -> AnomalyDetectionResult:
        """Detect anomalies (Placeholder for EventProcessor)."""
        return AnomalyDetectionResult(is_anomaly=False, anomaly_score=0.0, confidence=0.0)

    async def get_threat_statistics(self) -> builtins.dict[str, Any]:
        """Get threat detection statistics."""
        return {
            "events_received": self.events_received,
            "events_processed": self.events_processed,
            "events_filtered": self.events_filtered,
            "processing_errors": self.processing_errors,
            "queue_size": self.processing_queue.qsize(),
        }

    # --- Internal Methods ---

    def _apply_filters(self, event: SecurityEvent) -> bool:
        """Apply event filters."""
        for filter_config in self.filters.values():
            if not filter_config.enabled:
                continue

            # Check service patterns
            if filter_config.service_patterns:
                if not any(
                    self._match_pattern(p, event.service_name)
                    for p in filter_config.service_patterns
                ):
                    continue

            # Check event types
            if filter_config.event_types:
                if str(event.event_type) not in filter_config.event_types:
                    continue

            # Check severity
            if filter_config.severity_levels:
                if event.severity.value not in filter_config.severity_levels:
                    continue

            return True
        return True

    def _match_pattern(self, pattern: str, text: str) -> bool:
        """Match pattern against text."""
        if "*" in pattern:
            regex = pattern.replace("*", ".*")
            return bool(re.match(regex, text, re.IGNORECASE))
        return pattern.lower() in text.lower()

    async def _enrich_event(self, event: SecurityEvent) -> builtins.dict[str, Any]:
        """Enrich event with context."""
        enrichments = {}

        # Mock Geo IP
        if event.source_ip:
            enrichments["geo_location"] = {
                "country": "US" if event.source_ip.startswith("192.168") else "Unknown",
                "is_internal": event.source_ip.startswith(("192.168", "10.", "172.")),
            }

        # Request Analysis
        if "request_body" in event.details:
            enrichments["request_analysis"] = self._analyze_request(
                str(event.details["request_body"])
            )

        return enrichments

    def _analyze_request(self, request_body: str) -> builtins.dict[str, Any]:
        """Analyze request body for patterns."""
        analysis = {"suspicious_patterns": []}

        sql_patterns = [r"(\bUNION\b|\bSELECT\b|\bINSERT\b)", r"(\'|\";|--;)"]
        for p in sql_patterns:
            if re.search(p, request_body, re.IGNORECASE):
                analysis["suspicious_patterns"].append("sql_injection")
                break

        return analysis

    async def _apply_rules(
        self, event: SecurityEvent
    ) -> tuple[builtins.list[SecurityEventRule], builtins.list[str]]:
        """Apply rules to event."""
        triggered = []
        actions = []

        for rule in self.rules.values():
            if not rule.enabled:
                continue

            if await self._evaluate_rule(rule, event):
                triggered.append(rule)
                actions.extend(rule.actions)

        return triggered, list(set(actions))

    async def _evaluate_rule(self, rule: SecurityEventRule, event: SecurityEvent) -> bool:
        """Evaluate single rule."""
        conditions = rule.conditions

        if "event_type" in conditions:
            if str(event.event_type) != conditions["event_type"]:
                return False

        if "request_patterns" in conditions and "request_body" in event.details:
            body = str(event.details["request_body"])
            for p in conditions["request_patterns"]:
                if re.search(p, body, re.IGNORECASE):
                    return True
            return False

        return True

    def _calculate_threat_score(
        self,
        event: SecurityEvent,
        triggered_rules: builtins.list[SecurityEventRule],
        enrichments: builtins.dict[str, Any],
    ) -> float:
        """Calculate threat score."""
        score = 0.0

        # Base severity
        severity_scores = {
            SecurityThreatLevel.LOW: 0.2,
            SecurityThreatLevel.MEDIUM: 0.5,
            SecurityThreatLevel.HIGH: 0.8,
            SecurityThreatLevel.CRITICAL: 1.0,
        }
        score += severity_scores.get(event.severity, 0.2)

        # Rules
        score += len(triggered_rules) * 0.1

        # Enrichments
        if "request_analysis" in enrichments:
            if enrichments["request_analysis"].get("suspicious_patterns"):
                score += 0.2

        return min(score, 1.0)

    async def process_events(self):
        """Background task to process events from queue."""
        while True:
            try:
                event = await self.processing_queue.get()
                await self.analyze_event(event)
                self.processing_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error processing event: {e}")
                self.processing_errors += 1
