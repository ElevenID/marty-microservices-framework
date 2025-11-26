"""
Communication protocols and data models for Marty Microservices Framework

This module contains enums and data classes used across the communication system.
"""

import builtins
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any


class CommunicationProtocol(Enum):
    """Service communication protocols."""

    HTTP = "http"
    HTTPS = "https"
    GRPC = "grpc"
    GRPC_WEB = "grpc_web"
    WEBSOCKET = "websocket"
    TCP = "tcp"
    UDP = "udp"
    KAFKA = "kafka"
    RABBITMQ = "rabbitmq"
    REDIS = "redis"


class ServiceType(Enum):
    """Service types for discovery and routing."""

    WEB_SERVICE = "web_service"
    API_SERVICE = "api_service"
    BACKGROUND_SERVICE = "background_service"
    DATABASE_SERVICE = "database_service"
    CACHE_SERVICE = "cache_service"
    MESSAGE_BROKER = "message_broker"
    GATEWAY_SERVICE = "gateway_service"


class HealthStatus(Enum):
    """Service health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"
    UNKNOWN = "unknown"
    STARTING = "starting"
    STOPPING = "stopping"


class ServiceState(Enum):
    """Service state in lifecycle."""

    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"
    MAINTENANCE = "maintenance"


class DependencyType(Enum):
    """Service dependency types."""

    HARD = "hard"  # Service cannot function without this dependency
    SOFT = "soft"  # Service can function with degraded performance
    CIRCUIT_BREAKER = "circuit_breaker"  # Uses circuit breaker pattern


@dataclass
class ServiceInstance:
    """Enhanced service instance with comprehensive metadata."""

    # Basic identification
    instance_id: str
    service_name: str
    host: str
    port: int
    protocol: CommunicationProtocol = CommunicationProtocol.HTTP
    service_type: ServiceType = ServiceType.API_SERVICE

    # Versioning
    version: str = "1.0.0"
    api_version: str = "v1"

    # Health and status
    health_status: HealthStatus = HealthStatus.UNKNOWN
    service_state: ServiceState = ServiceState.STARTING
    last_health_check: datetime | None = None
    health_check_url: str = "/health"
    readiness_check_url: str = "/ready"

    # Capabilities and metadata
    capabilities: builtins.list[str] = field(default_factory=list)
    tags: builtins.dict[str, str] = field(default_factory=dict)
    metadata: builtins.dict[str, Any] = field(default_factory=dict)

    # Performance characteristics
    cpu_limit: float | None = None  # CPU cores
    memory_limit: int | None = None  # MB
    max_connections: int | None = None
    rate_limit: int | None = None  # requests per second

    # Networking
    ssl_enabled: bool = False
    certificate_info: builtins.dict[str, str] | None = None

    # Timestamps
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_seen: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class ServiceDependency:
    """Service dependency definition."""

    dependency_id: str
    source_service: str
    target_service: str
    dependency_type: DependencyType
    required_version: str | None = None
    fallback_service: str | None = None
    timeout: int = 30  # seconds
    retry_attempts: int = 3
    circuit_breaker_enabled: bool = True
    health_check_required: bool = True


@dataclass
class ServiceContract:
    """Service contract for API specifications."""

    contract_id: str
    service_name: str
    version: str
    contract_type: str  # "openapi", "grpc", "graphql", etc.
    schema_url: str | None = None
    endpoints: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)
    documentation_url: str | None = None


@dataclass
class CommunicationMetrics:
    """Communication metrics and statistics."""

    service_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time: float = 0.0
    last_request_time: datetime | None = None
    error_rate: float = 0.0
    throughput: float = 0.0  # requests per second
    circuit_breaker_trips: int = 0
    dependency_failures: builtins.dict[str, int] = field(default_factory=dict)
