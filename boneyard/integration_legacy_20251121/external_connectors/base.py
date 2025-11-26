"""
Base External System Connector

Abstract base class and common functionality for external system connectors.
"""

import time
from abc import ABC, abstractmethod

from .config import ExternalSystemConfig, IntegrationRequest, IntegrationResponse


class ExternalSystemConnector(ABC):
    """Abstract base class for external system connectors."""

    def __init__(self, config: ExternalSystemConfig):
        """Initialize connector with configuration."""
        self.config = config
        self.connected = False
        self.circuit_breaker_state = "closed"
        self.failure_count = 0
        self.last_failure_time = None

        # Metrics
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_latency": 0.0,
        }

    @abstractmethod
    async def connect(self) -> bool:
        """Establish connection to external system."""

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from external system."""

    @abstractmethod
    async def execute_request(self, request: IntegrationRequest) -> IntegrationResponse:
        """Execute request against external system."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check health of external system."""

    def is_circuit_breaker_open(self) -> bool:
        """Check if circuit breaker is open."""
        if self.circuit_breaker_state == "open":
            if self.last_failure_time:
                elapsed = time.time() - self.last_failure_time
                if elapsed > self.config.recovery_timeout:
                    self.circuit_breaker_state = "half_open"
                    return False
            return True
        return False

    def record_success(self):
        """Record successful request."""
        self.failure_count = 0
        if self.circuit_breaker_state == "half_open":
            self.circuit_breaker_state = "closed"

        self.metrics["successful_requests"] += 1

    def record_failure(self):
        """Record failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.config.failure_threshold:
            self.circuit_breaker_state = "open"

        self.metrics["failed_requests"] += 1

    def get_average_latency(self) -> float:
        """Get average request latency."""
        if self.metrics["total_requests"] > 0:
            return self.metrics["total_latency"] / self.metrics["total_requests"]
        return 0.0

    def get_success_rate(self) -> float:
        """Get success rate percentage."""
        total = self.metrics["total_requests"]
        if total > 0:
            return (self.metrics["successful_requests"] / total) * 100
        return 0.0

    def reset_metrics(self):
        """Reset connector metrics."""
        self.metrics = {
            "total_requests": 0,
            "successful_requests": 0,
            "failed_requests": 0,
            "total_latency": 0.0,
        }
