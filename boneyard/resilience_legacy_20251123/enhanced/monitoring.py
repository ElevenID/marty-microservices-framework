"""
Monitoring and health checking for resilience patterns.

Ported from Marty's resilience framework to provide comprehensive
monitoring capabilities for microservices.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ResilienceHealthCheck:
    """Health check result for resilience components."""

    component: str
    healthy: bool
    message: str
    timestamp: float = field(default_factory=time.time)
    metrics: dict[str, Any] = field(default_factory=dict)


class ResilienceMonitor:
    """Monitor for resilience patterns and components."""

    def __init__(self, name: str):
        self.name = name
        self.health_checks: list[ResilienceHealthCheck] = []
        self.circuit_breakers: dict[str, Any] = {}
        self.retry_managers: dict[str, Any] = {}

    def add_health_check(self, check: ResilienceHealthCheck) -> None:
        """Add a health check result."""
        self.health_checks.append(check)
        # Keep only last 100 checks
        if len(self.health_checks) > 100:
            self.health_checks.pop(0)

    def get_latest_health_status(self) -> ResilienceHealthCheck | None:
        """Get the latest health check result."""
        return self.health_checks[-1] if self.health_checks else None

    def register_circuit_breaker(self, name: str, circuit_breaker: Any) -> None:
        """Register a circuit breaker for monitoring."""
        self.circuit_breakers[name] = circuit_breaker

    def register_retry_manager(self, name: str, retry_manager: Any) -> None:
        """Register a retry manager for monitoring."""
        self.retry_managers[name] = retry_manager

    def get_status_summary(self) -> dict[str, Any]:
        """Get comprehensive status summary."""
        return {
            "name": self.name,
            "timestamp": time.time(),
            "circuit_breakers": len(self.circuit_breakers),
            "retry_managers": len(self.retry_managers),
            "recent_health_checks": len(self.health_checks),
            "latest_health": self.get_latest_health_status(),
        }


# Global monitor instance
_global_monitor: ResilienceMonitor | None = None


def get_global_monitor() -> ResilienceMonitor:
    """Get the global resilience monitor."""
    global _global_monitor  # noqa: PLW0603
    if _global_monitor is None:
        _global_monitor = ResilienceMonitor("global")
    return _global_monitor


def register_circuit_breaker_for_monitoring(name: str, circuit_breaker: Any) -> None:
    """Register a circuit breaker for monitoring."""
    monitor = get_global_monitor()
    monitor.register_circuit_breaker(name, circuit_breaker)


def register_retry_manager_for_monitoring(name: str, retry_manager: Any) -> None:
    """Register a retry manager for monitoring."""
    monitor = get_global_monitor()
    monitor.register_retry_manager(name, retry_manager)


def get_resilience_health_status() -> ResilienceHealthCheck | None:
    """Get current resilience health status."""
    monitor = get_global_monitor()
    return monitor.get_latest_health_status()


def generate_resilience_health_report() -> dict[str, Any]:
    """Generate comprehensive resilience health report."""
    monitor = get_global_monitor()
    return monitor.get_status_summary()
