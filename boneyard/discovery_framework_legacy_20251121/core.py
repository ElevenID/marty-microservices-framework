"""
Core Service Discovery Abstractions

Fundamental classes and interfaces for service discovery including
service instances, metadata, health status, and configuration.
"""

import builtins
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class ServiceStatus(Enum):
    """Service instance status."""

    UNKNOWN = "unknown"
    STARTING = "starting"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    CRITICAL = "critical"
    MAINTENANCE = "maintenance"
    TERMINATING = "terminating"
    TERMINATED = "terminated"


class HealthStatus(Enum):
    """Health check status."""

    UNKNOWN = "unknown"
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    TIMEOUT = "timeout"
    ERROR = "error"


class ServiceInstanceType(Enum):
    """Service instance types."""

    HTTP = "http"
    HTTPS = "https"
    TCP = "tcp"
    UDP = "udp"
    GRPC = "grpc"
    WEBSOCKET = "websocket"


@dataclass
class ServiceEndpoint:
    """Service endpoint definition."""

    host: str
    port: int
    protocol: ServiceInstanceType = ServiceInstanceType.HTTP
    path: str = ""

    # SSL/TLS configuration
    ssl_enabled: bool = False
    ssl_verify: bool = True
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None

    # Connection settings
    connection_timeout: float = 5.0
    read_timeout: float = 30.0

    def get_url(self) -> str:
        """Get full URL for the endpoint."""
        scheme = "https" if self.ssl_enabled else "http"
        if self.protocol == ServiceInstanceType.HTTPS:
            scheme = "https"
        elif self.protocol in [
            ServiceInstanceType.TCP,
            ServiceInstanceType.UDP,
            ServiceInstanceType.GRPC,
        ]:
            return f"{self.protocol.value}://{self.host}:{self.port}"

        url = f"{scheme}://{self.host}:{self.port}"
        if self.path:
            url += self.path if self.path.startswith("/") else f"/{self.path}"

        return url

    def __str__(self) -> str:
        return self.get_url()


@dataclass
class ServiceMetadata:
    """Service instance metadata."""

    # Basic information
    version: str = "1.0.0"
    environment: str = "production"
    region: str = "default"
    availability_zone: str = "default"

    # Deployment information
    deployment_id: str | None = None
    build_id: str | None = None
    git_commit: str | None = None

    # Resource information
    cpu_cores: int | None = None
    memory_mb: int | None = None
    disk_gb: int | None = None

    # Network information
    public_ip: str | None = None
    private_ip: str | None = None
    subnet: str | None = None

    # Service configuration
    max_connections: int | None = None
    request_timeout: float | None = None

    # Custom metadata
    tags: builtins.set[str] = field(default_factory=set)
    labels: builtins.dict[str, str] = field(default_factory=dict)
    annotations: builtins.dict[str, str] = field(default_factory=dict)

    def add_tag(self, tag: str):
        """Add a tag."""
        self.tags.add(tag)

    def remove_tag(self, tag: str):
        """Remove a tag."""
        self.tags.discard(tag)

    def has_tag(self, tag: str) -> bool:
        """Check if tag exists."""
        return tag in self.tags

    def set_label(self, key: str, value: str):
        """Set a label."""
        self.labels[key] = value

    def get_label(self, key: str, default: str | None = None) -> str | None:
        """Get a label value."""
        return self.labels.get(key, default)

    def set_annotation(self, key: str, value: str):
        """Set an annotation."""
        self.annotations[key] = value

    def get_annotation(self, key: str, default: str | None = None) -> str | None:
        """Get an annotation value."""
        return self.annotations.get(key, default)


@dataclass
class HealthCheck:
    """Health check configuration."""

    # Health check type and configuration
    url: str | None = None
    method: str = "GET"
    headers: builtins.dict[str, str] = field(default_factory=dict)
    expected_status: int = 200
    timeout: float = 5.0

    # TCP health check
    tcp_port: int | None = None

    # Custom health check
    custom_check: str | None = None

    # Check intervals
    interval: float = 30.0  # Seconds between checks
    initial_delay: float = 0.0  # Delay before first check
    failure_threshold: int = 3  # Failures before marking unhealthy
    success_threshold: int = 2  # Successes before marking healthy

    # Advanced settings
    follow_redirects: bool = True
    verify_ssl: bool = True

    def is_valid(self) -> bool:
        """Check if health check configuration is valid."""
        return bool(self.url or self.tcp_port or self.custom_check)


class ServiceInstance:
    """Service instance representation."""

    def __init__(
        self,
        service_name: str,
        instance_id: str | None = None,
        endpoint: ServiceEndpoint | None = None,
        host: str | None = None,
        port: int | None = None,
        metadata: ServiceMetadata | None = None,
        health_check: HealthCheck | None = None,
    ):
        self.service_name = service_name
        self.instance_id = instance_id or str(uuid.uuid4())

        # Handle endpoint creation
        if endpoint:
            self.endpoint = endpoint
        elif host and port:
            self.endpoint = ServiceEndpoint(host=host, port=port)
        else:
            raise ValueError("Either endpoint or host/port must be provided")

        self.metadata = metadata or ServiceMetadata()
        self.health_check = health_check or HealthCheck()

        # State management
        self.status = ServiceStatus.UNKNOWN
        self.health_status = HealthStatus.UNKNOWN
        self.last_health_check: float | None = None
        self.registration_time = time.time()
        self.last_seen = time.time()

        # Statistics
        self.total_requests = 0
        self.active_connections = 0
        self.total_failures = 0
        self.response_times: builtins.list[float] = []

        # Circuit breaker state
        self.circuit_breaker_open = False
        self.circuit_breaker_failures = 0
        self.circuit_breaker_last_failure: float | None = None

    def update_health_status(self, status: HealthStatus):
        """Update health status."""
        old_status = self.health_status
        self.health_status = status
        self.last_health_check = time.time()
        self.last_seen = time.time()

        # Update service status based on health
        if status == HealthStatus.HEALTHY:
            if self.status in [ServiceStatus.UNKNOWN, ServiceStatus.UNHEALTHY]:
                self.status = ServiceStatus.HEALTHY
        elif status == HealthStatus.UNHEALTHY:
            self.status = ServiceStatus.UNHEALTHY

        if old_status != status:
            logger.info(
                "Service %s instance %s health status changed: %s -> %s",
                self.service_name,
                self.instance_id,
                old_status.value,
                status.value,
            )

    def record_request(self, response_time: float | None = None, success: bool = True):
        """Record a request to this instance."""
        self.total_requests += 1
        self.last_seen = time.time()

        if response_time is not None:
            self.response_times.append(response_time)
            # Keep only last 100 response times
            if len(self.response_times) > 100:
                self.response_times = self.response_times[-100:]

        if not success:
            self.total_failures += 1

    def record_connection(self, active: bool = True):
        """Record active connection change."""
        if active:
            self.active_connections += 1
        else:
            self.active_connections = max(0, self.active_connections - 1)

    def get_average_response_time(self) -> float:
        """Get average response time."""
        if not self.response_times:
            return 0.0
        return sum(self.response_times) / len(self.response_times)

    def get_success_rate(self) -> float:
        """Get success rate."""
        if self.total_requests == 0:
            return 1.0
        return (self.total_requests - self.total_failures) / self.total_requests

    def is_healthy(self) -> bool:
        """Check if instance is healthy."""
        return (
            self.status == ServiceStatus.HEALTHY
            and self.health_status == HealthStatus.HEALTHY
            and not self.circuit_breaker_open
        )

    def is_available(self) -> bool:
        """Check if instance is available for requests."""
        return (
            self.status in [ServiceStatus.HEALTHY, ServiceStatus.UNKNOWN]
            and self.health_status in [HealthStatus.HEALTHY, HealthStatus.UNKNOWN]
            and not self.circuit_breaker_open
        )

    def get_weight(self) -> float:
        """Get dynamic weight based on performance."""
        base_weight = 1.0

        # Adjust based on success rate
        success_rate = self.get_success_rate()
        weight = base_weight * success_rate

        # Adjust based on response time
        avg_response_time = self.get_average_response_time()
        if avg_response_time > 0:
            # Lower weight for slower responses
            time_factor = max(0.1, 1.0 - (avg_response_time / 5000))  # 5 second baseline
            weight *= time_factor

        # Adjust based on active connections
        if self.metadata.max_connections:
            connection_ratio = self.active_connections / self.metadata.max_connections
            connection_factor = max(0.1, 1.0 - connection_ratio)
            weight *= connection_factor

        return max(0.1, weight)  # Minimum weight of 0.1

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "endpoint": {
                "host": self.endpoint.host,
                "port": self.endpoint.port,
                "protocol": self.endpoint.protocol.value,
                "path": self.endpoint.path,
                "url": self.endpoint.get_url(),
            },
            "metadata": {
                "version": self.metadata.version,
                "environment": self.metadata.environment,
                "region": self.metadata.region,
                "availability_zone": self.metadata.availability_zone,
                "tags": list(self.metadata.tags),
                "labels": self.metadata.labels.copy(),
                "annotations": self.metadata.annotations.copy(),
            },
            "status": self.status.value,
            "health_status": self.health_status.value,
            "last_health_check": self.last_health_check,
            "registration_time": self.registration_time,
            "last_seen": self.last_seen,
            "stats": {
                "total_requests": self.total_requests,
                "active_connections": self.active_connections,
                "total_failures": self.total_failures,
                "success_rate": self.get_success_rate(),
                "average_response_time": self.get_average_response_time(),
                "weight": self.get_weight(),
            },
            "circuit_breaker": {
                "open": self.circuit_breaker_open,
                "failures": self.circuit_breaker_failures,
                "last_failure": self.circuit_breaker_last_failure,
            },
        }

    def __str__(self) -> str:
        return f"{self.service_name}[{self.instance_id}]@{self.endpoint}"

    def __repr__(self) -> str:
        return (
            f"ServiceInstance(service_name='{self.service_name}', "
            f"instance_id='{self.instance_id}', "
            f"endpoint='{self.endpoint}', "
            f"status={self.status.value}, "
            f"health_status={self.health_status.value})"
        )


@dataclass
class ServiceRegistryConfig:
    """Configuration for service registry."""

    # Registry behavior
    enable_health_checks: bool = True
    health_check_interval: float = 30.0
    instance_ttl: float = 300.0  # 5 minutes
    cleanup_interval: float = 60.0  # 1 minute

    # Clustering and replication
    enable_clustering: bool = False
    cluster_nodes: builtins.list[str] = field(default_factory=list)
    replication_factor: int = 3

    # Storage configuration
    persistence_enabled: bool = False
    persistence_path: str | None = None
    backup_interval: float = 3600.0  # 1 hour

    # Security
    enable_authentication: bool = False
    auth_token: str | None = None
    enable_encryption: bool = False

    # Performance
    max_instances_per_service: int = 1000
    max_services: int = 10000
    cache_size: int = 10000

    # Monitoring
    enable_metrics: bool = True
    metrics_interval: float = 60.0

    # Notifications
    enable_notifications: bool = True
    notification_channels: builtins.list[str] = field(default_factory=list)


class ServiceRegistry(ABC):
    """Abstract service registry interface."""

    @abstractmethod
    async def register(self, instance: ServiceInstance) -> bool:
        """Register a service instance."""

    @abstractmethod
    async def deregister(self, service_name: str, instance_id: str) -> bool:
        """Deregister a service instance."""

    @abstractmethod
    async def discover(self, service_name: str) -> builtins.list[ServiceInstance]:
        """Discover all instances of a service."""

    @abstractmethod
    async def get_instance(self, service_name: str, instance_id: str) -> ServiceInstance | None:
        """Get a specific service instance."""

    @abstractmethod
    async def update_instance(self, instance: ServiceInstance) -> bool:
        """Update a service instance."""

    @abstractmethod
    async def list_services(self) -> builtins.list[str]:
        """List all registered services."""

    @abstractmethod
    async def get_healthy_instances(self, service_name: str) -> builtins.list[ServiceInstance]:
        """Get healthy instances of a service."""

    @abstractmethod
    async def update_health_status(
        self, service_name: str, instance_id: str, status: HealthStatus
    ) -> bool:
        """Update health status of an instance."""


class ServiceEvent:
    """Service registry event."""

    def __init__(
        self,
        event_type: str,
        service_name: str,
        instance_id: str,
        instance: ServiceInstance | None = None,
        timestamp: float | None = None,
    ):
        self.event_type = event_type  # register, deregister, health_change, etc.
        self.service_name = service_name
        self.instance_id = instance_id
        self.instance = instance
        self.timestamp = timestamp or time.time()
        self.event_id = str(uuid.uuid4())

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "instance": self.instance.to_dict() if self.instance else None,
            "timestamp": self.timestamp,
        }


class ServiceWatcher(ABC):
    """Abstract service registry watcher."""

    @abstractmethod
    async def watch(self, service_name: str | None = None) -> None:
        """Watch for service registry changes."""

    @abstractmethod
    async def on_service_registered(self, event: ServiceEvent) -> None:
        """Handle service registration event."""

    @abstractmethod
    async def on_service_deregistered(self, event: ServiceEvent) -> None:
        """Handle service deregistration event."""

    @abstractmethod
    async def on_health_changed(self, event: ServiceEvent) -> None:
        """Handle health status change event."""
