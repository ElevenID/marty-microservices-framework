"""
Security Monitoring and SIEM Integration for Marty Microservices Framework

Provides comprehensive security monitoring capabilities including:
- Real-time security event collection and analysis
- SIEM integration and log aggregation
- Security metrics and dashboards
- Threat hunting and investigation tools
- Security alerting and incident response
- Performance monitoring for security controls
"""

import asyncio
import builtins
import hashlib
import json
import uuid
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

import redis
from elasticsearch import Elasticsearch
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram

# DI Container imports
from ..core.di_container import get_service, has_service, register_instance


class SecurityEventType(Enum):
    """Types of security events"""

    AUTHENTICATION_SUCCESS = "authentication_success"
    AUTHENTICATION_FAILURE = "authentication_failure"
    AUTHORIZATION_FAILURE = "authorization_failure"
    DATA_ACCESS = "data_access"
    DATA_MODIFICATION = "data_modification"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    MALWARE_DETECTION = "malware_detection"
    INTRUSION_ATTEMPT = "intrusion_attempt"
    POLICY_VIOLATION = "policy_violation"
    CONFIGURATION_CHANGE = "configuration_change"
    VULNERABILITY_DETECTED = "vulnerability_detected"
    THREAT_DETECTED = "threat_detected"
    COMPLIANCE_VIOLATION = "compliance_violation"
    NETWORK_ANOMALY = "network_anomaly"
    SYSTEM_ANOMALY = "system_anomaly"


class SecurityEventSeverity(Enum):
    """Security event severity levels"""

    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SecurityEventStatus(Enum):
    """Security event status"""

    NEW = "new"
    INVESTIGATING = "investigating"
    CONFIRMED = "confirmed"
    FALSE_POSITIVE = "false_positive"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


@dataclass
class SecurityEvent:
    """Security event data structure"""

    event_id: str
    event_type: SecurityEventType
    severity: SecurityEventSeverity
    timestamp: datetime

    # Event details
    source_ip: str | None = None
    user_id: str | None = None
    service_name: str | None = None
    resource: str | None = None
    action: str | None = None

    # Additional context
    user_agent: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    correlation_id: str | None = None

    # Event data
    raw_data: builtins.dict[str, Any] = field(default_factory=dict)
    normalized_data: builtins.dict[str, Any] = field(default_factory=dict)
    enrichment_data: builtins.dict[str, Any] = field(default_factory=dict)

    # Investigation
    status: SecurityEventStatus = SecurityEventStatus.NEW
    assigned_analyst: str | None = None
    investigation_notes: builtins.list[str] = field(default_factory=list)
    related_events: builtins.list[str] = field(default_factory=list)

    # Response
    response_actions: builtins.list[str] = field(default_factory=list)
    mitigation_applied: bool = False

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "event_type": self.event_type.value,
            "severity": self.severity.value,
            "status": self.status.value,
            "timestamp": self.timestamp.isoformat(),
        }

    def calculate_risk_score(self) -> float:
        """Calculate risk score for the event"""
        base_score = {
            SecurityEventSeverity.INFO: 0.1,
            SecurityEventSeverity.LOW: 0.3,
            SecurityEventSeverity.MEDIUM: 0.5,
            SecurityEventSeverity.HIGH: 0.8,
            SecurityEventSeverity.CRITICAL: 1.0,
        }.get(self.severity, 0.1)

        # Adjust for event type
        type_multiplier = {
            SecurityEventType.MALWARE_DETECTION: 1.5,
            SecurityEventType.INTRUSION_ATTEMPT: 1.4,
            SecurityEventType.PRIVILEGE_ESCALATION: 1.3,
            SecurityEventType.DATA_MODIFICATION: 1.2,
            SecurityEventType.AUTHENTICATION_FAILURE: 1.1,
            SecurityEventType.POLICY_VIOLATION: 1.0,
            SecurityEventType.DATA_ACCESS: 0.9,
            SecurityEventType.AUTHENTICATION_SUCCESS: 0.5,
        }.get(self.event_type, 1.0)

        return min(1.0, base_score * type_multiplier)


@dataclass
class SecurityAlert:
    """Security alert based on multiple events or conditions"""

    alert_id: str
    alert_name: str
    severity: SecurityEventSeverity
    created_at: datetime

    # Alert conditions
    trigger_conditions: builtins.list[str] = field(default_factory=list)
    related_events: builtins.list[str] = field(default_factory=list)

    # Alert context
    affected_resources: builtins.list[str] = field(default_factory=list)
    threat_indicators: builtins.list[str] = field(default_factory=list)
    recommended_actions: builtins.list[str] = field(default_factory=list)

    # Response tracking
    status: SecurityEventStatus = SecurityEventStatus.NEW
    assigned_team: str | None = None
    escalation_level: int = 0
    resolution_time: datetime | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "severity": self.severity.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolution_time": self.resolution_time.isoformat() if self.resolution_time else None,
        }


class SecurityEventCollector:
    """
    Collects and normalizes security events from various sources

    Features:
    - Multi-source event collection
    - Event normalization and enrichment
    - Real-time event streaming
    - Event correlation and deduplication
    """

    def __init__(self, redis_client: redis.Redis | None = None):
        self.event_sources: builtins.dict[str, Any] = {}
        self.event_processors: builtins.list[Any] = []
        self.event_queue = asyncio.Queue()
        self.processed_events: builtins.dict[str, SecurityEvent] = {}

        # Use injected Redis client or get from DI container
        if redis_client:
            self.redis_client = redis_client
        else:
            self.redis_client = self._get_redis_client()

        # Event deduplication
        self.recent_events = deque(maxlen=10000)
        self.event_hashes: builtins.set[str] = set()

        # Metrics
        self.events_collected = Counter(
            "marty_security_events_collected_total",
            "Security events collected",
            ["event_type", "severity", "source"],
        )

        self.events_processed = Counter(
            "marty_security_events_processed_total",
            "Security events processed",
            ["status"],
        )

    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client from DI container or create default."""
        if has_service(redis.Redis):
            return get_service(redis.Redis)
        else:
            # Create default Redis client and register it
            client = redis.Redis(host="localhost", port=6379, db=1)
            register_instance(redis.Redis, client)
            return client

    def register_event_source(self, source_name: str, source_config: builtins.dict[str, Any]):
        """Register a new event source"""
        self.event_sources[source_name] = source_config
        print(f"Registered event source: {source_name}")

    async def collect_event(
        self,
        source: str,
        event_type: SecurityEventType,
        severity: SecurityEventSeverity,
        event_data: builtins.dict[str, Any],
    ) -> SecurityEvent | None:
        """Collect and process a security event"""

        # Create security event
        event = SecurityEvent(
            event_id=f"SEC_{uuid.uuid4().hex[:12]}",
            event_type=event_type,
            severity=severity,
            timestamp=datetime.now(),
            source_ip=event_data.get("source_ip"),
            user_id=event_data.get("user_id"),
            service_name=event_data.get("service"),
            resource=event_data.get("resource"),
            action=event_data.get("action"),
            user_agent=event_data.get("user_agent"),
            session_id=event_data.get("session_id"),
            request_id=event_data.get("request_id"),
            raw_data=event_data,
        )

        # Check for duplicates
        event_hash = self._calculate_event_hash(event)
        if event_hash in self.event_hashes:
            return None  # Duplicate event

        # Add to deduplication tracking
        self.event_hashes.add(event_hash)
        self.recent_events.append(event_hash)

        # If queue is full, remove old hash
        if len(self.recent_events) == self.recent_events.maxlen:
            old_hash = self.recent_events[0]
            self.event_hashes.discard(old_hash)

        # Normalize event data
        event.normalized_data = self._normalize_event_data(event)

        # Enrich event with additional context
        event.enrichment_data = await self._enrich_event(event)

        # Store event
        self.processed_events[event.event_id] = event

        # Add to queue for further processing
        await self.event_queue.put(event)

        # Update metrics
        self.events_collected.labels(
            event_type=event_type.value, severity=severity.value, source=source
        ).inc()

        return event

    def _calculate_event_hash(self, event: SecurityEvent) -> str:
        """Calculate hash for event deduplication"""
        hash_data = f"{event.event_type.value}_{event.source_ip}_{event.user_id}_{event.action}"
        return hashlib.sha256(hash_data.encode()).hexdigest()[:16]

    def _normalize_event_data(self, event: SecurityEvent) -> builtins.dict[str, Any]:
        """Normalize event data to standard format"""

        normalized = {
            "timestamp": event.timestamp.isoformat(),
            "event_type": event.event_type.value,
            "severity": event.severity.value,
            "source_ip": event.source_ip,
            "user_id": event.user_id,
            "service": event.service_name,
            "resource": event.resource,
            "action": event.action,
        }

        # Extract additional fields from raw data
        if "http_status" in event.raw_data:
            normalized["http_status"] = event.raw_data["http_status"]

        if "response_time" in event.raw_data:
            normalized["response_time"] = event.raw_data["response_time"]

        if "bytes_transferred" in event.raw_data:
            normalized["bytes_transferred"] = event.raw_data["bytes_transferred"]

        return normalized

    async def _enrich_event(self, event: SecurityEvent) -> builtins.dict[str, Any]:
        """Enrich event with additional context"""

        enrichment = {}

        # GeoIP enrichment
        if event.source_ip:
            enrichment["geo_location"] = self._lookup_geo_location(event.source_ip)

        # User context enrichment
        if event.user_id:
            enrichment["user_context"] = await self._get_user_context(event.user_id)

        # Threat intelligence enrichment
        if event.source_ip:
            enrichment["threat_intel"] = await self._lookup_threat_intelligence(event.source_ip)

        # Asset enrichment
        if event.resource:
            enrichment["asset_info"] = await self._get_asset_information(event.resource)

        return enrichment

    def _lookup_geo_location(self, ip_address: str) -> builtins.dict[str, Any]:
        """Lookup geographic location of IP address"""
        # Mock implementation - would use real GeoIP service
        return {
            "country": "US",
            "region": "California",
            "city": "San Francisco",
            "latitude": 37.7749,
            "longitude": -122.4194,
        }

    async def _get_user_context(self, user_id: str) -> builtins.dict[str, Any]:
        """Get additional user context"""
        # Mock implementation - would query user database
        return {
            "user_type": "standard",
            "department": "Engineering",
            "last_login": "2025-01-21T10:00:00Z",
            "risk_score": 0.2,
        }

    async def _lookup_threat_intelligence(self, ip_address: str) -> builtins.dict[str, Any]:
        """Lookup threat intelligence for IP"""
        # Mock implementation - would query threat intel feeds
        return {
            "reputation": "clean",
            "threat_types": [],
            "confidence": 0.95,
            "last_seen": None,
        }

    async def _get_asset_information(self, resource: str) -> builtins.dict[str, Any]:
        """Get asset information for resource"""
        # Mock implementation - would query asset database
        return {
            "asset_type": "database",
            "criticality": "high",
            "owner": "data-team",
            "compliance_requirements": ["GDPR", "HIPAA"],
        }


class SecurityAnalyticsEngine:
    """
    Advanced security analytics and correlation engine

    Features:
    - Event correlation and pattern detection
    - Behavioral analysis and anomaly detection
    - Threat hunting queries
    - Security metrics calculation
    """

    def __init__(self, redis_client: redis.Redis | None = None):
        self.correlation_rules: builtins.list[builtins.dict[str, Any]] = []
        self.behavioral_baselines: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.threat_patterns: builtins.list[builtins.dict[str, Any]] = []

        # Use injected Redis client or get from DI container
        if redis_client:
            self.redis_client = redis_client
        else:
            self.redis_client = self._get_redis_client()

        # Initialize built-in correlation rules
        self._initialize_correlation_rules()

        # Metrics
        self.correlations_detected = Counter(
            "marty_security_correlations_detected_total",
            "Security event correlations detected",
            ["rule_name"],
        )

        self.anomalies_detected = Counter(
            "marty_security_anomalies_detected_total",
            "Security anomalies detected",
            ["anomaly_type"],
        )

    def _get_redis_client(self) -> redis.Redis:
        """Get Redis client from DI container or create default."""
        if has_service(redis.Redis):
            return get_service(redis.Redis)
        else:
            # Create default Redis client and register it
            client = redis.Redis(host="localhost", port=6379, db=2)
            register_instance(redis.Redis, client)
            return client

    def _initialize_correlation_rules(self):
        """Initialize built-in correlation rules"""

        # Multiple failed logins followed by success
        self.correlation_rules.append(
            {
                "rule_id": "RULE_001",
                "name": "Brute Force Attack",
                "description": "Multiple failed logins followed by successful login",
                "conditions": [
                    {
                        "event_type": SecurityEventType.AUTHENTICATION_FAILURE,
                        "count": ">=5",
                        "timeframe": 300,  # 5 minutes
                    },
                    {
                        "event_type": SecurityEventType.AUTHENTICATION_SUCCESS,
                        "count": ">=1",
                        "timeframe": 60,  # 1 minute after failures
                    },
                ],
                "severity": SecurityEventSeverity.HIGH,
                "actions": ["block_ip", "notify_security_team"],
            }
        )

        # Privilege escalation after authentication
        self.correlation_rules.append(
            {
                "rule_id": "RULE_002",
                "name": "Privilege Escalation",
                "description": "Privilege escalation shortly after authentication",
                "conditions": [
                    {
                        "event_type": SecurityEventType.AUTHENTICATION_SUCCESS,
                        "count": ">=1",
                        "timeframe": 3600,
                    },
                    {
                        "event_type": SecurityEventType.PRIVILEGE_ESCALATION,
                        "count": ">=1",
                        "timeframe": 300,
                    },
                ],
                "severity": SecurityEventSeverity.CRITICAL,
                "actions": ["disable_account", "escalate_incident"],
            }
        )

        # Unusual data access patterns
        self.correlation_rules.append(
            {
                "rule_id": "RULE_003",
                "name": "Mass Data Access",
                "description": "Unusual volume of data access events",
                "conditions": [
                    {
                        "event_type": SecurityEventType.DATA_ACCESS,
                        "count": ">=100",
                        "timeframe": 3600,
                    }
                ],
                "severity": SecurityEventSeverity.MEDIUM,
                "actions": ["monitor_user", "notify_data_owner"],
            }
        )

    async def analyze_events(
        self, events: builtins.list[SecurityEvent]
    ) -> builtins.list[SecurityAlert]:
        """Analyze events for correlations and anomalies"""

        alerts = []

        # Run correlation analysis
        correlation_alerts = await self._run_correlation_analysis(events)
        alerts.extend(correlation_alerts)

        # Run anomaly detection
        anomaly_alerts = await self._run_anomaly_detection(events)
        alerts.extend(anomaly_alerts)

        # Run behavioral analysis
        behavioral_alerts = await self._run_behavioral_analysis(events)
        alerts.extend(behavioral_alerts)

        return alerts

    async def _run_correlation_analysis(
        self, events: builtins.list[SecurityEvent]
    ) -> builtins.list[SecurityAlert]:
        """Run correlation analysis on events"""

        alerts = []

        for rule in self.correlation_rules:
            try:
                # Check if rule conditions are met
                if await self._evaluate_correlation_rule(rule, events):
                    alert = SecurityAlert(
                        alert_id=f"ALERT_{uuid.uuid4().hex[:12]}",
                        alert_name=rule["name"],
                        severity=rule["severity"],
                        created_at=datetime.now(),
                        trigger_conditions=[rule["description"]],
                        related_events=[e.event_id for e in events],
                        recommended_actions=rule.get("actions", []),
                    )
                    alerts.append(alert)

                    # Update metrics
                    self.correlations_detected.labels(rule_name=rule["name"]).inc()

            except Exception as e:
                print(f"Error evaluating correlation rule {rule['rule_id']}: {e}")

        return alerts

    async def _evaluate_correlation_rule(
        self, rule: builtins.dict[str, Any], events: builtins.list[SecurityEvent]
    ) -> bool:
        """Evaluate if correlation rule conditions are met"""

        conditions = rule["conditions"]
        current_time = datetime.now()

        # Group events by type and timeframe
        for condition in conditions:
            event_type = condition["event_type"]
            count_threshold = int(condition["count"].replace(">=", ""))
            timeframe = condition["timeframe"]

            # Find matching events within timeframe
            matching_events = [
                event
                for event in events
                if (
                    event.event_type == event_type
                    and (current_time - event.timestamp).total_seconds() <= timeframe
                )
            ]

            if len(matching_events) < count_threshold:
                return False

        return True

    async def _run_anomaly_detection(
        self, events: builtins.list[SecurityEvent]
    ) -> builtins.list[SecurityAlert]:
        """Run anomaly detection on events"""

        alerts = []

        # Statistical anomaly detection
        event_counts = defaultdict(int)
        for event in events:
            event_counts[event.event_type] += 1

        # Check for unusual event volumes
        for event_type, count in event_counts.items():
            baseline = self._get_baseline_count(event_type)
            if count > baseline * 2:  # 2x normal volume
                alert = SecurityAlert(
                    alert_id=f"ANOMALY_{uuid.uuid4().hex[:12]}",
                    alert_name=f"Unusual {event_type.value} Volume",
                    severity=SecurityEventSeverity.MEDIUM,
                    created_at=datetime.now(),
                    trigger_conditions=[f"Event count {count} exceeds baseline {baseline}"],
                    recommended_actions=["investigate_cause", "check_system_health"],
                )
                alerts.append(alert)

                # Update metrics
                self.anomalies_detected.labels(anomaly_type="volume_anomaly").inc()

        return alerts

    def _get_baseline_count(self, event_type: SecurityEventType) -> int:
        """Get baseline count for event type"""
        # Mock implementation - would use historical data
        baselines = {
            SecurityEventType.AUTHENTICATION_SUCCESS: 1000,
            SecurityEventType.AUTHENTICATION_FAILURE: 50,
            SecurityEventType.DATA_ACCESS: 500,
            SecurityEventType.AUTHORIZATION_FAILURE: 20,
        }
        return baselines.get(event_type, 100)

    async def _run_behavioral_analysis(
        self, events: builtins.list[SecurityEvent]
    ) -> builtins.list[SecurityAlert]:
        """Run behavioral analysis on events"""

        alerts = []

        # Analyze user behavior patterns
        user_events = defaultdict(list)
        for event in events:
            if event.user_id:
                user_events[event.user_id].append(event)

        for user_id, user_event_list in user_events.items():
            # Check for unusual access patterns
            unusual_hours = self._check_unusual_access_hours(user_event_list)
            if unusual_hours:
                alert = SecurityAlert(
                    alert_id=f"BEHAVIOR_{uuid.uuid4().hex[:12]}",
                    alert_name=f"Unusual Access Hours - {user_id}",
                    severity=SecurityEventSeverity.LOW,
                    created_at=datetime.now(),
                    trigger_conditions=["Access outside normal business hours"],
                    affected_resources=[user_id],
                    recommended_actions=[
                        "verify_user_activity",
                        "check_account_compromise",
                    ],
                )
                alerts.append(alert)

        return alerts

    def _check_unusual_access_hours(self, events: builtins.list[SecurityEvent]) -> bool:
        """Check if user is accessing system at unusual hours"""
        # Mock implementation - check for access outside 9-5
        for event in events:
            hour = event.timestamp.hour
            if hour < 9 or hour > 17:  # Outside business hours
                return True
        return False


class SIEMIntegration:
    """
    SIEM (Security Information and Event Management) integration

    Features:
    - Integration with popular SIEM platforms
    - Log forwarding and normalization
    - Alert correlation with external systems
    - Threat intelligence feeds
    """

    def __init__(self, elasticsearch_client: Elasticsearch | None = None):
        self.siem_connections: builtins.dict[str, Any] = {}
        self.log_forwarders: builtins.list[Any] = []

        # Use injected Elasticsearch client or get from DI container
        if elasticsearch_client:
            self.elasticsearch = elasticsearch_client
        else:
            self.elasticsearch = self._get_elasticsearch_client()

        # Metrics
        self.logs_forwarded = Counter(
            "marty_siem_logs_forwarded_total",
            "Logs forwarded to SIEM",
            ["destination"],
        )

    def _get_elasticsearch_client(self) -> Elasticsearch:
        """Get Elasticsearch client from DI container or create default."""
        if has_service(Elasticsearch):
            return get_service(Elasticsearch)
        else:
            # Create default Elasticsearch client and register it
            client = Elasticsearch([{"host": "localhost", "port": 9200}])
            register_instance(Elasticsearch, client)
            return client

    def configure_siem_connection(self, siem_name: str, config: builtins.dict[str, Any]):
        """Configure connection to SIEM platform"""
        self.siem_connections[siem_name] = config
        print(f"Configured SIEM connection: {siem_name}")

    async def forward_event_to_siem(self, event: SecurityEvent, siem_name: str):
        """Forward security event to SIEM platform"""

        if siem_name not in self.siem_connections:
            print(f"SIEM connection not configured: {siem_name}")
            return

        # Convert event to SIEM format
        siem_event = self._convert_to_siem_format(event, siem_name)

        # Forward to SIEM
        try:
            if siem_name == "elasticsearch":
                await self._forward_to_elasticsearch(siem_event)
            elif siem_name == "splunk":
                await self._forward_to_splunk(siem_event)
            elif siem_name == "qradar":
                await self._forward_to_qradar(siem_event)

            # Update metrics
            self.logs_forwarded.labels(destination=siem_name).inc()

        except Exception as e:
            print(f"Error forwarding to SIEM {siem_name}: {e}")

    def _convert_to_siem_format(
        self, event: SecurityEvent, siem_name: str
    ) -> builtins.dict[str, Any]:
        """Convert event to SIEM-specific format"""

        if siem_name == "elasticsearch":
            return {
                "@timestamp": event.timestamp.isoformat(),
                "event": {
                    "id": event.event_id,
                    "type": event.event_type.value,
                    "severity": event.severity.value,
                    "category": "security",
                },
                "source": {"ip": event.source_ip},
                "user": {"id": event.user_id},
                "service": {"name": event.service_name},
                "resource": event.resource,
                "action": event.action,
                "raw_data": event.raw_data,
                "normalized_data": event.normalized_data,
                "enrichment_data": event.enrichment_data,
            }

        if siem_name == "splunk":
            return {
                "time": event.timestamp.timestamp(),
                "source": "marty_security",
                "sourcetype": "security_event",
                "event": json.dumps(event.to_dict()),
            }

        # Generic format
        return event.to_dict()

    async def _forward_to_elasticsearch(self, event_data: builtins.dict[str, Any]):
        """Forward event to Elasticsearch"""
        index_name = f"marty-security-{datetime.now().strftime('%Y.%m.%d')}"
        self.elasticsearch.index(index=index_name, document=event_data)

    async def _forward_to_splunk(self, event_data: builtins.dict[str, Any]):
        """Forward event to Splunk"""
        # Mock implementation - would use Splunk HEC or Universal Forwarder
        raise NotImplementedError("Splunk forwarding not implemented")
        print(f"Forwarding to Splunk: {event_data}")

    async def _forward_to_qradar(self, event_data: builtins.dict[str, Any]):
        """Forward event to IBM QRadar"""
        # Mock implementation - would use QRadar REST API
        raise NotImplementedError("QRadar forwarding not implemented")
        print(f"Forwarding to QRadar: {event_data}")


class SecurityMonitoringDashboard:
    """
    Security monitoring dashboard and reporting

    Features:
    - Real-time security metrics
    - Interactive dashboards
    - Security KPI tracking
    - Alert management interface
    """

    def __init__(self):
        self.metrics_registry = CollectorRegistry()
        self.active_alerts: builtins.dict[str, SecurityAlert] = {}

        # Dashboard metrics
        self.security_score = Gauge(
            "marty_security_score",
            "Overall security score",
            registry=self.metrics_registry,
        )

        self.threat_level = Gauge(
            "marty_threat_level",
            "Current threat level",
            registry=self.metrics_registry,
        )

    def get_security_dashboard(self) -> builtins.dict[str, Any]:
        """Get security dashboard data"""

        # Calculate security metrics
        security_score = self._calculate_security_score()
        threat_level = self._calculate_threat_level()

        # Get alert summary
        alert_summary = self._get_alert_summary()

        # Get top threats
        top_threats = self._get_top_threats()

        return {
            "dashboard_timestamp": datetime.now().isoformat(),
            "security_score": security_score,
            "threat_level": threat_level,
            "alert_summary": alert_summary,
            "top_threats": top_threats,
            "total_active_alerts": len(self.active_alerts),
            "critical_alerts": len(
                [
                    a
                    for a in self.active_alerts.values()
                    if a.severity == SecurityEventSeverity.CRITICAL
                ]
            ),
        }

    def _calculate_security_score(self) -> float:
        """Calculate overall security score (0-100)"""
        # Mock calculation - would use real security metrics
        base_score = 85.0

        # Deduct points for active critical alerts
        critical_alerts = len(
            [a for a in self.active_alerts.values() if a.severity == SecurityEventSeverity.CRITICAL]
        )
        score = base_score - (critical_alerts * 10)

        # Deduct points for high alerts
        high_alerts = len(
            [a for a in self.active_alerts.values() if a.severity == SecurityEventSeverity.HIGH]
        )
        score = score - (high_alerts * 5)

        return max(0.0, min(100.0, score))

    def _calculate_threat_level(self) -> str:
        """Calculate current threat level"""
        critical_count = len(
            [a for a in self.active_alerts.values() if a.severity == SecurityEventSeverity.CRITICAL]
        )
        high_count = len(
            [a for a in self.active_alerts.values() if a.severity == SecurityEventSeverity.HIGH]
        )

        if critical_count > 0:
            return "CRITICAL"
        if high_count > 3:
            return "HIGH"
        if high_count > 0:
            return "ELEVATED"
        return "NORMAL"

    def _get_alert_summary(self) -> builtins.dict[str, Any]:
        """Get alert summary by severity and status"""

        by_severity = defaultdict(int)
        by_status = defaultdict(int)

        for alert in self.active_alerts.values():
            by_severity[alert.severity.value] += 1
            by_status[alert.status.value] += 1

        return {"by_severity": dict(by_severity), "by_status": dict(by_status)}

    def _get_top_threats(self) -> builtins.list[builtins.dict[str, Any]]:
        """Get top security threats"""

        # Mock implementation - would analyze actual threat data
        return [
            {
                "threat_name": "Brute Force Attacks",
                "count": 15,
                "trend": "increasing",
                "risk_level": "high",
            },
            {
                "threat_name": "Unusual Data Access",
                "count": 8,
                "trend": "stable",
                "risk_level": "medium",
            },
            {
                "threat_name": "Policy Violations",
                "count": 23,
                "trend": "decreasing",
                "risk_level": "low",
            },
        ]


class SecurityMonitoringSystem:
    """
    Complete security monitoring system orchestrator

    Coordinates all security monitoring components:
    - Event collection and processing
    - Analytics and correlation
    - SIEM integration
    - Dashboard and reporting
    """

    def __init__(self,
                 event_collector: SecurityEventCollector | None = None,
                 analytics_engine: SecurityAnalyticsEngine | None = None,
                 siem_integration: SIEMIntegration | None = None,
                 dashboard: SecurityMonitoringDashboard | None = None):
        # Use injected components or create new ones
        self.event_collector = event_collector or SecurityEventCollector()
        self.analytics_engine = analytics_engine or SecurityAnalyticsEngine()
        self.siem_integration = siem_integration or SIEMIntegration()
        self.dashboard = dashboard or SecurityMonitoringDashboard()

        # Register components in DI container
        self._register_components_in_di()

        # Processing queues
        self.event_queue = asyncio.Queue()
        self.alert_queue = asyncio.Queue()

        # System state
        self.monitoring_enabled = True
        self.processing_workers = 3

        # Register common event sources
        self._register_default_sources()

    def _register_components_in_di(self) -> None:
        """Register monitoring components in DI container."""
        register_instance(SecurityEventCollector, self.event_collector)
        register_instance(SecurityAnalyticsEngine, self.analytics_engine)
        register_instance(SIEMIntegration, self.siem_integration)
        register_instance(SecurityMonitoringDashboard, self.dashboard)
        register_instance(SecurityMonitoringSystem, self)

    def _register_default_sources(self):
        """Register default event sources"""

        # Application logs
        self.event_collector.register_event_source(
            "application_logs",
            {"type": "log_file", "path": "/var/log/marty/*.log", "format": "json"},
        )

        # Web server logs
        self.event_collector.register_event_source(
            "nginx_logs",
            {
                "type": "log_file",
                "path": "/var/log/nginx/access.log",
                "format": "combined",
            },
        )

        # System logs
        self.event_collector.register_event_source(
            "system_logs", {"type": "syslog", "facility": "auth", "severity": "info"}
        )

    async def start_monitoring(self):
        """Start security monitoring system"""

        print("Starting Security Monitoring System...")

        # Start processing workers
        workers = []
        for i in range(self.processing_workers):
            worker = asyncio.create_task(self._process_events_worker(f"worker_{i}"))
            workers.append(worker)

        # Start alert processor
        alert_processor = asyncio.create_task(self._process_alerts_worker())
        workers.append(alert_processor)

        # Start metrics updater
        metrics_updater = asyncio.create_task(self._update_metrics_worker())
        workers.append(metrics_updater)

        print(f"Security monitoring started with {len(workers)} workers")

        # Wait for all workers
        await asyncio.gather(*workers)

    async def _process_events_worker(self, worker_name: str):
        """Process security events worker"""

        print(f"Starting event processing worker: {worker_name}")

        while self.monitoring_enabled:
            try:
                # Get event from collector queue
                event = await self.event_collector.event_queue.get()

                if event is None:
                    continue

                # Run analytics on event
                alerts = await self.analytics_engine.analyze_events([event])

                # Process any generated alerts
                for alert in alerts:
                    await self.alert_queue.put(alert)
                    self.dashboard.active_alerts[alert.alert_id] = alert

                # Forward to SIEM
                for siem_name in self.siem_integration.siem_connections.keys():
                    await self.siem_integration.forward_event_to_siem(event, siem_name)

                # Mark task as done
                self.event_collector.event_queue.task_done()

            except Exception as e:
                print(f"Error in event processing worker {worker_name}: {e}")
                await asyncio.sleep(1)

    async def _process_alerts_worker(self):
        """Process security alerts worker"""

        print("Starting alert processing worker")

        while self.monitoring_enabled:
            try:
                # Get alert from queue
                alert = await self.alert_queue.get()

                if alert is None:
                    continue

                # Process alert based on severity
                await self._handle_security_alert(alert)

                # Mark task as done
                self.alert_queue.task_done()

            except Exception as e:
                print(f"Error in alert processing: {e}")
                await asyncio.sleep(1)

    async def _handle_security_alert(self, alert: SecurityAlert):
        """Handle security alert based on severity and type"""

        print(f"Processing alert: {alert.alert_name} ({alert.severity.value})")

        # Critical alerts require immediate action
        if alert.severity == SecurityEventSeverity.CRITICAL:
            await self._handle_critical_alert(alert)

        # High alerts require investigation
        elif alert.severity == SecurityEventSeverity.HIGH:
            await self._handle_high_alert(alert)

        # Medium alerts are logged and monitored
        elif alert.severity == SecurityEventSeverity.MEDIUM:
            await self._handle_medium_alert(alert)

        # Update alert status
        alert.status = SecurityEventStatus.INVESTIGATING

    async def _handle_critical_alert(self, alert: SecurityAlert):
        """Handle critical security alert"""

        print(f"CRITICAL ALERT: {alert.alert_name}")

        # Implement automated response
        for action in alert.recommended_actions:
            if action == "block_ip":
                # Mock IP blocking
                print("Blocking suspicious IP addresses")
            elif action == "disable_account":
                # Mock account disabling
                print("Disabling compromised user accounts")
            elif action == "escalate_incident":
                # Mock incident escalation
                print("Escalating to security incident response team")

        # Send notifications
        await self._send_alert_notification(alert, ["security-team@company.com"])

    async def _handle_high_alert(self, alert: SecurityAlert):
        """Handle high severity alert"""

        print(f"HIGH ALERT: {alert.alert_name}")

        # Assign to security analyst
        alert.assigned_team = "security_operations"

        # Send notification
        await self._send_alert_notification(alert, ["soc@company.com"])

    async def _handle_medium_alert(self, alert: SecurityAlert):
        """Handle medium severity alert"""

        print(f"MEDIUM ALERT: {alert.alert_name}")

        # Log for investigation
        # Would integrate with ticketing system

    async def _send_alert_notification(self, alert: SecurityAlert, recipients: builtins.list[str]):
        """Send alert notification"""

        # Mock implementation - would integrate with email/Slack/PagerDuty
        print(f"Sending alert notification to {recipients}")
        print(f"Alert: {alert.alert_name}")
        print(f"Severity: {alert.severity.value}")
        print(f"Time: {alert.created_at}")

    async def _update_metrics_worker(self):
        """Update security metrics worker"""

        while self.monitoring_enabled:
            try:
                # Update dashboard metrics
                if self.dashboard.metrics_registry:
                    security_score = self.dashboard._calculate_security_score()
                    self.dashboard.security_score.set(security_score)

                    threat_level_map = {
                        "NORMAL": 1,
                        "ELEVATED": 2,
                        "HIGH": 3,
                        "CRITICAL": 4,
                    }
                    threat_level = self.dashboard._calculate_threat_level()
                    self.dashboard.threat_level.set(threat_level_map.get(threat_level, 1))

                # Sleep for metrics update interval
                await asyncio.sleep(60)  # Update every minute

            except Exception as e:
                print(f"Error updating metrics: {e}")
                await asyncio.sleep(60)

    def get_monitoring_status(self) -> builtins.dict[str, Any]:
        """Get monitoring system status"""

        return {
            "monitoring_enabled": self.monitoring_enabled,
            "event_queue_size": self.event_collector.event_queue.qsize(),
            "alert_queue_size": self.alert_queue.qsize(),
            "processed_events": len(self.event_collector.processed_events),
            "active_alerts": len(self.dashboard.active_alerts),
            "registered_sources": len(self.event_collector.event_sources),
            "siem_connections": len(self.siem_integration.siem_connections),
        }


# Example usage and testing
async def main():
    """Example usage of security monitoring system"""

    # Initialize monitoring system
    monitoring = SecurityMonitoringSystem()

    print("=== Security Monitoring System Demo ===")

    # Configure SIEM connections
    monitoring.siem_integration.configure_siem_connection(
        "elasticsearch", {"host": "localhost", "port": 9200}
    )

    # Simulate some security events
    print("\nSimulating security events...")

    # Failed login attempts
    for _i in range(6):
        await monitoring.event_collector.collect_event(
            source="application",
            event_type=SecurityEventType.AUTHENTICATION_FAILURE,
            severity=SecurityEventSeverity.MEDIUM,
            event_data={
                "source_ip": "192.168.1.100",
                "user_id": "admin",
                "action": "login_attempt",
                "http_status": 401,
            },
        )

    # Successful login (potential brute force success)
    await monitoring.event_collector.collect_event(
        source="application",
        event_type=SecurityEventType.AUTHENTICATION_SUCCESS,
        severity=SecurityEventSeverity.INFO,
        event_data={
            "source_ip": "192.168.1.100",
            "user_id": "admin",
            "action": "login_success",
            "http_status": 200,
        },
    )

    # Privilege escalation
    await monitoring.event_collector.collect_event(
        source="application",
        event_type=SecurityEventType.PRIVILEGE_ESCALATION,
        severity=SecurityEventSeverity.HIGH,
        event_data={
            "source_ip": "192.168.1.100",
            "user_id": "admin",
            "action": "sudo_command",
            "resource": "/etc/passwd",
        },
    )

    # Process events through analytics
    events = list(monitoring.event_collector.processed_events.values())
    alerts = await monitoring.analytics_engine.analyze_events(events)

    print(f"Generated {len(alerts)} security alerts")

    # Show dashboard
    dashboard_data = monitoring.dashboard.get_security_dashboard()
    print("\nSecurity Dashboard:")
    print(f"Security Score: {dashboard_data['security_score']}")
    print(f"Threat Level: {dashboard_data['threat_level']}")
    print(f"Active Alerts: {dashboard_data['total_active_alerts']}")
    print(f"Critical Alerts: {dashboard_data['critical_alerts']}")

    # Show monitoring status
    status = monitoring.get_monitoring_status()
    print("\nMonitoring Status:")
    print(f"Events Processed: {status['processed_events']}")
    print(f"Active Alerts: {status['active_alerts']}")
    print(f"SIEM Connections: {status['siem_connections']}")


# DI container convenience functions

def create_monitoring_system_with_di() -> SecurityMonitoringSystem:
    """Create a complete monitoring system with all components registered in DI container."""
    monitoring_system = SecurityMonitoringSystem()
    return monitoring_system


def get_monitoring_system_from_di() -> SecurityMonitoringSystem:
    """Get the monitoring system from DI container, creating if necessary."""
    if has_service(SecurityMonitoringSystem):
        return get_service(SecurityMonitoringSystem)
    else:
        return create_monitoring_system_with_di()


def get_event_collector_from_di() -> SecurityEventCollector:
    """Get the event collector from DI container."""
    if has_service(SecurityEventCollector):
        return get_service(SecurityEventCollector)
    else:
        # Create monitoring system which will register the event collector
        create_monitoring_system_with_di()
        return get_service(SecurityEventCollector)


def get_analytics_engine_from_di() -> SecurityAnalyticsEngine:
    """Get the analytics engine from DI container."""
    if has_service(SecurityAnalyticsEngine):
        return get_service(SecurityAnalyticsEngine)
    else:
        # Create monitoring system which will register the analytics engine
        create_monitoring_system_with_di()
        return get_service(SecurityAnalyticsEngine)


def get_siem_integration_from_di() -> SIEMIntegration:
    """Get the SIEM integration from DI container."""
    if has_service(SIEMIntegration):
        return get_service(SIEMIntegration)
    else:
        # Create monitoring system which will register the SIEM integration
        create_monitoring_system_with_di()
        return get_service(SIEMIntegration)


if __name__ == "__main__":
    asyncio.run(main())
