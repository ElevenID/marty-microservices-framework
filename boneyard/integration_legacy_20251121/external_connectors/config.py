"""
External System Configuration Models

Data classes for external system configuration, integration requests,
responses, and data transformations.
"""

import builtins
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from .enums import ConnectorType, DataFormat, IntegrationPattern, TransformationType


@dataclass
class ExternalSystemConfig:
    """Configuration for external system connection."""

    system_id: str
    name: str
    connector_type: ConnectorType
    endpoint_url: str

    # Authentication
    auth_type: str = "none"  # none, basic, bearer, oauth2, api_key, certificate
    credentials: builtins.dict[str, str] = field(default_factory=dict)

    # Connection settings
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: int = 5

    # Protocol specific settings
    protocol_settings: builtins.dict[str, Any] = field(default_factory=dict)

    # Data format
    input_format: DataFormat = DataFormat.JSON
    output_format: DataFormat = DataFormat.JSON

    # Health checking
    health_check_enabled: bool = True
    health_check_endpoint: str | None = None
    health_check_interval: int = 60

    # Rate limiting
    rate_limit: int | None = None  # requests per second

    # Circuit breaker
    circuit_breaker_enabled: bool = True
    failure_threshold: int = 5
    recovery_timeout: int = 60

    # Metadata
    version: str = "1.0.0"
    description: str = ""
    tags: builtins.dict[str, str] = field(default_factory=dict)


@dataclass
class IntegrationRequest:
    """Request for external system integration."""

    request_id: str
    system_id: str
    operation: str
    data: Any

    # Request configuration
    pattern: IntegrationPattern = IntegrationPattern.REQUEST_RESPONSE
    timeout: int | None = None
    retry_policy: builtins.dict[str, Any] | None = None

    # Transformation
    input_transformation: str | None = None
    output_transformation: str | None = None

    # Metadata
    correlation_id: str | None = None
    headers: builtins.dict[str, str] = field(default_factory=dict)

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class IntegrationResponse:
    """Response from external system integration."""

    request_id: str
    success: bool
    data: Any

    # Response metadata
    status_code: int | None = None
    headers: builtins.dict[str, str] = field(default_factory=dict)

    # Error information
    error_code: str | None = None
    error_message: str | None = None

    # Performance metrics
    latency_ms: float | None = None
    retry_count: int = 0

    # Timestamps
    completed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class DataTransformation:
    """Data transformation definition."""

    transformation_id: str
    name: str
    transformation_type: TransformationType

    # Transformation logic
    source_schema: builtins.dict[str, Any] | None = None
    target_schema: builtins.dict[str, Any] | None = None
    mapping_rules: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)

    # Transformation code
    transformation_script: str | None = None

    # Validation rules
    validation_rules: builtins.list[builtins.dict[str, Any]] = field(default_factory=list)

    # Metadata
    description: str = ""
    version: str = "1.0.0"
