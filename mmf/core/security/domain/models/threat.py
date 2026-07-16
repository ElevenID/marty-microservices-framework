"""
Threat Detection Domain Models

Domain models for threat detection and security event processing.
"""

from __future__ import annotations

import builtins
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from mmf.core.domain.audit_types import SecurityEventType, SecurityThreatLevel


class ThreatType(Enum):
    """Types of security threats."""

    INJECTION = "injection"
    XSS = "xss"
    INTRUSION = "intrusion"
    BRUTE_FORCE = "brute_force"
    DOS = "dos"
    RECONNAISSANCE = "reconnaissance"
    MALWARE = "malware"
    DATA_LEAK = "data_leak"
    UNKNOWN = "unknown"


@dataclass
class SecurityEvent:
    """Security event for threat analysis."""

    event_id: str
    event_type: SecurityEventType | str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    service_name: str = ""
    user_id: str | None = None
    source_ip: str | None = None
    user_agent: str | None = None
    endpoint: str | None = None
    method: str | None = None
    status_code: int | None = None
    response_time_ms: float | None = None
    severity: SecurityThreatLevel = SecurityThreatLevel.LOW
    details: builtins.dict[str, Any] = field(default_factory=dict)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class ThreatDetectionResult:
    """Result of threat detection analysis."""

    event: SecurityEvent
    is_threat: bool
    threat_score: float  # 0.0 to 1.0
    threat_level: SecurityThreatLevel
    detected_threats: builtins.list[str] = field(default_factory=list)
    risk_factors: builtins.list[str] = field(default_factory=list)
    recommended_actions: builtins.list[str] = field(default_factory=list)
    correlated_events: builtins.list[str] = field(default_factory=list)
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class UserBehaviorProfile:
    """User behavior profile for anomaly detection."""

    user_id: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Access patterns
    typical_access_hours: builtins.list[int] = field(default_factory=list)
    typical_services: builtins.list[str] = field(default_factory=list)
    typical_endpoints: builtins.list[str] = field(default_factory=list)
    typical_ip_ranges: builtins.list[str] = field(default_factory=list)

    # Behavioral metrics
    avg_requests_per_hour: float = 0.0
    avg_session_duration: float = 0.0
    avg_response_time: float = 0.0

    # Risk factors
    failed_login_rate: float = 0.0
    privilege_escalation_attempts: int = 0
    unusual_access_count: int = 0

    # ML features
    feature_vector: builtins.list[float] = field(default_factory=list)
    anomaly_score: float = 0.0


@dataclass
class ServiceBehaviorProfile:
    """Service behavior profile for system anomaly detection."""

    service_name: str
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Performance metrics
    avg_response_time: float = 0.0
    avg_throughput: float = 0.0
    avg_error_rate: float = 0.0
    avg_cpu_usage: float = 0.0
    avg_memory_usage: float = 0.0

    # Traffic patterns
    typical_request_patterns: builtins.dict[str, float] = field(default_factory=dict)
    typical_user_agents: builtins.list[str] = field(default_factory=list)
    typical_source_countries: builtins.list[str] = field(default_factory=list)

    # Security metrics
    auth_failure_rate: float = 0.0
    suspicious_request_rate: float = 0.0
    malicious_ip_access_rate: float = 0.0

    # ML features
    feature_vector: builtins.list[float] = field(default_factory=list)
    anomaly_score: float = 0.0


@dataclass
class AnomalyDetectionResult:
    """Result of anomaly detection analysis."""

    is_anomaly: bool
    anomaly_score: float  # -1.0 to 1.0 (Isolation Forest) or distance metric
    confidence: float  # 0.0 to 1.0
    detected_anomalies: builtins.list[str] = field(default_factory=list)
    baseline_deviation: builtins.dict[str, float] = field(default_factory=dict)
    analyzed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
