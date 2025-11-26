"""
Threat Detection Ports

Interfaces for threat detection and vulnerability scanning.
"""

from __future__ import annotations

import builtins
from abc import ABC, abstractmethod
from typing import Any

from ..domain.models.threat import (
    SecurityEvent,
    ThreatDetectionResult,
    UserBehaviorProfile,
    ServiceBehaviorProfile,
    AnomalyDetectionResult,
)
from ..domain.models.vulnerability import SecurityVulnerability


class IThreatDetector(ABC):
    """Interface for threat detection service."""

    @abstractmethod
    async def analyze_event(self, event: SecurityEvent) -> ThreatDetectionResult:
        """Analyze a security event for threats."""
        pass

    @abstractmethod
    async def analyze_user_behavior(
        self, user_id: str, recent_events: builtins.list[SecurityEvent]
    ) -> UserBehaviorProfile:
        """Analyze user behavior for anomalies."""
        pass

    @abstractmethod
    async def analyze_service_behavior(
        self, service_name: str, recent_events: builtins.list[SecurityEvent]
    ) -> ServiceBehaviorProfile:
        """Analyze service behavior for anomalies."""
        pass

    @abstractmethod
    async def detect_anomalies(self, data: builtins.dict[str, Any]) -> AnomalyDetectionResult:
        """Detect anomalies in generic data."""
        pass

    @abstractmethod
    async def get_threat_statistics(self) -> builtins.dict[str, Any]:
        """Get threat detection statistics."""
        pass


class IVulnerabilityScanner(ABC):
    """Interface for vulnerability scanning service."""

    @abstractmethod
    def scan_code(self, code: str, file_path: str = "") -> builtins.list[SecurityVulnerability]:
        """Scan code for vulnerabilities."""
        pass

    @abstractmethod
    def scan_configuration(
        self, config: builtins.dict[str, Any]
    ) -> builtins.list[SecurityVulnerability]:
        """Scan configuration for vulnerabilities."""
        pass

    @abstractmethod
    def scan_dependencies(
        self, dependencies: builtins.list[builtins.dict[str, Any]]
    ) -> builtins.list[SecurityVulnerability]:
        """Scan dependencies for vulnerabilities."""
        pass

    @abstractmethod
    def get_vulnerability_summary(self) -> builtins.dict[str, Any]:
        """Get vulnerability scan summary."""
        pass
