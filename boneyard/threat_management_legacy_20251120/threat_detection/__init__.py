"""
Advanced Threat Detection and Response System for Marty Microservices Framework

Provides comprehensive threat detection including:
- Real-time anomaly detection
- Behavioral analysis and machine learning
- Threat intelligence integration
- Automated incident response
- Security event correlation
- Advanced persistent threat (APT) detection
"""

import asyncio
import builtins
import re
import statistics
import time
from collections import defaultdict, deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any

from prometheus_client import Counter, Histogram

# External dependencies (optional)
try:
    REDIS_AVAILABLE = True

    ANALYTICS_AVAILABLE = True
except ImportError:
    ANALYTICS_AVAILABLE = False


class ThreatLevel(Enum):
    """Threat severity levels"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatCategory(Enum):
    """Categories of security threats"""

    AUTHENTICATION_ATTACK = "authentication_attack"
    AUTHORIZATION_BYPASS = "authorization_bypass"
    DATA_EXFILTRATION = "data_exfiltration"
    INJECTION_ATTACK = "injection_attack"
    DDoS_ATTACK = "ddos_attack"
    MALWARE = "malware"
    INSIDER_THREAT = "insider_threat"
    APT = "advanced_persistent_threat"
    BRUTE_FORCE = "brute_force"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    LATERAL_MOVEMENT = "lateral_movement"


class IncidentStatus(Enum):
    """Incident response status"""

    DETECTED = "detected"
    INVESTIGATING = "investigating"
    CONTAINED = "contained"
    RESOLVED = "resolved"
    FALSE_POSITIVE = "false_positive"


@dataclass
class SecurityEvent:
    """Security event data structure"""

    event_id: str
    timestamp: datetime
    source_ip: str
    user_id: str | None
    service_name: str
    event_type: str
    description: str
    severity: ThreatLevel
    category: ThreatCategory
    raw_data: builtins.dict[str, Any]
    correlation_id: str | None = None
    threat_indicators: builtins.list[str] = field(default_factory=list)

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "timestamp": self.timestamp.isoformat(),
            "severity": self.severity.value,
            "category": self.category.value,
        }


@dataclass
class ThreatIntelligence:
    """Threat intelligence data"""

    indicator: str
    indicator_type: str  # ip, domain, hash, etc.
    threat_type: ThreatCategory
    confidence: float  # 0.0 - 1.0
    source: str
    description: str
    created_at: datetime
    expires_at: datetime | None = None

    def is_valid(self) -> bool:
        """Check if threat intel is still valid"""
        if self.expires_at:
            return datetime.now() < self.expires_at
        return True


@dataclass
class SecurityIncident:
    """Security incident tracking"""

    incident_id: str
    title: str
    description: str
    threat_level: ThreatLevel
    category: ThreatCategory
    status: IncidentStatus
    created_at: datetime
    updated_at: datetime
    events: builtins.list[SecurityEvent] = field(default_factory=list)
    affected_services: builtins.set[str] = field(default_factory=set)
    response_actions: builtins.list[str] = field(default_factory=list)
    assigned_to: str | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        return {
            **asdict(self),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "events": [event.to_dict() for event in self.events],
            "affected_services": list(self.affected_services),
            "threat_level": self.threat_level.value,
            "category": self.category.value,
            "status": self.status.value,
        }


class AnomalyDetector:
    """
    Machine learning-based anomaly detection system

    Features:
    - Statistical anomaly detection
    - Behavioral baseline establishment
    - Real-time analysis
    - Pattern recognition
    """

    def __init__(self, window_size: int = 1000):
        self.window_size = window_size
        self.baselines: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.event_history: builtins.dict[str, deque] = defaultdict(
            lambda: deque(maxlen=window_size)
        )

        # Metrics
        if ANALYTICS_AVAILABLE:
            self.anomaly_detections = Counter(
                "marty_anomaly_detections_total",
                "Anomaly detections",
                ["service", "type", "severity"],
            )
            self.anomaly_score = Histogram(
                "marty_anomaly_score", "Anomaly scores", ["service", "metric"]
            )

    def establish_baseline(self, service_name: str, metric_name: str, values: builtins.list[float]):
        """Establish behavioral baseline for a service metric"""
        if len(values) < 10:
            return  # Need minimum data points

        baseline = {
            "mean": statistics.mean(values),
            "std_dev": statistics.stdev(values) if len(values) > 1 else 0,
            "median": statistics.median(values),
            "percentile_95": statistics.quantiles(values, n=20)[18]
            if len(values) >= 20
            else max(values),
            "min": min(values),
            "max": max(values),
            "sample_count": len(values),
            "last_updated": datetime.now(),
        }

        if service_name not in self.baselines:
            self.baselines[service_name] = {}

        self.baselines[service_name][metric_name] = baseline
        print(f"Established baseline for {service_name}.{metric_name}")

    def detect_statistical_anomaly(
        self,
        service_name: str,
        metric_name: str,
        value: float,
        threshold_std: float = 3.0,
    ) -> builtins.tuple[bool, float]:
        """Detect statistical anomalies using Z-score"""

        # Store value in history
        key = f"{service_name}.{metric_name}"
        self.event_history[key].append({"value": value, "timestamp": datetime.now()})

        # Check if we have baseline
        if service_name not in self.baselines or metric_name not in self.baselines[service_name]:
            # Build baseline from recent history
            recent_values = [item["value"] for item in self.event_history[key]]
            if len(recent_values) >= 30:  # Minimum for baseline
                self.establish_baseline(service_name, metric_name, recent_values)
                return False, 0.0  # Not anomalous during baseline establishment
            return False, 0.0

        baseline = self.baselines[service_name][metric_name]

        # Calculate Z-score
        if baseline["std_dev"] == 0:
            z_score = 0.0
        else:
            z_score = abs(value - baseline["mean"]) / baseline["std_dev"]

        # Update metrics
        if ANALYTICS_AVAILABLE:
            self.anomaly_score.labels(service=service_name, metric=metric_name).observe(z_score)

        is_anomaly = z_score > threshold_std

        if is_anomaly and ANALYTICS_AVAILABLE:
            severity = "high" if z_score > 5.0 else "medium" if z_score > 4.0 else "low"
            self.anomaly_detections.labels(
                service=service_name, type="statistical", severity=severity
            ).inc()

        return is_anomaly, z_score

    def detect_behavioral_anomaly(
        self, service_name: str, user_actions: builtins.list[builtins.dict[str, Any]]
    ) -> builtins.tuple[bool, float, builtins.list[str]]:
        """Detect behavioral anomalies in user actions"""

        if not user_actions:
            return False, 0.0, []

        anomaly_indicators = []
        anomaly_score = 0.0

        # Analyze request patterns
        request_times = [action.get("timestamp", datetime.now()) for action in user_actions]
        if len(request_times) > 1:
            # Check for rapid-fire requests (potential bot behavior)
            time_deltas = []
            for i in range(1, len(request_times)):
                if isinstance(request_times[i], str):
                    current_time = datetime.fromisoformat(request_times[i])
                else:
                    current_time = request_times[i]

                if isinstance(request_times[i - 1], str):
                    prev_time = datetime.fromisoformat(request_times[i - 1])
                else:
                    prev_time = request_times[i - 1]

                delta = (current_time - prev_time).total_seconds()
                time_deltas.append(delta)

            if time_deltas:
                avg_delta = statistics.mean(time_deltas)
                if avg_delta < 0.1:  # Less than 100ms between requests
                    anomaly_score += 0.3
                    anomaly_indicators.append("rapid_requests")

        # Analyze request patterns
        endpoints = [action.get("endpoint", "") for action in user_actions]
        unique_endpoints = set(endpoints)

        if len(endpoints) > 100 and len(unique_endpoints) > 50:
            # Potential reconnaissance
            anomaly_score += 0.4
            anomaly_indicators.append("reconnaissance_pattern")

        # Check for suspicious user agents
        user_agents = [action.get("user_agent", "") for action in user_actions]
        for ua in user_agents:
            if self._is_suspicious_user_agent(ua):
                anomaly_score += 0.2
                anomaly_indicators.append("suspicious_user_agent")
                break

        # Check for unusual geographic patterns
        ips = [action.get("source_ip", "") for action in user_actions]
        unique_ips = set(ips)
        if len(unique_ips) > 10:  # Many different IPs for same user
            anomaly_score += 0.3
            anomaly_indicators.append("multiple_ips")

        # Check for privilege escalation attempts
        for action in user_actions:
            endpoint = action.get("endpoint", "")
            if "/admin" in endpoint or "/privileged" in endpoint:
                anomaly_score += 0.2
                anomaly_indicators.append("privilege_escalation_attempt")

        is_anomaly = anomaly_score > 0.5

        if is_anomaly and ANALYTICS_AVAILABLE:
            severity = "high" if anomaly_score > 0.8 else "medium"
            self.anomaly_detections.labels(
                service=service_name, type="behavioral", severity=severity
            ).inc()

        return is_anomaly, anomaly_score, anomaly_indicators

    def _is_suspicious_user_agent(self, user_agent: str) -> bool:
        """Check if user agent is suspicious"""
        suspicious_patterns = [
            r"(?i)bot",
            r"(?i)crawler",
            r"(?i)scanner",
            r"(?i)sqlmap",
            r"(?i)nikto",
            r"(?i)nmap",
            r"(?i)python-requests",
            r"(?i)curl",
            r"(?i)wget",
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, user_agent):
                return True

        return False

    def get_baseline_summary(self) -> builtins.dict[str, Any]:
        """Get summary of established baselines"""
        summary = {
            "total_services": len(self.baselines),
            "total_metrics": sum(len(metrics) for metrics in self.baselines.values()),
            "services": {},
        }

        for service, metrics in self.baselines.items():
            summary["services"][service] = {
                "metric_count": len(metrics),
                "metrics": list(metrics.keys()),
                "last_updated": max(
                    metric["last_updated"] for metric in metrics.values()
                ).isoformat(),
            }

        return summary


class ThreatIntelligenceEngine:
    """
    Threat intelligence integration and management

    Features:
    - Multiple threat intel sources
    - Real-time threat feed updates
    - IoC (Indicators of Compromise) matching
    - Threat attribution and scoring
    """

    def __init__(self):
        self.threat_indicators: builtins.dict[str, ThreatIntelligence] = {}
        self.threat_feeds: builtins.list[str] = []

        # Load default threat indicators
        self._load_default_indicators()

    def _load_default_indicators(self):
        """Load default threat indicators"""

        # Known malicious IPs (examples)
        malicious_ips = [
            "192.168.1.100",  # Example internal scanner
            "10.0.0.50",  # Example compromised host
        ]

        for ip in malicious_ips:
            self.add_threat_indicator(
                ThreatIntelligence(
                    indicator=ip,
                    indicator_type="ip",
                    threat_type=ThreatCategory.MALWARE,
                    confidence=0.8,
                    source="internal_detection",
                    description="Known malicious IP from internal detection",
                    created_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(days=30),
                )
            )

        # Suspicious domains
        suspicious_domains = ["malicious-site.example.com", "phishing-domain.test"]

        for domain in suspicious_domains:
            self.add_threat_indicator(
                ThreatIntelligence(
                    indicator=domain,
                    indicator_type="domain",
                    threat_type=ThreatCategory.DATA_EXFILTRATION,
                    confidence=0.9,
                    source="threat_feed",
                    description="Known phishing domain",
                    created_at=datetime.now(),
                    expires_at=datetime.now() + timedelta(days=7),
                )
            )

        # Known attack patterns
        attack_patterns = [
            "SELECT * FROM users WHERE",  # SQL injection
            "'; DROP TABLE",  # SQL injection
            "<script>alert(",  # XSS
            "../../etc/passwd",  # Path traversal
        ]

        for pattern in attack_patterns:
            self.add_threat_indicator(
                ThreatIntelligence(
                    indicator=pattern,
                    indicator_type="pattern",
                    threat_type=ThreatCategory.INJECTION_ATTACK,
                    confidence=0.95,
                    source="signature_detection",
                    description="Known attack pattern",
                    created_at=datetime.now(),
                )
            )

    def add_threat_indicator(self, threat_intel: ThreatIntelligence):
        """Add threat intelligence indicator"""
        self.threat_indicators[threat_intel.indicator] = threat_intel
        print(
            f"Added threat indicator: {threat_intel.indicator} ({threat_intel.threat_type.value})"
        )

    def check_threat_indicators(
        self, data: builtins.dict[str, Any]
    ) -> builtins.list[ThreatIntelligence]:
        """Check data against threat indicators"""
        matches = []

        # Check IP addresses
        source_ip = data.get("source_ip", "")
        if source_ip in self.threat_indicators:
            intel = self.threat_indicators[source_ip]
            if intel.is_valid():
                matches.append(intel)

        # Check domains in URLs
        url = data.get("url", "")
        for indicator, intel in self.threat_indicators.items():
            if intel.indicator_type == "domain" and intel.is_valid():
                if indicator in url:
                    matches.append(intel)

        # Check patterns in request data
        request_body = str(data.get("request_body", ""))
        request_params = str(data.get("request_params", ""))
        combined_request = f"{request_body} {request_params}".lower()

        for indicator, intel in self.threat_indicators.items():
            if intel.indicator_type == "pattern" and intel.is_valid():
                if indicator.lower() in combined_request:
                    matches.append(intel)

        return matches

    async def update_threat_feeds(self):
        """Update threat intelligence from external feeds"""
        # This would integrate with real threat intel providers
        # For demo purposes, we'll simulate updates

        print("Updating threat intelligence feeds...")

        # Simulate adding new threat indicators
        new_indicators = [
            ThreatIntelligence(
                indicator="198.51.100.42",
                indicator_type="ip",
                threat_type=ThreatCategory.BRUTE_FORCE,
                confidence=0.85,
                source="external_feed",
                description="Brute force attack source",
                created_at=datetime.now(),
                expires_at=datetime.now() + timedelta(hours=24),
            )
        ]

        for indicator in new_indicators:
            self.add_threat_indicator(indicator)

        # Clean expired indicators
        expired_indicators = []
        for key, intel in self.threat_indicators.items():
            if not intel.is_valid():
                expired_indicators.append(key)

        for key in expired_indicators:
            del self.threat_indicators[key]
            print(f"Removed expired threat indicator: {key}")

    def get_threat_summary(self) -> builtins.dict[str, Any]:
        """Get threat intelligence summary"""
        active_indicators = [intel for intel in self.threat_indicators.values() if intel.is_valid()]

        by_type = defaultdict(int)
        by_category = defaultdict(int)

        for intel in active_indicators:
            by_type[intel.indicator_type] += 1
            by_category[intel.threat_type.value] += 1

        return {
            "total_indicators": len(active_indicators),
            "by_type": dict(by_type),
            "by_category": dict(by_category),
            "last_updated": datetime.now().isoformat(),
        }


class IncidentResponseEngine:
    """
    Automated incident response and orchestration

    Features:
    - Automated incident creation
    - Response playbook execution
    - Escalation management
    - Remediation actions
    """

    def __init__(self):
        self.incidents: builtins.dict[str, SecurityIncident] = {}
        self.response_playbooks: builtins.dict[ThreatCategory, builtins.list[str]] = {}
        self.incident_counter = 0

        # Initialize default playbooks
        self._create_default_playbooks()

        # Metrics
        if ANALYTICS_AVAILABLE:
            self.incidents_created = Counter(
                "marty_security_incidents_total",
                "Security incidents created",
                ["category", "severity"],
            )
            self.incident_response_time = Histogram(
                "marty_incident_response_time_seconds", "Incident response time"
            )

    def _create_default_playbooks(self):
        """Create default incident response playbooks"""

        self.response_playbooks[ThreatCategory.BRUTE_FORCE] = [
            "Block source IP temporarily",
            "Increase authentication monitoring",
            "Alert security team",
            "Review affected accounts",
            "Implement additional rate limiting",
        ]

        self.response_playbooks[ThreatCategory.INJECTION_ATTACK] = [
            "Block suspicious requests",
            "Review application logs",
            "Check database integrity",
            "Alert development team",
            "Implement input validation fixes",
        ]

        self.response_playbooks[ThreatCategory.DATA_EXFILTRATION] = [
            "Block external connections",
            "Review access logs",
            "Check data integrity",
            "Alert legal and compliance teams",
            "Initiate forensic investigation",
        ]

        self.response_playbooks[ThreatCategory.PRIVILEGE_ESCALATION] = [
            "Revoke elevated permissions",
            "Audit privilege assignments",
            "Review system configurations",
            "Alert administrators",
            "Implement additional access controls",
        ]

        self.response_playbooks[ThreatCategory.ANOMALOUS_BEHAVIOR] = [
            "Monitor user activities closely",
            "Review user permissions",
            "Check for lateral movement",
            "Alert security analysts",
            "Implement behavioral analysis",
        ]

    def create_incident(
        self,
        title: str,
        description: str,
        threat_level: ThreatLevel,
        category: ThreatCategory,
        events: builtins.list[SecurityEvent],
    ) -> SecurityIncident:
        """Create new security incident"""

        self.incident_counter += 1
        incident_id = f"INC-{datetime.now().strftime('%Y%m%d')}-{self.incident_counter:04d}"

        incident = SecurityIncident(
            incident_id=incident_id,
            title=title,
            description=description,
            threat_level=threat_level,
            category=category,
            status=IncidentStatus.DETECTED,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            events=events,
            affected_services={event.service_name for event in events},
        )

        self.incidents[incident_id] = incident

        # Update metrics
        if ANALYTICS_AVAILABLE:
            self.incidents_created.labels(
                category=category.value, severity=threat_level.value
            ).inc()

        print(f"Created security incident: {incident_id} - {title}")

        # Trigger automated response
        asyncio.create_task(self._execute_response_playbook(incident))

        return incident

    async def _execute_response_playbook(self, incident: SecurityIncident):
        """Execute automated response playbook"""

        playbook = self.response_playbooks.get(incident.category, [])
        if not playbook:
            print(f"No playbook defined for {incident.category.value}")
            return

        print(f"Executing response playbook for {incident.incident_id}")

        for action in playbook:
            print(f"  - {action}")
            incident.response_actions.append(f"{datetime.now().isoformat()}: {action}")

            # Simulate action execution time
            await asyncio.sleep(0.1)

            # Specific automated actions
            if "Block source IP" in action:
                await self._block_source_ips(incident)
            elif "Alert" in action:
                await self._send_alert(incident, action)
            elif "Review" in action:
                await self._trigger_investigation(incident, action)

        # Update incident status
        incident.status = IncidentStatus.INVESTIGATING
        incident.updated_at = datetime.now()

        print(f"Completed automated response for {incident.incident_id}")

    async def _block_source_ips(self, incident: SecurityIncident):
        """Block source IPs involved in the incident"""
        source_ips = set()

        for event in incident.events:
            if event.source_ip:
                source_ips.add(event.source_ip)

        for ip in source_ips:
            print(f"    Blocking IP: {ip}")
            # This would integrate with firewall/WAF to block IPs
            incident.response_actions.append(f"Blocked IP: {ip}")

    async def _send_alert(self, incident: SecurityIncident, action: str):
        """Send alert to appropriate teams"""
        print(f"    Sending alert: {action}")

        # This would integrate with alerting systems (PagerDuty, Slack, etc.)

        # Simulate alert sending
        incident.response_actions.append(f"Alert sent: {action}")

    async def _trigger_investigation(self, incident: SecurityIncident, action: str):
        """Trigger investigation activities"""
        print(f"    Triggering investigation: {action}")

        # This would create investigation tasks
        incident.response_actions.append(f"Investigation triggered: {action}")

    def update_incident(
        self,
        incident_id: str,
        status: IncidentStatus | None = None,
        assigned_to: str | None = None,
        notes: str | None = None,
    ) -> bool:
        """Update incident details"""

        if incident_id not in self.incidents:
            return False

        incident = self.incidents[incident_id]

        if status:
            incident.status = status
        if assigned_to:
            incident.assigned_to = assigned_to
        if notes:
            incident.response_actions.append(f"{datetime.now().isoformat()}: {notes}")

        incident.updated_at = datetime.now()

        print(f"Updated incident {incident_id}")
        return True

    def get_active_incidents(self) -> builtins.list[SecurityIncident]:
        """Get all active incidents"""
        return [
            incident
            for incident in self.incidents.values()
            if incident.status not in [IncidentStatus.RESOLVED, IncidentStatus.FALSE_POSITIVE]
        ]

    def get_incident_summary(self) -> builtins.dict[str, Any]:
        """Get incident summary statistics"""
        incidents = list(self.incidents.values())

        by_status = defaultdict(int)
        by_severity = defaultdict(int)
        by_category = defaultdict(int)

        for incident in incidents:
            by_status[incident.status.value] += 1
            by_severity[incident.threat_level.value] += 1
            by_category[incident.category.value] += 1

        return {
            "total_incidents": len(incidents),
            "active_incidents": len(self.get_active_incidents()),
            "by_status": dict(by_status),
            "by_severity": dict(by_severity),
            "by_category": dict(by_category),
        }


class ThreatDetectionManager:
    """
    Complete threat detection and response system

    Orchestrates all threat detection components:
    - Anomaly detection
    - Threat intelligence
    - Incident response
    - Security event correlation
    """

    def __init__(self):
        self.anomaly_detector = AnomalyDetector()
        self.threat_intel = ThreatIntelligenceEngine()
        self.incident_response = IncidentResponseEngine()

        self.event_correlation_window = timedelta(minutes=5)
        self.recent_events: deque = deque(maxlen=10000)

        # Metrics
        if ANALYTICS_AVAILABLE:
            self.events_processed = Counter(
                "marty_security_events_processed_total",
                "Security events processed",
                ["service", "event_type"],
            )

    async def process_security_event(
        self, event_data: builtins.dict[str, Any]
    ) -> SecurityEvent | None:
        """Process incoming security event"""

        # Create security event
        event = SecurityEvent(
            event_id=f"EVT-{int(time.time() * 1000)}",
            timestamp=datetime.now(),
            source_ip=event_data.get("source_ip", ""),
            user_id=event_data.get("user_id"),
            service_name=event_data.get("service_name", "unknown"),
            event_type=event_data.get("event_type", "unknown"),
            description=event_data.get("description", ""),
            severity=ThreatLevel(event_data.get("severity", "low")),
            category=ThreatCategory(event_data.get("category", "anomalous_behavior")),
            raw_data=event_data,
        )

        # Check against threat intelligence
        threat_matches = self.threat_intel.check_threat_indicators(event_data)
        if threat_matches:
            event.threat_indicators = [match.indicator for match in threat_matches]
            # Escalate severity if threat intel matches
            if any(match.confidence > 0.8 for match in threat_matches):
                if event.severity == ThreatLevel.LOW:
                    event.severity = ThreatLevel.MEDIUM
                elif event.severity == ThreatLevel.MEDIUM:
                    event.severity = ThreatLevel.HIGH

        # Store event
        self.recent_events.append(event)

        # Update metrics
        if ANALYTICS_AVAILABLE:
            self.events_processed.labels(
                service=event.service_name, event_type=event.event_type
            ).inc()

        # Check for anomalies
        await self._check_anomalies(event)

        # Check for correlated events
        await self._check_event_correlation(event)

        return event

    async def _check_anomalies(self, event: SecurityEvent):
        """Check for various types of anomalies"""

        # Statistical anomaly detection for metrics
        if "response_time" in event.raw_data:
            response_time = float(event.raw_data["response_time"])
            is_anomaly, score = self.anomaly_detector.detect_statistical_anomaly(
                event.service_name, "response_time", response_time
            )

            if is_anomaly:
                await self._create_anomaly_incident(
                    event,
                    "Response time anomaly detected",
                    f"Response time {response_time}ms is {score:.2f} standard deviations from normal",
                    ThreatLevel.MEDIUM if score > 4.0 else ThreatLevel.LOW,
                )

        # Error rate anomaly
        if "error_rate" in event.raw_data:
            error_rate = float(event.raw_data["error_rate"])
            is_anomaly, score = self.anomaly_detector.detect_statistical_anomaly(
                event.service_name, "error_rate", error_rate
            )

            if is_anomaly:
                await self._create_anomaly_incident(
                    event,
                    "Error rate anomaly detected",
                    f"Error rate {error_rate}% is {score:.2f} standard deviations from normal",
                    ThreatLevel.HIGH if score > 4.0 else ThreatLevel.MEDIUM,
                )

    async def _check_event_correlation(self, event: SecurityEvent):
        """Check for correlated security events"""

        # Find recent events from same source
        cutoff_time = datetime.now() - self.event_correlation_window
        related_events = [
            e
            for e in self.recent_events
            if (
                e.timestamp >= cutoff_time
                and e.source_ip == event.source_ip
                and e.event_id != event.event_id
            )
        ]

        if len(related_events) >= 5:  # Multiple events from same source
            # Check for brute force pattern
            auth_events = [e for e in related_events if "auth" in e.event_type.lower()]
            if len(auth_events) >= 3:
                await self._create_correlation_incident(
                    [event] + auth_events,
                    "Potential brute force attack",
                    f"Multiple authentication attempts from {event.source_ip}",
                    ThreatLevel.HIGH,
                    ThreatCategory.BRUTE_FORCE,
                )

            # Check for reconnaissance pattern
            unique_endpoints = {e.raw_data.get("endpoint", "") for e in related_events}
            if len(unique_endpoints) >= 10:
                await self._create_correlation_incident(
                    [event] + related_events,
                    "Potential reconnaissance activity",
                    f"Multiple endpoints accessed from {event.source_ip}",
                    ThreatLevel.MEDIUM,
                    ThreatCategory.ANOMALOUS_BEHAVIOR,
                )

        # Check for privilege escalation sequence
        if "admin" in event.raw_data.get("endpoint", "").lower():
            recent_user_events = [
                e
                for e in related_events
                if e.user_id == event.user_id and "user" in e.raw_data.get("endpoint", "").lower()
            ]

            if recent_user_events:
                await self._create_correlation_incident(
                    [event] + recent_user_events,
                    "Potential privilege escalation",
                    f"User {event.user_id} accessed admin endpoints after user endpoints",
                    ThreatLevel.HIGH,
                    ThreatCategory.PRIVILEGE_ESCALATION,
                )

    async def _create_anomaly_incident(
        self, event: SecurityEvent, title: str, description: str, severity: ThreatLevel
    ):
        """Create incident for detected anomaly"""

        incident = self.incident_response.create_incident(
            title=title,
            description=description,
            threat_level=severity,
            category=ThreatCategory.ANOMALOUS_BEHAVIOR,
            events=[event],
        )

        print(f"Created anomaly incident: {incident.incident_id}")

    async def _create_correlation_incident(
        self,
        events: builtins.list[SecurityEvent],
        title: str,
        description: str,
        severity: ThreatLevel,
        category: ThreatCategory,
    ):
        """Create incident for correlated events"""

        incident = self.incident_response.create_incident(
            title=title,
            description=description,
            threat_level=severity,
            category=category,
            events=events,
        )

        print(f"Created correlation incident: {incident.incident_id}")

    async def start_monitoring(self):
        """Start continuous threat monitoring"""
        print("Starting threat detection monitoring...")

        # Update threat feeds periodically
        while True:
            try:
                await self.threat_intel.update_threat_feeds()
                await asyncio.sleep(3600)  # Update every hour
            except Exception as e:
                print(f"Error updating threat feeds: {e}")
                await asyncio.sleep(300)  # Retry in 5 minutes

    def get_security_status(self) -> builtins.dict[str, Any]:
        """Get overall security status"""
        return {
            "threat_detection_active": True,
            "anomaly_detector": self.anomaly_detector.get_baseline_summary(),
            "threat_intelligence": self.threat_intel.get_threat_summary(),
            "incidents": self.incident_response.get_incident_summary(),
            "recent_events_count": len(self.recent_events),
        }


# Example usage
async def main():
    """Example usage of threat detection system"""

    # Initialize threat detection
    threat_manager = ThreatDetectionManager()

    # Start monitoring in background
    monitoring_task = asyncio.create_task(threat_manager.start_monitoring())

    # Simulate security events
    test_events = [
        {
            "source_ip": "192.168.1.100",
            "user_id": "user123",
            "service_name": "user-service",
            "event_type": "authentication_failure",
            "description": "Failed login attempt",
            "severity": "medium",
            "category": "authentication_attack",
            "endpoint": "/api/v1/auth/login",
        },
        {
            "source_ip": "192.168.1.100",
            "user_id": "user123",
            "service_name": "user-service",
            "event_type": "authentication_failure",
            "description": "Failed login attempt",
            "severity": "medium",
            "category": "authentication_attack",
            "endpoint": "/api/v1/auth/login",
        },
        {
            "source_ip": "192.168.1.100",
            "service_name": "api-gateway",
            "event_type": "suspicious_request",
            "description": "SQL injection attempt",
            "severity": "high",
            "category": "injection_attack",
            "endpoint": "/api/v1/users",
            "request_body": "SELECT * FROM users WHERE id = '1' OR '1'='1'",
        },
        {
            "source_ip": "10.0.0.50",
            "service_name": "payment-service",
            "event_type": "data_access",
            "description": "Unusual data access pattern",
            "severity": "medium",
            "category": "anomalous_behavior",
            "response_time": 5000,  # Unusually high response time
        },
    ]

    print("Processing test security events...")
    for event_data in test_events:
        event = await threat_manager.process_security_event(event_data)
        if event:
            print(f"Processed event: {event.event_id} - {event.description}")

        # Small delay between events
        await asyncio.sleep(1)

    # Wait a bit for correlation analysis
    await asyncio.sleep(2)

    # Show security status
    status = threat_manager.get_security_status()
    print("\n=== SECURITY STATUS ===")
    print(f"Active incidents: {status['incidents']['active_incidents']}")
    print(f"Total threat indicators: {status['threat_intelligence']['total_indicators']}")
    print(f"Baseline services: {status['anomaly_detector']['total_services']}")

    # Show active incidents
    active_incidents = threat_manager.incident_response.get_active_incidents()
    print(f"\n=== ACTIVE INCIDENTS ({len(active_incidents)}) ===")
    for incident in active_incidents:
        print(f"{incident.incident_id}: {incident.title} ({incident.threat_level.value})")
        print(f"  Status: {incident.status.value}")
        print(f"  Events: {len(incident.events)}")
        print(f"  Actions: {len(incident.response_actions)}")

    # Stop monitoring
    monitoring_task.cancel()


if __name__ == "__main__":
    asyncio.run(main())
