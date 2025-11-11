"""
Real-time Security Event Processing for Marty Microservices Framework

Provides real-time processing and analysis of security events including:
- High-throughput event ingestion
- Stream processing and filtering
- Real-time threat correlation
- Event enrichment and normalization
- Security alerting and notifications
"""

import asyncio
import builtins
import re
import time
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, list

import aiohttp
import redis.asyncio as redis
from prometheus_client import Counter, Gauge, Histogram

# External dependencies
try:
    REDIS_AVAILABLE = True

    STREAMING_AVAILABLE = True
except ImportError:
    STREAMING_AVAILABLE = False
    REDIS_AVAILABLE = False


@dataclass
class SecurityEventFilter:
    """Security event filter configuration"""

    name: str
    service_patterns: builtins.list[str] = None
    event_types: builtins.list[str] = None
    severity_levels: builtins.list[str] = None
    source_ip_patterns: builtins.list[str] = None
    user_patterns: builtins.list[str] = None
    enabled: bool = True


@dataclass
class SecurityEventRule:
    """Security event processing rule"""

    rule_id: str
    name: str
    description: str
    conditions: builtins.dict[str, Any]
    actions: builtins.list[str]
    severity: str
    category: str
    enabled: bool = True
    priority: int = 1


@dataclass
class ProcessedSecurityEvent:
    """Processed and enriched security event"""

    original_event: builtins.dict[str, Any]
    processed_at: datetime
    enrichments: builtins.dict[str, Any]
    threat_score: float
    risk_factors: builtins.list[str]
    correlated_events: builtins.list[str]
    triggered_rules: builtins.list[str]
    recommended_actions: builtins.list[str]


class SecurityEventProcessor:
    """
    Real-time security event processing engine

    Features:
    - High-throughput event processing
    - Real-time filtering and enrichment
    - Rule-based analysis
    - Threat scoring
    - Event correlation
    """

    def __init__(self, max_events_per_second: int = 10000):
        self.max_events_per_second = max_events_per_second
        self.processing_queue: asyncio.Queue = asyncio.Queue(maxsize=50000)
        self.processed_events: deque = deque(maxlen=100000)

        # Event filters and rules
        self.filters: builtins.dict[str, SecurityEventFilter] = {}
        self.rules: builtins.dict[str, SecurityEventRule] = {}

        # Event processors
        self.processors: builtins.list[Callable] = []
        self.enrichers: builtins.list[Callable] = []

        # Processing metrics
        self.events_received = 0
        self.events_processed = 0
        self.events_filtered = 0
        self.processing_errors = 0

        # Rate limiting
        self.rate_limiter = defaultdict(lambda: deque(maxlen=1000))

        # Initialize default filters and rules
        self._initialize_default_config()

        # Metrics
        if STREAMING_AVAILABLE:
            self.event_ingestion_rate = Counter(
                "marty_security_event_ingestion_total",
                "Security events ingested",
                ["service", "event_type", "severity"],
            )
            self.event_processing_time = Histogram(
                "marty_security_event_processing_seconds",
                "Security event processing time",
            )
            self.threat_score_distribution = Histogram(
                "marty_security_threat_score",
                "Security threat scores",
                buckets=[0.1, 0.3, 0.5, 0.7, 0.9, 1.0],
            )

    def _initialize_default_config(self):
        """Initialize default filters and rules"""

        # Default filters
        self.add_filter(
            SecurityEventFilter(
                name="high_severity_filter",
                severity_levels=["high", "critical"],
                description="Filter for high severity events",
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
                description="Filter for authentication events",
            )
        )

        self.add_filter(
            SecurityEventFilter(
                name="admin_access_filter",
                service_patterns=["*admin*", "*management*"],
                description="Filter for administrative access",
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
                    "time_window": 300,  # 5 minutes
                    "count_threshold": 5,
                    "group_by": "source_ip",
                },
                actions=["create_incident", "block_ip", "alert_security_team"],
                severity="high",
                category="brute_force",
            )
        )

        self.add_rule(
            SecurityEventRule(
                rule_id="admin_access_anomaly",
                name="Unusual Administrative Access",
                description="Detect unusual administrative access patterns",
                conditions={
                    "endpoint_patterns": ["/admin/*", "/management/*"],
                    "time_window": 3600,  # 1 hour
                    "unique_users_threshold": 10,
                },
                actions=[
                    "create_incident",
                    "alert_security_team",
                    "increase_monitoring",
                ],
                severity="medium",
                category="privilege_escalation",
            )
        )

        self.add_rule(
            SecurityEventRule(
                rule_id="data_exfiltration_pattern",
                name="Potential Data Exfiltration",
                description="Detect patterns indicating data exfiltration",
                conditions={
                    "response_size_threshold": 10485760,  # 10MB
                    "time_window": 600,  # 10 minutes
                    "count_threshold": 5,
                },
                actions=["create_incident", "alert_security_team", "throttle_user"],
                severity="critical",
                category="data_exfiltration",
            )
        )

        self.add_rule(
            SecurityEventRule(
                rule_id="injection_attack_detection",
                name="Injection Attack Detection",
                description="Detect SQL injection and other injection attempts",
                conditions={
                    "request_patterns": [
                        r"(\bUNION\b|\bSELECT\b|\bINSERT\b|\bDELETE\b|\bDROP\b)",
                        r"(\<script\>|\<\/script\>)",
                        r"(\.\.\/|\.\.\\)",
                        r"(\bOR\b.*\b1=1\b|\bAND\b.*\b1=1\b)",
                    ]
                },
                actions=["block_request", "create_incident", "alert_security_team"],
                severity="high",
                category="injection_attack",
            )
        )

    def add_filter(self, filter_config: SecurityEventFilter):
        """Add event filter"""
        self.filters[filter_config.name] = filter_config
        print(f"Added security event filter: {filter_config.name}")

    def add_rule(self, rule: SecurityEventRule):
        """Add processing rule"""
        self.rules[rule.rule_id] = rule
        print(f"Added security event rule: {rule.name}")

    def add_processor(self, processor: Callable):
        """Add custom event processor"""
        self.processors.append(processor)

    def add_enricher(self, enricher: Callable):
        """Add event enricher"""
        self.enrichers.append(enricher)

    async def ingest_event(self, event_data: builtins.dict[str, Any]) -> bool:
        """Ingest security event for processing"""

        try:
            # Rate limiting check
            source_ip = event_data.get("source_ip", "unknown")
            now = time.time()

            # Clean old entries
            cutoff = now - 60  # 1 minute window
            while self.rate_limiter[source_ip] and self.rate_limiter[source_ip][0] < cutoff:
                self.rate_limiter[source_ip].popleft()

            # Check rate limit (100 events per minute per IP)
            if len(self.rate_limiter[source_ip]) >= 100:
                print(f"Rate limit exceeded for {source_ip}")
                return False

            self.rate_limiter[source_ip].append(now)

            # Add to processing queue
            await self.processing_queue.put(event_data)
            self.events_received += 1

            # Update metrics
            if STREAMING_AVAILABLE:
                self.event_ingestion_rate.labels(
                    service=event_data.get("service_name", "unknown"),
                    event_type=event_data.get("event_type", "unknown"),
                    severity=event_data.get("severity", "unknown"),
                ).inc()

            return True

        except Exception as e:
            print(f"Error ingesting event: {e}")
            return False

    async def process_events(self):
        """Main event processing loop"""

        print("Starting security event processing...")

        while True:
            try:
                # Get event from queue with timeout
                event_data = await asyncio.wait_for(self.processing_queue.get(), timeout=1.0)

                start_time = time.time()

                # Process the event
                processed_event = await self._process_single_event(event_data)

                if processed_event:
                    self.processed_events.append(processed_event)
                    self.events_processed += 1

                    # Update processing time metric
                    if STREAMING_AVAILABLE:
                        processing_time = time.time() - start_time
                        self.event_processing_time.observe(processing_time)

                        # Update threat score distribution
                        self.threat_score_distribution.observe(processed_event.threat_score)

            except asyncio.TimeoutError:
                # No events to process, continue
                continue
            except Exception as e:
                print(f"Error processing event: {e}")
                self.processing_errors += 1

    async def _process_single_event(
        self, event_data: builtins.dict[str, Any]
    ) -> ProcessedSecurityEvent | None:
        """Process a single security event"""

        # Apply filters
        if not self._apply_filters(event_data):
            self.events_filtered += 1
            return None

        # Create processed event object
        processed_event = ProcessedSecurityEvent(
            original_event=event_data,
            processed_at=datetime.now(),
            enrichments={},
            threat_score=0.0,
            risk_factors=[],
            correlated_events=[],
            triggered_rules=[],
            recommended_actions=[],
        )

        # Enrich event
        await self._enrich_event(processed_event)

        # Apply processing rules
        await self._apply_rules(processed_event)

        # Calculate threat score
        processed_event.threat_score = self._calculate_threat_score(processed_event)

        # Run custom processors
        for processor in self.processors:
            try:
                await processor(processed_event)
            except Exception as e:
                print(f"Error in custom processor: {e}")

        return processed_event

    def _apply_filters(self, event_data: builtins.dict[str, Any]) -> bool:
        """Apply event filters to determine if event should be processed"""

        for _filter_name, filter_config in self.filters.items():
            if not filter_config.enabled:
                continue

            # Check service patterns
            if filter_config.service_patterns:
                service_name = event_data.get("service_name", "")
                if not any(
                    self._match_pattern(pattern, service_name)
                    for pattern in filter_config.service_patterns
                ):
                    continue

            # Check event types
            if filter_config.event_types:
                event_type = event_data.get("event_type", "")
                if event_type not in filter_config.event_types:
                    continue

            # Check severity levels
            if filter_config.severity_levels:
                severity = event_data.get("severity", "")
                if severity not in filter_config.severity_levels:
                    continue

            # Check source IP patterns
            if filter_config.source_ip_patterns:
                source_ip = event_data.get("source_ip", "")
                if not any(
                    self._match_pattern(pattern, source_ip)
                    for pattern in filter_config.source_ip_patterns
                ):
                    continue

            # Check user patterns
            if filter_config.user_patterns:
                user_id = event_data.get("user_id", "")
                if not any(
                    self._match_pattern(pattern, user_id) for pattern in filter_config.user_patterns
                ):
                    continue

            # Filter matched
            return True

        # No filters matched (or no filters defined), process the event
        return True

    def _match_pattern(self, pattern: str, text: str) -> bool:
        """Match pattern against text (supports wildcards)"""
        if "*" in pattern:
            # Convert wildcard pattern to regex
            regex_pattern = pattern.replace("*", ".*")
            return bool(re.match(regex_pattern, text, re.IGNORECASE))
        return pattern.lower() in text.lower()

    async def _enrich_event(self, processed_event: ProcessedSecurityEvent):
        """Enrich event with additional context"""

        event_data = processed_event.original_event
        enrichments = processed_event.enrichments

        # Geographic enrichment (mock)
        source_ip = event_data.get("source_ip", "")
        if source_ip:
            enrichments["geo_location"] = await self._get_geo_location(source_ip)

        # User context enrichment
        user_id = event_data.get("user_id", "")
        if user_id:
            enrichments["user_context"] = await self._get_user_context(user_id)

        # Service context enrichment
        service_name = event_data.get("service_name", "")
        if service_name:
            enrichments["service_context"] = await self._get_service_context(service_name)

        # Request analysis
        if "request_body" in event_data or "request_params" in event_data:
            enrichments["request_analysis"] = self._analyze_request(event_data)

        # Temporal analysis
        enrichments["temporal_analysis"] = self._analyze_temporal_patterns(event_data)

        # Run custom enrichers
        for enricher in self.enrichers:
            try:
                await enricher(processed_event)
            except Exception as e:
                print(f"Error in custom enricher: {e}")

    async def _get_geo_location(self, ip_address: str) -> builtins.dict[str, Any]:
        """Get geographic location for IP address (mock)"""
        # This would integrate with real geolocation service
        return {
            "country": "US" if ip_address.startswith("192.168") else "Unknown",
            "region": "Internal" if ip_address.startswith("192.168") else "External",
            "is_internal": ip_address.startswith(("192.168", "10.", "172.")),
            "risk_score": 0.1 if ip_address.startswith(("192.168", "10.", "172.")) else 0.5,
        }

    async def _get_user_context(self, user_id: str) -> builtins.dict[str, Any]:
        """Get user context information (mock)"""
        # This would integrate with user management system
        return {
            "user_type": "admin" if "admin" in user_id.lower() else "regular",
            "account_age_days": 365,  # Mock data
            "last_login": datetime.now() - timedelta(hours=2),
            "failed_login_count_24h": 1,
            "privilege_level": "high" if "admin" in user_id.lower() else "normal",
        }

    async def _get_service_context(self, service_name: str) -> builtins.dict[str, Any]:
        """Get service context information"""
        return {
            "service_tier": "critical"
            if any(x in service_name.lower() for x in ["payment", "auth", "user"])
            else "standard",
            "data_classification": "sensitive" if "payment" in service_name.lower() else "internal",
            "public_facing": "gateway" in service_name.lower() or "api" in service_name.lower(),
        }

    def _analyze_request(self, event_data: builtins.dict[str, Any]) -> builtins.dict[str, Any]:
        """Analyze request content for threats"""
        analysis = {
            "suspicious_patterns": [],
            "risk_indicators": [],
            "payload_analysis": {},
        }

        request_body = str(event_data.get("request_body", ""))
        request_params = str(event_data.get("request_params", ""))
        combined_request = f"{request_body} {request_params}".lower()

        # Check for SQL injection patterns
        sql_patterns = [
            r"(\bUNION\b|\bSELECT\b|\bINSERT\b|\bDELETE\b|\bDROP\b)",
            r"(\bOR\b.*\b1=1\b|\bAND\b.*\b1=1\b)",
            r"(\'|\";|--;)",
        ]

        for pattern in sql_patterns:
            if re.search(pattern, combined_request, re.IGNORECASE):
                analysis["suspicious_patterns"].append("sql_injection")
                analysis["risk_indicators"].append("SQL injection attempt detected")
                break

        # Check for XSS patterns
        xss_patterns = [
            r"(\<script\>|\<\/script\>)",
            r"(javascript:|onerror=|onload=)",
            r"(\<img.*onerror|\<body.*onload)",
        ]

        for pattern in xss_patterns:
            if re.search(pattern, combined_request, re.IGNORECASE):
                analysis["suspicious_patterns"].append("xss")
                analysis["risk_indicators"].append("XSS attempt detected")
                break

        # Check for path traversal
        if re.search(r"(\.\.\/|\.\.\\)", combined_request):
            analysis["suspicious_patterns"].append("path_traversal")
            analysis["risk_indicators"].append("Path traversal attempt detected")

        # Analyze payload size
        payload_size = len(combined_request)
        if payload_size > 10000:  # Large payload
            analysis["payload_analysis"]["size"] = "large"
            analysis["risk_indicators"].append("Unusually large payload")

        return analysis

    def _analyze_temporal_patterns(
        self, event_data: builtins.dict[str, Any]
    ) -> builtins.dict[str, Any]:
        """Analyze temporal patterns in events"""
        analysis = {
            "time_of_day": "business_hours",  # Mock analysis
            "day_of_week": "weekday",
            "frequency_analysis": {},
            "anomaly_indicators": [],
        }

        # Check if event occurs during off-hours
        current_hour = datetime.now().hour
        if current_hour < 6 or current_hour > 22:
            analysis["time_of_day"] = "off_hours"
            analysis["anomaly_indicators"].append("Off-hours activity")

        # Check day of week
        current_day = datetime.now().weekday()
        if current_day >= 5:  # Weekend
            analysis["day_of_week"] = "weekend"
            analysis["anomaly_indicators"].append("Weekend activity")

        return analysis

    async def _apply_rules(self, processed_event: ProcessedSecurityEvent):
        """Apply processing rules to event"""

        for rule_id, rule in self.rules.items():
            if not rule.enabled:
                continue

            try:
                if await self._evaluate_rule(rule, processed_event):
                    processed_event.triggered_rules.append(rule_id)
                    processed_event.recommended_actions.extend(rule.actions)

                    # Add rule-specific risk factors
                    processed_event.risk_factors.append(f"Rule triggered: {rule.name}")

                    print(
                        f"Rule triggered: {rule.name} for event {processed_event.original_event.get('event_id', 'unknown')}"
                    )

            except Exception as e:
                print(f"Error evaluating rule {rule_id}: {e}")

    async def _evaluate_rule(
        self, rule: SecurityEventRule, processed_event: ProcessedSecurityEvent
    ) -> bool:
        """Evaluate if rule conditions are met"""

        event_data = processed_event.original_event
        conditions = rule.conditions

        # Check event type condition
        if "event_type" in conditions:
            if event_data.get("event_type") != conditions["event_type"]:
                return False

        # Check endpoint patterns
        if "endpoint_patterns" in conditions:
            endpoint = event_data.get("endpoint", "")
            if not any(
                self._match_pattern(pattern, endpoint)
                for pattern in conditions["endpoint_patterns"]
            ):
                return False

        # Check request patterns
        if "request_patterns" in conditions:
            request_body = str(event_data.get("request_body", ""))
            request_params = str(event_data.get("request_params", ""))
            combined_request = f"{request_body} {request_params}"

            for pattern in conditions["request_patterns"]:
                if re.search(pattern, combined_request, re.IGNORECASE):
                    return True
            return False

        # Check response size threshold
        if "response_size_threshold" in conditions:
            response_size = event_data.get("response_size", 0)
            if response_size < conditions["response_size_threshold"]:
                return False

        # Time-based and count-based conditions would require correlation
        # with historical events (simplified for this example)

        return True

    def _calculate_threat_score(self, processed_event: ProcessedSecurityEvent) -> float:
        """Calculate overall threat score for event"""

        score = 0.0
        event_data = processed_event.original_event

        # Base score from severity
        severity_scores = {"low": 0.2, "medium": 0.5, "high": 0.8, "critical": 1.0}

        base_severity = event_data.get("severity", "low")
        score += severity_scores.get(base_severity, 0.2)

        # Add score for triggered rules
        score += len(processed_event.triggered_rules) * 0.1

        # Add score for suspicious patterns
        enrichments = processed_event.enrichments
        if "request_analysis" in enrichments:
            request_analysis = enrichments["request_analysis"]
            score += len(request_analysis.get("suspicious_patterns", [])) * 0.2

        # Add score for geographic risk
        if "geo_location" in enrichments:
            geo_location = enrichments["geo_location"]
            score += geo_location.get("risk_score", 0.0)

        # Add score for user context
        if "user_context" in enrichments:
            user_context = enrichments["user_context"]
            if user_context.get("user_type") == "admin":
                score += 0.1  # Admin activities are higher risk

        # Add score for temporal anomalies
        if "temporal_analysis" in enrichments:
            temporal_analysis = enrichments["temporal_analysis"]
            score += len(temporal_analysis.get("anomaly_indicators", [])) * 0.1

        # Normalize score to 0-1 range
        return min(score, 1.0)

    def get_processing_statistics(self) -> builtins.dict[str, Any]:
        """Get event processing statistics"""
        return {
            "events_received": self.events_received,
            "events_processed": self.events_processed,
            "events_filtered": self.events_filtered,
            "processing_errors": self.processing_errors,
            "queue_size": self.processing_queue.qsize(),
            "processed_events_count": len(self.processed_events),
            "active_filters": len([f for f in self.filters.values() if f.enabled]),
            "active_rules": len([r for r in self.rules.values() if r.enabled]),
        }

    def get_recent_events(self, limit: int = 100) -> builtins.list[ProcessedSecurityEvent]:
        """Get recent processed events"""
        return list(self.processed_events)[-limit:]

    def get_high_threat_events(
        self, threshold: float = 0.7
    ) -> builtins.list[ProcessedSecurityEvent]:
        """Get events with high threat scores"""
        return [event for event in self.processed_events if event.threat_score >= threshold]


# Example usage
async def main():
    """Example usage of security event processor"""

    # Initialize processor
    processor = SecurityEventProcessor()

    # Start processing
    processing_task = asyncio.create_task(processor.process_events())

    # Simulate incoming security events
    test_events = [
        {
            "event_id": "evt_001",
            "source_ip": "192.168.1.100",
            "user_id": "admin_user",
            "service_name": "user-service",
            "event_type": "authentication_failure",
            "endpoint": "/api/v1/auth/login",
            "severity": "medium",
            "request_body": "username=admin&password=wrongpass",
        },
        {
            "event_id": "evt_002",
            "source_ip": "10.0.0.50",
            "service_name": "api-gateway",
            "event_type": "suspicious_request",
            "endpoint": "/api/v1/users",
            "severity": "high",
            "request_body": "SELECT * FROM users WHERE id = '1' OR '1'='1'",
        },
        {
            "event_id": "evt_003",
            "source_ip": "203.0.113.42",
            "user_id": "user123",
            "service_name": "payment-service",
            "event_type": "data_access",
            "endpoint": "/api/v1/admin/payments",
            "severity": "medium",
            "response_size": 15728640,  # 15MB
        },
    ]

    print("Ingesting test security events...")
    for event in test_events:
        success = await processor.ingest_event(event)
        print(f"Ingested event {event['event_id']}: {success}")

    # Wait for processing
    await asyncio.sleep(2)

    # Show statistics
    stats = processor.get_processing_statistics()
    print("\n=== PROCESSING STATISTICS ===")
    print(f"Events received: {stats['events_received']}")
    print(f"Events processed: {stats['events_processed']}")
    print(f"Events filtered: {stats['events_filtered']}")
    print(f"Processing errors: {stats['processing_errors']}")

    # Show high threat events
    high_threat_events = processor.get_high_threat_events(threshold=0.5)
    print(f"\n=== HIGH THREAT EVENTS ({len(high_threat_events)}) ===")
    for event in high_threat_events:
        print(f"Event ID: {event.original_event.get('event_id')}")
        print(f"  Threat Score: {event.threat_score:.2f}")
        print(f"  Triggered Rules: {event.triggered_rules}")
        print(f"  Risk Factors: {event.risk_factors}")
        print(f"  Recommended Actions: {event.recommended_actions}")

    # Stop processing
    processing_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
