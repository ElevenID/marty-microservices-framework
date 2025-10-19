"""
Central Configuration Service for Microservices

This module implements a comprehensive configuration management system that allows
runtime configuration changes without service redeployment. It supports environment-specific
settings, real-time updates, configuration validation, versioning, and rollback capabilities.

Key Features:
- Environment-specific configuration management
- Real-time configuration updates via WebSocket/SSE
- Configuration versioning and rollback
- Configuration validation and schema enforcement
- Distributed configuration caching
- Configuration change notifications
- Audit logging and change tracking
- Configuration templates and inheritance
- Secret management integration
- Multi-format configuration support (JSON, YAML, TOML, ENV)

Author: Marty Framework Team
Version: 1.0.0
"""

import asyncio
import builtins
import hashlib
import json
import uuid
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, dict, list, set

import redis.asyncio as redis
import structlog
import uvicorn
import yaml
from cryptography.fernet import Fernet
from fastapi import (
    Depends,
    FastAPI,
    HTTPException,
    Response,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate
from opentelemetry import trace
from opentelemetry.exporter.jaeger.thrift import JaegerExporter
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

__version__ = "1.0.0"



# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer(),
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()

# Metrics
config_requests_total = Counter(
    "config_requests_total",
    "Total configuration requests",
    ["service", "environment", "status"],
)
config_updates_total = Counter(
    "config_updates_total", "Total configuration updates", ["service", "environment"]
)
config_validations_total = Counter(
    "config_validations_total", "Total configuration validations", ["service", "status"]
)
config_cache_hits_total = Counter(
    "config_cache_hits_total", "Total configuration cache hits", ["service"]
)
config_cache_misses_total = Counter(
    "config_cache_misses_total", "Total configuration cache misses", ["service"]
)
config_subscriptions_gauge = Gauge(
    "config_subscriptions_total", "Number of active configuration subscriptions"
)
config_fetch_duration = Histogram(
    "config_fetch_duration_seconds",
    "Configuration fetch duration",
    ["service", "environment"],
)


class ConfigFormat(Enum):
    """Configuration file formats."""

    JSON = "json"
    YAML = "yaml"
    TOML = "toml"
    ENV = "env"
    PROPERTIES = "properties"


class ConfigScope(Enum):
    """Configuration scope levels."""

    GLOBAL = "global"
    ENVIRONMENT = "environment"
    SERVICE = "service"
    INSTANCE = "instance"


class ChangeType(Enum):
    """Configuration change types."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ROLLBACK = "rollback"


class ValidationLevel(Enum):
    """Configuration validation levels."""

    NONE = "none"
    BASIC = "basic"
    STRICT = "strict"
    CUSTOM = "custom"


@dataclass
class ConfigurationValue:
    """Individual configuration value with metadata."""

    key: str
    value: Any
    data_type: str = "string"
    description: str | None = None
    default_value: Any | None = None
    required: bool = False
    sensitive: bool = False
    validation_rules: builtins.dict[str, Any] = field(default_factory=dict)
    tags: builtins.set[str] = field(default_factory=set)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str | None = None
    updated_by: str | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["created_at"] = self.created_at.isoformat()
        data["updated_at"] = self.updated_at.isoformat()
        data["tags"] = list(self.tags)
        return data

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "ConfigurationValue":
        """Create from dictionary."""
        if data.get("created_at"):
            data["created_at"] = datetime.fromisoformat(data["created_at"])
        if data.get("updated_at"):
            data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("tags"):
            data["tags"] = set(data["tags"])
        return cls(**data)


@dataclass
class ConfigurationSet:
    """Complete configuration set for a service/environment."""

    service_name: str
    environment: str
    version: str
    values: builtins.dict[str, ConfigurationValue] = field(default_factory=dict)
    schema: builtins.dict[str, Any] | None = None
    parent_config: str | None = None  # For inheritance
    metadata: builtins.dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    created_by: str | None = None
    updated_by: str | None = None
    checksum: str | None = None

    def __post_init__(self):
        """Calculate checksum after initialization."""
        self.checksum = self.calculate_checksum()

    def calculate_checksum(self) -> str:
        """Calculate configuration checksum for change detection."""
        content = json.dumps(
            {k: v.value for k, v in self.values.items()}, sort_keys=True, default=str
        )
        return hashlib.sha256(content.encode()).hexdigest()

    def get_flat_config(self, include_sensitive: bool = False) -> builtins.dict[str, Any]:
        """Get flattened configuration values."""
        result = {}
        for key, config_value in self.values.items():
            if config_value.sensitive and not include_sensitive:
                result[key] = "***REDACTED***"
            else:
                result[key] = config_value.value
        return result

    def validate_against_schema(self) -> builtins.list[str]:
        """Validate configuration against JSON schema."""
        if not self.schema:
            return []

        errors = []
        try:
            config_data = self.get_flat_config(include_sensitive=True)
            validate(instance=config_data, schema=self.schema)
        except JsonSchemaValidationError as e:
            errors.append(f"Schema validation error: {e.message}")
        except Exception as e:
            errors.append(f"Validation error: {str(e)}")

        return errors

    def merge_with_parent(
        self, parent_config: "ConfigurationSet"
    ) -> "ConfigurationSet":
        """Merge configuration with parent configuration."""
        merged_values = parent_config.values.copy()
        merged_values.update(self.values)

        return ConfigurationSet(
            service_name=self.service_name,
            environment=self.environment,
            version=self.version,
            values=merged_values,
            schema=self.schema or parent_config.schema,
            parent_config=self.parent_config,
            metadata={**parent_config.metadata, **self.metadata},
            created_at=self.created_at,
            updated_at=self.updated_at,
            created_by=self.created_by,
            updated_by=self.updated_by,
        )

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "service_name": self.service_name,
            "environment": self.environment,
            "version": self.version,
            "values": {k: v.to_dict() for k, v in self.values.items()},
            "schema": self.schema,
            "parent_config": self.parent_config,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "created_by": self.created_by,
            "updated_by": self.updated_by,
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "ConfigurationSet":
        """Create from dictionary."""
        # Convert values
        values = {}
        if data.get("values"):
            values = {
                k: ConfigurationValue.from_dict(v) for k, v in data["values"].items()
            }

        # Convert timestamps
        created_at = (
            datetime.fromisoformat(data["created_at"])
            if data.get("created_at")
            else datetime.utcnow()
        )
        updated_at = (
            datetime.fromisoformat(data["updated_at"])
            if data.get("updated_at")
            else datetime.utcnow()
        )

        return cls(
            service_name=data["service_name"],
            environment=data["environment"],
            version=data["version"],
            values=values,
            schema=data.get("schema"),
            parent_config=data.get("parent_config"),
            metadata=data.get("metadata", {}),
            created_at=created_at,
            updated_at=updated_at,
            created_by=data.get("created_by"),
            updated_by=data.get("updated_by"),
            checksum=data.get("checksum"),
        )


@dataclass
class ConfigurationChange:
    """Configuration change record for audit trail."""

    id: str
    service_name: str
    environment: str
    change_type: ChangeType
    changed_keys: builtins.list[str]
    old_values: builtins.dict[str, Any] = field(default_factory=dict)
    new_values: builtins.dict[str, Any] = field(default_factory=dict)
    version_before: str | None = None
    version_after: str | None = None
    changed_by: str | None = None
    change_reason: str | None = None
    timestamp: datetime = field(default_factory=datetime.utcnow)
    rollback_id: str | None = None

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary for serialization."""
        data = asdict(self)
        data["timestamp"] = self.timestamp.isoformat()
        data["change_type"] = self.change_type.value
        return data

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "ConfigurationChange":
        """Create from dictionary."""
        data["timestamp"] = datetime.fromisoformat(data["timestamp"])
        data["change_type"] = ChangeType(data["change_type"])
        return cls(**data)


class ConfigurationStore(ABC):
    """Abstract base class for configuration storage."""

    @abstractmethod
    async def get_configuration(
        self, service_name: str, environment: str, version: str | None = None
    ) -> ConfigurationSet | None:
        """Get configuration for service and environment."""
        pass

    @abstractmethod
    async def save_configuration(self, config: ConfigurationSet) -> bool:
        """Save configuration."""
        pass

    @abstractmethod
    async def list_configurations(
        self, service_name: str | None = None, environment: str | None = None
    ) -> builtins.list[ConfigurationSet]:
        """List configurations."""
        pass

    @abstractmethod
    async def delete_configuration(
        self, service_name: str, environment: str, version: str | None = None
    ) -> bool:
        """Delete configuration."""
        pass

    @abstractmethod
    async def get_configuration_versions(
        self, service_name: str, environment: str
    ) -> builtins.list[str]:
        """Get all versions of a configuration."""
        pass

    @abstractmethod
    async def save_change_record(self, change: ConfigurationChange) -> bool:
        """Save configuration change record."""
        pass

    @abstractmethod
    async def get_change_history(
        self, service_name: str, environment: str, limit: int = 100
    ) -> builtins.list[ConfigurationChange]:
        """Get configuration change history."""
        pass


class MemoryConfigurationStore(ConfigurationStore):
    """In-memory configuration store for development and testing."""

    def __init__(self):
        self._configurations: builtins.dict[str, builtins.dict[str, builtins.dict[str, ConfigurationSet]]] = {}
        self._changes: builtins.dict[str, builtins.list[ConfigurationChange]] = {}

    def _get_key(self, service_name: str, environment: str) -> str:
        """Generate storage key."""
        return f"{service_name}:{environment}"

    async def get_configuration(
        self, service_name: str, environment: str, version: str | None = None
    ) -> ConfigurationSet | None:
        """Get configuration for service and environment."""
        if service_name not in self._configurations:
            return None

        if environment not in self._configurations[service_name]:
            return None

        if version:
            return self._configurations[service_name][environment].get(version)
        else:
            # Return latest version
            versions = self._configurations[service_name][environment]
            if not versions:
                return None
            latest_version = max(versions.keys())
            return versions[latest_version]

    async def save_configuration(self, config: ConfigurationSet) -> bool:
        """Save configuration."""
        if config.service_name not in self._configurations:
            self._configurations[config.service_name] = {}

        if config.environment not in self._configurations[config.service_name]:
            self._configurations[config.service_name][config.environment] = {}

        self._configurations[config.service_name][config.environment][
            config.version
        ] = config
        return True

    async def list_configurations(
        self, service_name: str | None = None, environment: str | None = None
    ) -> builtins.list[ConfigurationSet]:
        """List configurations."""
        result = []

        services = [service_name] if service_name else self._configurations.keys()

        for svc in services:
            if svc not in self._configurations:
                continue

            environments = (
                [environment] if environment else self._configurations[svc].keys()
            )

            for env in environments:
                if env not in self._configurations[svc]:
                    continue

                # Get latest version for each environment
                versions = self._configurations[svc][env]
                if versions:
                    latest_version = max(versions.keys())
                    result.append(versions[latest_version])

        return result

    async def delete_configuration(
        self, service_name: str, environment: str, version: str | None = None
    ) -> bool:
        """Delete configuration."""
        if service_name not in self._configurations:
            return False

        if environment not in self._configurations[service_name]:
            return False

        if version:
            if version in self._configurations[service_name][environment]:
                del self._configurations[service_name][environment][version]
                return True
        else:
            # Delete all versions
            self._configurations[service_name][environment] = {}
            return True

        return False

    async def get_configuration_versions(
        self, service_name: str, environment: str
    ) -> builtins.list[str]:
        """Get all versions of a configuration."""
        if service_name not in self._configurations:
            return []

        if environment not in self._configurations[service_name]:
            return []

        return list(self._configurations[service_name][environment].keys())

    async def save_change_record(self, change: ConfigurationChange) -> bool:
        """Save configuration change record."""
        key = self._get_key(change.service_name, change.environment)

        if key not in self._changes:
            self._changes[key] = []

        self._changes[key].append(change)
        return True

    async def get_change_history(
        self, service_name: str, environment: str, limit: int = 100
    ) -> builtins.list[ConfigurationChange]:
        """Get configuration change history."""
        key = self._get_key(service_name, environment)

        if key not in self._changes:
            return []

        # Return most recent changes first
        changes = sorted(self._changes[key], key=lambda x: x.timestamp, reverse=True)
        return changes[:limit]


class ConfigurationCache:
    """Configuration caching layer with TTL and invalidation."""

    def __init__(self, redis_client: redis.Redis | None = None, ttl: int = 300):
        self.redis_client = redis_client
        self.ttl = ttl
        self._memory_cache: builtins.dict[str, tuple] = {}  # (config, expiry)

    def _get_cache_key(
        self, service_name: str, environment: str, version: str | None = None
    ) -> str:
        """Generate cache key."""
        key = f"config:{service_name}:{environment}"
        if version:
            key += f":{version}"
        return key

    async def get(
        self, service_name: str, environment: str, version: str | None = None
    ) -> ConfigurationSet | None:
        """Get configuration from cache."""
        cache_key = self._get_cache_key(service_name, environment, version)

        # Try Redis first
        if self.redis_client:
            try:
                cached_data = await self.redis_client.get(cache_key)
                if cached_data:
                    config_data = json.loads(cached_data)
                    config_cache_hits_total.labels(service=service_name).inc()
                    return ConfigurationSet.from_dict(config_data)
            except Exception as e:
                logger.warning("Redis cache error", error=str(e))

        # Fallback to memory cache
        if cache_key in self._memory_cache:
            config, expiry = self._memory_cache[cache_key]
            if datetime.utcnow() < expiry:
                config_cache_hits_total.labels(service=service_name).inc()
                return config
            else:
                # Expired
                del self._memory_cache[cache_key]

        config_cache_misses_total.labels(service=service_name).inc()
        return None

    async def set(self, config: ConfigurationSet) -> bool:
        """Set configuration in cache."""
        cache_key = self._get_cache_key(
            config.service_name, config.environment, config.version
        )

        # Cache in Redis
        if self.redis_client:
            try:
                config_data = json.dumps(config.to_dict(), default=str)
                await self.redis_client.setex(cache_key, self.ttl, config_data)
            except Exception as e:
                logger.warning("Redis cache set error", error=str(e))

        # Cache in memory
        expiry = datetime.utcnow() + timedelta(seconds=self.ttl)
        self._memory_cache[cache_key] = (config, expiry)

        return True

    async def invalidate(
        self, service_name: str, environment: str, version: str | None = None
    ) -> bool:
        """Invalidate cache for specific configuration."""
        cache_key = self._get_cache_key(service_name, environment, version)

        # Invalidate Redis
        if self.redis_client:
            try:
                await self.redis_client.delete(cache_key)
            except Exception as e:
                logger.warning("Redis cache invalidation error", error=str(e))

        # Invalidate memory cache
        if cache_key in self._memory_cache:
            del self._memory_cache[cache_key]

        return True

    async def invalidate_service(self, service_name: str) -> bool:
        """Invalidate all cache entries for a service."""
        pattern = f"config:{service_name}:*"

        # Invalidate Redis
        if self.redis_client:
            try:
                keys = await self.redis_client.keys(pattern)
                if keys:
                    await self.redis_client.delete(*keys)
            except Exception as e:
                logger.warning("Redis service cache invalidation error", error=str(e))

        # Invalidate memory cache
        keys_to_delete = [
            key
            for key in self._memory_cache.keys()
            if key.startswith(f"config:{service_name}:")
        ]
        for key in keys_to_delete:
            del self._memory_cache[key]

        return True


class ConfigurationManager:
    """Main configuration management service."""

    def __init__(
        self,
        store: ConfigurationStore,
        cache: ConfigurationCache | None = None,
        encryption_key: bytes | None = None,
    ):
        self.store = store
        self.cache = cache
        self.cipher = Fernet(encryption_key) if encryption_key else None
        self.tracer = trace.get_tracer(__name__)
        self._subscribers: builtins.dict[str, builtins.set[WebSocket]] = {}  # service -> websockets
        self._notification_queue = asyncio.Queue()

        # Start background notification processor
        asyncio.create_task(self._process_notifications())

    async def get_configuration(
        self,
        service_name: str,
        environment: str,
        version: str | None = None,
        include_sensitive: bool = False,
    ) -> ConfigurationSet | None:
        """Get configuration with caching and inheritance."""
        with self.tracer.start_as_current_span(
            f"get_configuration_{service_name}"
        ) as span:
            span.set_attribute("service.name", service_name)
            span.set_attribute("environment", environment)

            start_time = datetime.utcnow()

            try:
                # Try cache first
                if self.cache:
                    config = await self.cache.get(service_name, environment, version)
                    if config:
                        config_requests_total.labels(
                            service=service_name,
                            environment=environment,
                            status="cache_hit",
                        ).inc()
                        return (
                            self._decrypt_sensitive_values(config)
                            if include_sensitive
                            else config
                        )

                # Load from store
                config = await self.store.get_configuration(
                    service_name, environment, version
                )
                if not config:
                    config_requests_total.labels(
                        service=service_name,
                        environment=environment,
                        status="not_found",
                    ).inc()
                    return None

                # Handle inheritance
                if config.parent_config:
                    parent_parts = config.parent_config.split(":")
                    if len(parent_parts) == 2:
                        parent_service, parent_env = parent_parts
                        parent_config = await self.store.get_configuration(
                            parent_service, parent_env
                        )
                        if parent_config:
                            config = config.merge_with_parent(parent_config)

                # Cache the result
                if self.cache:
                    await self.cache.set(config)

                config_requests_total.labels(
                    service=service_name, environment=environment, status="success"
                ).inc()

                return (
                    self._decrypt_sensitive_values(config)
                    if include_sensitive
                    else config
                )

            except Exception as e:
                config_requests_total.labels(
                    service=service_name, environment=environment, status="error"
                ).inc()
                logger.error(
                    "Configuration fetch error",
                    service=service_name,
                    environment=environment,
                    error=str(e),
                )
                raise

            finally:
                duration = (datetime.utcnow() - start_time).total_seconds()
                config_fetch_duration.labels(
                    service=service_name, environment=environment
                ).observe(duration)

    async def save_configuration(
        self,
        config: ConfigurationSet,
        changed_by: str | None = None,
        change_reason: str | None = None,
    ) -> bool:
        """Save configuration with validation and change tracking."""
        with self.tracer.start_as_current_span(
            f"save_configuration_{config.service_name}"
        ) as span:
            span.set_attribute("service.name", config.service_name)
            span.set_attribute("environment", config.environment)

            try:
                # Get current configuration for change tracking
                current_config = await self.store.get_configuration(
                    config.service_name, config.environment
                )

                # Validate configuration
                validation_errors = config.validate_against_schema()
                if validation_errors:
                    config_validations_total.labels(
                        service=config.service_name, status="failed"
                    ).inc()
                    raise ValueError(
                        f"Configuration validation failed: {', '.join(validation_errors)}"
                    )

                config_validations_total.labels(
                    service=config.service_name, status="success"
                ).inc()

                # Encrypt sensitive values
                encrypted_config = self._encrypt_sensitive_values(config)

                # Update metadata
                encrypted_config.updated_at = datetime.utcnow()
                encrypted_config.updated_by = changed_by

                # Save configuration
                success = await self.store.save_configuration(encrypted_config)

                if success:
                    # Invalidate cache
                    if self.cache:
                        await self.cache.invalidate_service(config.service_name)

                    # Track changes
                    await self._track_configuration_change(
                        current_config, config, changed_by, change_reason
                    )

                    # Notify subscribers
                    await self._notify_configuration_change(config)

                    config_updates_total.labels(
                        service=config.service_name, environment=config.environment
                    ).inc()

                    logger.info(
                        "Configuration updated",
                        service=config.service_name,
                        environment=config.environment,
                        version=config.version,
                        changed_by=changed_by,
                    )

                return success

            except Exception as e:
                logger.error(
                    "Configuration save error",
                    service=config.service_name,
                    environment=config.environment,
                    error=str(e),
                )
                raise

    async def rollback_configuration(
        self,
        service_name: str,
        environment: str,
        target_version: str,
        changed_by: str | None = None,
    ) -> bool:
        """Rollback configuration to a previous version."""
        # Get target version
        target_config = await self.store.get_configuration(
            service_name, environment, target_version
        )
        if not target_config:
            raise ValueError(f"Target version {target_version} not found")

        # Create new version with rollback
        new_version = f"rollback-{uuid.uuid4().hex[:8]}"
        rollback_config = ConfigurationSet(
            service_name=service_name,
            environment=environment,
            version=new_version,
            values=target_config.values,
            schema=target_config.schema,
            parent_config=target_config.parent_config,
            metadata={**target_config.metadata, "rollback_from": target_version},
            created_by=changed_by,
            updated_by=changed_by,
        )

        # Save rollback configuration
        success = await self.save_configuration(
            rollback_config, changed_by, f"Rollback to version {target_version}"
        )

        if success:
            # Record rollback change
            change = ConfigurationChange(
                id=str(uuid.uuid4()),
                service_name=service_name,
                environment=environment,
                change_type=ChangeType.ROLLBACK,
                changed_keys=list(rollback_config.values.keys()),
                old_values={},
                new_values={k: v.value for k, v in rollback_config.values.items()},
                version_before=None,
                version_after=new_version,
                changed_by=changed_by,
                change_reason=f"Rollback to version {target_version}",
                rollback_id=target_version,
            )

            await self.store.save_change_record(change)

        return success

    async def subscribe_to_changes(self, websocket: WebSocket, service_name: str):
        """Subscribe to configuration changes via WebSocket."""
        if service_name not in self._subscribers:
            self._subscribers[service_name] = set()

        self._subscribers[service_name].add(websocket)
        config_subscriptions_gauge.inc()

        logger.info(
            "Configuration subscription added",
            service=service_name,
            client=websocket.client.host if websocket.client else "unknown",
        )

    async def unsubscribe_from_changes(self, websocket: WebSocket, service_name: str):
        """Unsubscribe from configuration changes."""
        if service_name in self._subscribers:
            self._subscribers[service_name].discard(websocket)
            if not self._subscribers[service_name]:
                del self._subscribers[service_name]

        config_subscriptions_gauge.dec()

        logger.info(
            "Configuration subscription removed",
            service=service_name,
            client=websocket.client.host if websocket.client else "unknown",
        )

    def _encrypt_sensitive_values(self, config: ConfigurationSet) -> ConfigurationSet:
        """Encrypt sensitive configuration values."""
        if not self.cipher:
            return config

        encrypted_config = ConfigurationSet(
            service_name=config.service_name,
            environment=config.environment,
            version=config.version,
            schema=config.schema,
            parent_config=config.parent_config,
            metadata=config.metadata,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by,
            updated_by=config.updated_by,
        )

        for key, value in config.values.items():
            if value.sensitive and isinstance(value.value, str):
                encrypted_value = self.cipher.encrypt(value.value.encode()).decode()
                new_value = ConfigurationValue(
                    key=value.key,
                    value=encrypted_value,
                    data_type=value.data_type,
                    description=value.description,
                    default_value=value.default_value,
                    required=value.required,
                    sensitive=value.sensitive,
                    validation_rules=value.validation_rules,
                    tags=value.tags,
                    created_at=value.created_at,
                    updated_at=value.updated_at,
                    created_by=value.created_by,
                    updated_by=value.updated_by,
                )
                encrypted_config.values[key] = new_value
            else:
                encrypted_config.values[key] = value

        return encrypted_config

    def _decrypt_sensitive_values(self, config: ConfigurationSet) -> ConfigurationSet:
        """Decrypt sensitive configuration values."""
        if not self.cipher:
            return config

        decrypted_config = ConfigurationSet(
            service_name=config.service_name,
            environment=config.environment,
            version=config.version,
            schema=config.schema,
            parent_config=config.parent_config,
            metadata=config.metadata,
            created_at=config.created_at,
            updated_at=config.updated_at,
            created_by=config.created_by,
            updated_by=config.updated_by,
        )

        for key, value in config.values.items():
            if value.sensitive and isinstance(value.value, str):
                try:
                    decrypted_value = self.cipher.decrypt(value.value.encode()).decode()
                    new_value = ConfigurationValue(
                        key=value.key,
                        value=decrypted_value,
                        data_type=value.data_type,
                        description=value.description,
                        default_value=value.default_value,
                        required=value.required,
                        sensitive=value.sensitive,
                        validation_rules=value.validation_rules,
                        tags=value.tags,
                        created_at=value.created_at,
                        updated_at=value.updated_at,
                        created_by=value.created_by,
                        updated_by=value.updated_by,
                    )
                    decrypted_config.values[key] = new_value
                except Exception:
                    # If decryption fails, keep original value
                    decrypted_config.values[key] = value
            else:
                decrypted_config.values[key] = value

        return decrypted_config

    async def _track_configuration_change(
        self,
        old_config: ConfigurationSet | None,
        new_config: ConfigurationSet,
        changed_by: str | None,
        change_reason: str | None,
    ):
        """Track configuration changes for audit trail."""
        if not old_config:
            change_type = ChangeType.CREATE
            changed_keys = list(new_config.values.keys())
            old_values = {}
            new_values = {k: v.value for k, v in new_config.values.items()}
            version_before = None
        else:
            change_type = ChangeType.UPDATE

            # Find changed keys
            changed_keys = []
            old_values = {}
            new_values = {}

            # Check for updated/new keys
            for key, new_value in new_config.values.items():
                if key not in old_config.values:
                    changed_keys.append(key)
                    new_values[key] = new_value.value
                elif old_config.values[key].value != new_value.value:
                    changed_keys.append(key)
                    old_values[key] = old_config.values[key].value
                    new_values[key] = new_value.value

            # Check for deleted keys
            for key in old_config.values:
                if key not in new_config.values:
                    changed_keys.append(key)
                    old_values[key] = old_config.values[key].value

            version_before = old_config.version

        if changed_keys:
            change = ConfigurationChange(
                id=str(uuid.uuid4()),
                service_name=new_config.service_name,
                environment=new_config.environment,
                change_type=change_type,
                changed_keys=changed_keys,
                old_values=old_values,
                new_values=new_values,
                version_before=version_before,
                version_after=new_config.version,
                changed_by=changed_by,
                change_reason=change_reason,
            )

            await self.store.save_change_record(change)

    async def _notify_configuration_change(self, config: ConfigurationSet):
        """Notify subscribers of configuration changes."""
        await self._notification_queue.put(
            {
                "type": "configuration_change",
                "service_name": config.service_name,
                "environment": config.environment,
                "version": config.version,
                "timestamp": datetime.utcnow().isoformat(),
                "checksum": config.checksum,
            }
        )

    async def _process_notifications(self):
        """Process notification queue and send to subscribers."""
        while True:
            try:
                notification = await self._notification_queue.get()
                service_name = notification["service_name"]

                if service_name in self._subscribers:
                    disconnected_clients = set()

                    for websocket in self._subscribers[service_name]:
                        try:
                            await websocket.send_json(notification)
                        except Exception:
                            disconnected_clients.add(websocket)

                    # Clean up disconnected clients
                    for websocket in disconnected_clients:
                        await self.unsubscribe_from_changes(websocket, service_name)

                self._notification_queue.task_done()

            except Exception as e:
                logger.error("Notification processing error", error=str(e))
                await asyncio.sleep(1)


# FastAPI application
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    # Startup
    logger.info("Starting Configuration Service")

    # Initialize tracing
    if app.state.config.get("tracing_enabled", False):
        trace.set_tracer_provider(TracerProvider())
        jaeger_exporter = JaegerExporter(
            agent_host_name=app.state.config.get("jaeger_host", "localhost"),
            agent_port=app.state.config.get("jaeger_port", 6831),
        )
        span_processor = BatchSpanProcessor(jaeger_exporter)
        trace.get_tracer_provider().add_span_processor(span_processor)

        FastAPIInstrumentor.instrument_app(app)
        HTTPXClientInstrumentor().instrument()

    yield

    # Shutdown
    logger.info("Shutting down Configuration Service")


app = FastAPI(
    title="Configuration Service",
    description="Central configuration management for microservices",
    version=__version__,
    lifespan=lifespan,
)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(GZipMiddleware, minimum_size=1000)

# Global state
store = MemoryConfigurationStore()
cache = ConfigurationCache()
manager = ConfigurationManager(store, cache)

# Configuration
app.state.config = {
    "tracing_enabled": False,
    "jaeger_host": "localhost",
    "jaeger_port": 6831,
}

# Security
security = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str | None:
    """Get current user from authorization header."""
    if not credentials:
        return None
    # Implement your authentication logic here
    return "system"  # Placeholder


# Pydantic models for API
class ConfigValueRequest(BaseModel):
    key: str
    value: Any
    data_type: str = "string"
    description: str | None = None
    default_value: Any | None = None
    required: bool = False
    sensitive: bool = False
    validation_rules: builtins.dict[str, Any] = {}
    tags: builtins.list[str] = []


class ConfigurationRequest(BaseModel):
    service_name: str
    environment: str
    version: str = Field(
        default_factory=lambda: f"v{int(datetime.utcnow().timestamp())}"
    )
    values: builtins.dict[str, ConfigValueRequest]
    schema: builtins.dict[str, Any] | None = None
    parent_config: str | None = None
    metadata: builtins.dict[str, Any] = {}
    change_reason: str | None = None


# API Routes
@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": __version__,
        "active_subscriptions": config_subscriptions_gauge._value._value,
    }


@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/api/v1/config/{service_name}/{environment}")
async def get_configuration(
    service_name: str,
    environment: str,
    version: str | None = None,
    include_sensitive: bool = False,
    format: ConfigFormat = ConfigFormat.JSON,
    current_user: str | None = Depends(get_current_user),
):
    """Get configuration for service and environment."""
    try:
        config = await manager.get_configuration(
            service_name, environment, version, include_sensitive
        )

        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")

        if format == ConfigFormat.JSON:
            return {
                "service_name": config.service_name,
                "environment": config.environment,
                "version": config.version,
                "values": config.get_flat_config(include_sensitive),
                "metadata": config.metadata,
                "checksum": config.checksum,
                "updated_at": config.updated_at.isoformat(),
            }
        elif format == ConfigFormat.YAML:
            config_data = config.get_flat_config(include_sensitive)
            yaml_content = yaml.dump(config_data, default_flow_style=False)
            return Response(content=yaml_content, media_type="application/x-yaml")
        elif format == ConfigFormat.ENV:
            config_data = config.get_flat_config(include_sensitive)
            env_content = "\n".join([f"{k}={v}" for k, v in config_data.items()])
            return Response(content=env_content, media_type="text/plain")
        else:
            raise HTTPException(status_code=400, detail=f"Unsupported format: {format}")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get configuration: {str(e)}"
        )


@app.post("/api/v1/config", status_code=201)
async def save_configuration(
    config_request: ConfigurationRequest,
    current_user: str | None = Depends(get_current_user),
):
    """Save configuration."""
    try:
        # Convert request to domain objects
        values = {}
        for key, value_req in config_request.values.items():
            config_value = ConfigurationValue(
                key=key,
                value=value_req.value,
                data_type=value_req.data_type,
                description=value_req.description,
                default_value=value_req.default_value,
                required=value_req.required,
                sensitive=value_req.sensitive,
                validation_rules=value_req.validation_rules,
                tags=set(value_req.tags),
                created_by=current_user,
                updated_by=current_user,
            )
            values[key] = config_value

        config = ConfigurationSet(
            service_name=config_request.service_name,
            environment=config_request.environment,
            version=config_request.version,
            values=values,
            schema=config_request.schema,
            parent_config=config_request.parent_config,
            metadata=config_request.metadata,
            created_by=current_user,
            updated_by=current_user,
        )

        success = await manager.save_configuration(
            config, current_user, config_request.change_reason
        )

        if success:
            return {
                "message": "Configuration saved successfully",
                "service_name": config.service_name,
                "environment": config.environment,
                "version": config.version,
                "checksum": config.checksum,
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save configuration")

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to save configuration: {str(e)}"
        )


@app.get("/api/v1/config/{service_name}/{environment}/versions")
async def get_configuration_versions(service_name: str, environment: str):
    """Get all versions of a configuration."""
    try:
        versions = await store.get_configuration_versions(service_name, environment)
        return {"versions": versions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get versions: {str(e)}")


@app.post("/api/v1/config/{service_name}/{environment}/rollback")
async def rollback_configuration(
    service_name: str,
    environment: str,
    target_version: str,
    current_user: str | None = Depends(get_current_user),
):
    """Rollback configuration to a previous version."""
    try:
        success = await manager.rollback_configuration(
            service_name, environment, target_version, current_user
        )

        if success:
            return {
                "message": f"Configuration rolled back to version {target_version}",
                "service_name": service_name,
                "environment": environment,
                "target_version": target_version,
            }
        else:
            raise HTTPException(
                status_code=500, detail="Failed to rollback configuration"
            )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to rollback configuration: {str(e)}"
        )


@app.get("/api/v1/config/{service_name}/{environment}/history")
async def get_configuration_history(
    service_name: str, environment: str, limit: int = 100
):
    """Get configuration change history."""
    try:
        changes = await store.get_change_history(service_name, environment, limit)
        return {"changes": [change.to_dict() for change in changes]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get history: {str(e)}")


@app.websocket("/api/v1/config/{service_name}/subscribe")
async def subscribe_to_configuration_changes(websocket: WebSocket, service_name: str):
    """Subscribe to configuration changes via WebSocket."""
    await websocket.accept()
    await manager.subscribe_to_changes(websocket, service_name)

    try:
        while True:
            # Keep connection alive
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.unsubscribe_from_changes(websocket, service_name)


@app.get("/api/v1/config/{service_name}/stream")
async def stream_configuration_changes(service_name: str):
    """Stream configuration changes via Server-Sent Events."""

    async def event_generator():
        # This is a simplified implementation
        # In a real scenario, you'd want to implement proper SSE streaming
        while True:
            # Placeholder for SSE implementation
            yield f"data: {json.dumps({'message': 'keepalive'})}\n\n"
            await asyncio.sleep(30)

    return EventSourceResponse(event_generator())


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8070,
        reload=True,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "()": structlog.stdlib.ProcessorFormatter,
                    "processor": structlog.dev.ConsoleRenderer(),
                },
            },
            "handlers": {
                "default": {
                    "level": "INFO",
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                },
            },
            "loggers": {
                "": {
                    "handlers": ["default"],
                    "level": "INFO",
                    "propagate": False,
                },
            },
        },
    )
