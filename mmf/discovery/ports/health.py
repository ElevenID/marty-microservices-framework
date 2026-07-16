"""
Health Check Port

Defines the interface for health check implementations.
"""

import builtins
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from mmf.discovery.domain.models import ServiceInstance


class HealthCheckType(Enum):
    """Health check types."""

    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    UDP = "udp"
    GRPC = "grpc"
    CUSTOM = "custom"
    COMPOSITE = "composite"


class HealthCheckStatus(Enum):
    """Health check status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    WARNING = "warning"
    UNKNOWN = "unknown"
    TIMEOUT = "timeout"


@dataclass
class HealthCheckConfig:
    """Configuration for health checks."""

    # Basic configuration
    check_type: HealthCheckType = HealthCheckType.HTTP
    interval: float = 30.0
    timeout: float = 5.0
    retries: int = 3
    retry_delay: float = 1.0

    # HTTP/HTTPS specific
    http_method: str = "GET"
    http_path: str = "/health"
    http_headers: builtins.dict[str, str] = field(default_factory=dict)
    expected_status_codes: builtins.list[int] = field(default_factory=lambda: [200])
    expected_response_body: str | None = None
    follow_redirects: bool = False
    verify_ssl: bool = True

    # TCP/UDP specific
    tcp_port: int | None = None
    udp_port: int | None = None
    send_data: bytes | None = None
    expected_response: bytes | None = None

    # Custom check specific
    custom_check_function: Callable | None = None
    custom_check_args: builtins.dict[str, Any] = field(default_factory=dict)

    # Thresholds
    healthy_threshold: int = 2  # Consecutive successes to mark healthy
    unhealthy_threshold: int = 3  # Consecutive failures to mark unhealthy
    warning_threshold: float = 2.0  # Response time threshold for warning

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: float = 60.0

    # Grace periods
    startup_grace_period: float = 60.0  # Grace period after service start
    shutdown_grace_period: float = 30.0  # Grace period during shutdown


@dataclass
class HealthCheckResult:
    """Result of a health check."""

    status: HealthCheckStatus
    response_time: float
    timestamp: float
    message: str = ""
    details: builtins.dict[str, Any] = field(default_factory=dict)

    # HTTP specific
    http_status_code: int | None = None
    http_response_body: str | None = None

    # Network specific
    network_error: str | None = None

    def is_healthy(self) -> bool:
        """Check if result indicates healthy status."""
        return self.status == HealthCheckStatus.HEALTHY

    def is_warning(self) -> bool:
        """Check if result indicates warning status."""
        return self.status == HealthCheckStatus.WARNING


class IHealthChecker(ABC):
    """Abstract health checker interface."""

    @abstractmethod
    async def check_health(self, instance: ServiceInstance) -> HealthCheckResult:
        """Perform health check on service instance."""
