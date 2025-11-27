"""
Integration Domain Services
"""

import time

from mmf_new.framework.integration.domain.exceptions import CircuitBreakerOpenError
from mmf_new.framework.integration.domain.models import (
    CircuitBreakerState,
    CircuitBreakerStatus,
    ConnectionConfig,
)


class CircuitBreakerService:
    """Domain service for managing circuit breaker state."""

    def __init__(self):
        self._breakers: dict[str, CircuitBreakerStatus] = {}

    def get_status(self, system_id: str) -> CircuitBreakerStatus:
        """Get circuit breaker status for a system."""
        if system_id not in self._breakers:
            self._breakers[system_id] = CircuitBreakerStatus(
                state=CircuitBreakerState.CLOSED,
                failure_count=0,
                last_failure_time=None,
                last_success_time=None,
            )
        return self._breakers[system_id]

    def check_availability(self, system_id: str, config: ConnectionConfig) -> None:
        """
        Check if request can be allowed through.
        Raises CircuitBreakerOpenError if circuit is open.
        """
        if not config.circuit_breaker_enabled:
            return

        status = self.get_status(system_id)

        if status.state == CircuitBreakerState.OPEN:
            if status.last_failure_time:
                elapsed = time.time() - status.last_failure_time
                if elapsed > config.recovery_timeout:
                    # Transition to half-open to test recovery
                    status.state = CircuitBreakerState.HALF_OPEN
                    return

            raise CircuitBreakerOpenError(
                f"Circuit breaker for system {system_id} is OPEN. "
                f"Last failure: {status.last_failure_time}"
            )

    def record_success(self, system_id: str) -> None:
        """Record a successful request."""
        status = self.get_status(system_id)
        status.last_success_time = time.time()
        status.failure_count = 0

        if status.state == CircuitBreakerState.HALF_OPEN:
            status.state = CircuitBreakerState.CLOSED

    def record_failure(self, system_id: str, config: ConnectionConfig) -> None:
        """Record a failed request."""
        if not config.circuit_breaker_enabled:
            return

        status = self.get_status(system_id)
        status.last_failure_time = time.time()
        status.failure_count += 1

        if status.failure_count >= config.failure_threshold:
            status.state = CircuitBreakerState.OPEN


class MetricsTracker:
    """Domain service for tracking integration metrics."""

    def __init__(self):
        self._metrics: dict[str, dict[str, float]] = {}

    def record_request(self, system_id: str, latency_ms: float, success: bool) -> None:
        """Record request metrics."""
        if system_id not in self._metrics:
            self._metrics[system_id] = {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_latency": 0.0,
            }

        metrics = self._metrics[system_id]
        metrics["total_requests"] += 1
        metrics["total_latency"] += latency_ms

        if success:
            metrics["successful_requests"] += 1
        else:
            metrics["failed_requests"] += 1

    def get_metrics(self, system_id: str) -> dict[str, float]:
        """Get metrics for a system."""
        return self._metrics.get(
            system_id,
            {
                "total_requests": 0,
                "successful_requests": 0,
                "failed_requests": 0,
                "total_latency": 0.0,
            },
        )
