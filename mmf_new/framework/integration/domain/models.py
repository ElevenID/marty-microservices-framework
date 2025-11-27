"""
Integration Domain Models
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any
from uuid import uuid4


class ConnectorType(str, Enum):
    """Types of external system connectors."""

    REST_API = "rest_api"
    DATABASE = "database"
    FILESYSTEM = "filesystem"
    GRPC = "grpc"
    GRAPHQL = "graphql"
    SOAP = "soap"
    MESSAGE_QUEUE = "message_queue"


class DataFormat(str, Enum):
    """Data formats for integration."""

    JSON = "json"
    XML = "xml"
    CSV = "csv"
    YAML = "yaml"
    PROTOBUF = "protobuf"
    BINARY = "binary"


class CircuitBreakerState(str, Enum):
    """State of the circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class ConnectionConfig:
    """Configuration for external system connection."""

    system_id: str
    name: str
    connector_type: ConnectorType
    endpoint_url: str

    # Authentication
    auth_type: str = "none"
    credentials: dict[str, str] = field(default_factory=dict)

    # Connection settings
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5

    # Protocol specific settings
    protocol_settings: dict[str, Any] = field(default_factory=dict)

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 60

    # Metadata
    description: str = ""
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class IntegrationRequest:
    """Request for external system integration."""

    system_id: str
    operation: str
    data: Any
    request_id: str = field(default_factory=lambda: str(uuid4()))

    # Request configuration
    timeout: int | None = None
    headers: dict[str, str] = field(default_factory=dict)

    # Metadata
    correlation_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class IntegrationResponse:
    """Response from external system integration."""

    request_id: str
    success: bool
    data: Any

    # Response metadata
    status_code: int | None = None
    headers: dict[str, str] = field(default_factory=dict)

    # Error information
    error_code: str | None = None
    error_message: str | None = None

    # Performance metrics
    latency_ms: float | None = None
    retry_count: int = 0

    # Timestamps
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CircuitBreakerStatus:
    """Status of a circuit breaker."""

    state: CircuitBreakerState
    failure_count: int
    last_failure_time: float | None
    last_success_time: float | None
