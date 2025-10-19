"""
Unified Data Consistency Configuration for Marty Microservices Framework

This module provides unified configuration and integration for all data consistency patterns:
- Saga orchestration configuration
- Transactional outbox configuration
- CQRS pattern configuration
- Event sourcing configuration
- Cross-pattern integration settings
"""

import json
import os
from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import yaml

from ..core.services import ConfigService
from ..framework.config.injection import container
from .cqrs.enhanced_cqrs import QueryExecutionMode
from .outbox.enhanced_outbox import (
    BatchConfig,
    OutboxConfig,
    PartitionConfig,
    RetryConfig,
)


class ConsistencyLevel(Enum):
    """Data consistency levels for distributed operations."""
    EVENTUAL = "eventual"
    STRONG = "strong"
    BOUNDED_STALENESS = "bounded_staleness"
    SESSION = "session"
    CONSISTENT_PREFIX = "consistent_prefix"


class PersistenceMode(Enum):
    """Persistence modes for different patterns."""
    IN_MEMORY = "in_memory"
    DATABASE = "database"
    DISTRIBUTED_CACHE = "distributed_cache"
    HYBRID = "hybrid"


@dataclass
class DatabaseConfig:
    """Database configuration for data consistency patterns."""
    connection_string: str = "postgresql://localhost:5432/mmf_consistency"
    pool_size: int = 10
    max_overflow: int = 20
    pool_timeout: int = 30
    pool_recycle: int = 3600
    echo_sql: bool = False

    # Transaction settings
    transaction_timeout_seconds: int = 30
    deadlock_retry_attempts: int = 3
    isolation_level: str = "READ_COMMITTED"


@dataclass
class EventStoreConfig:
    """Event store configuration."""
    connection_string: str = "postgresql://localhost:5432/mmf_eventstore"
    stream_page_size: int = 100
    snapshot_frequency: int = 100
    enable_snapshots: bool = True
    compression_enabled: bool = True
    encryption_enabled: bool = False

    # Performance settings
    batch_size: int = 50
    flush_interval_ms: int = 1000
    max_memory_cache_events: int = 10000


@dataclass
class MessageBrokerConfig:
    """Message broker configuration."""
    broker_type: str = "kafka"  # kafka, rabbitmq, redis
    brokers: list[str] = field(default_factory=lambda: ["localhost:9092"])

    # Kafka settings
    kafka_security_protocol: str = "PLAINTEXT"
    kafka_sasl_mechanism: str | None = None
    kafka_sasl_username: str | None = None
    kafka_sasl_password: str | None = None

    # RabbitMQ settings
    rabbitmq_host: str = "localhost"
    rabbitmq_port: int = 5672
    rabbitmq_username: str = "guest"
    rabbitmq_password: str = "guest"
    rabbitmq_virtual_host: str = "/"

    # Common settings
    enable_ssl: bool = False
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None
    ssl_ca_path: str | None = None


@dataclass
class SagaConfig:
    """Enhanced saga orchestration configuration."""
    # Core settings
    orchestrator_id: str = "default-orchestrator"
    worker_count: int = 3
    enable_parallel_execution: bool = True

    # Timing settings
    step_timeout_seconds: int = 30
    saga_timeout_seconds: int = 300
    compensation_timeout_seconds: int = 60

    # Retry configuration
    max_retry_attempts: int = 3
    retry_delay_ms: int = 1000
    retry_exponential_base: float = 2.0

    # Persistence
    persistence_mode: PersistenceMode = PersistenceMode.DATABASE
    state_store_table: str = "saga_state"
    history_retention_days: int = 30

    # Monitoring
    enable_metrics: bool = True
    enable_tracing: bool = True
    health_check_interval_ms: int = 30000

    # Error handling
    enable_dead_letter_queue: bool = True
    dead_letter_topic: str = "saga.dead-letter"
    auto_compensation_enabled: bool = True


@dataclass
class CQRSConfig:
    """CQRS pattern configuration."""
    # Query settings
    default_query_mode: QueryExecutionMode = QueryExecutionMode.SYNC
    query_timeout_seconds: int = 30
    enable_query_caching: bool = True
    cache_ttl_seconds: int = 300

    # Command settings
    command_timeout_seconds: int = 60
    enable_command_validation: bool = True
    enable_command_idempotency: bool = True
    idempotency_window_hours: int = 24

    # Read model settings
    read_model_consistency: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    max_staleness_ms: int = 5000
    enable_read_model_versioning: bool = True

    # Projection settings
    projection_batch_size: int = 100
    projection_poll_interval_ms: int = 1000
    enable_projection_checkpoints: bool = True
    checkpoint_frequency: int = 100

    # Performance
    enable_read_model_caching: bool = True
    read_cache_size_mb: int = 256
    enable_query_parallelization: bool = True
    max_concurrent_queries: int = 10


@dataclass
class DataConsistencyConfig:
    """Unified configuration for all data consistency patterns."""

    # Service identification
    service_name: str = "mmf-service"
    service_version: str = "1.0.0"
    environment: str = "development"

    # Core configurations
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    event_store: EventStoreConfig = field(default_factory=EventStoreConfig)
    message_broker: MessageBrokerConfig = field(default_factory=MessageBrokerConfig)

    # Pattern configurations
    saga: SagaConfig = field(default_factory=SagaConfig)
    outbox: OutboxConfig = field(default_factory=OutboxConfig)
    cqrs: CQRSConfig = field(default_factory=CQRSConfig)

    # Cross-pattern settings
    global_consistency_level: ConsistencyLevel = ConsistencyLevel.EVENTUAL
    enable_distributed_tracing: bool = True
    trace_correlation_header: str = "X-Correlation-ID"

    # Monitoring and observability
    enable_metrics: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    enable_health_checks: bool = True
    health_check_port: int = 8080
    health_check_path: str = "/health"

    # Security
    enable_encryption_at_rest: bool = False
    enable_encryption_in_transit: bool = True
    encryption_key_id: str | None = None

    # Development settings
    enable_debug_logging: bool = False
    log_level: str = "INFO"
    enable_sql_logging: bool = False

    @classmethod
    def from_env(cls) -> "DataConsistencyConfig":
        """Create configuration from environment variables."""
        config = cls()

        # Service settings
        config.service_name = os.getenv("MMF_SERVICE_NAME", config.service_name)
        config.service_version = os.getenv("MMF_SERVICE_VERSION", config.service_version)
        config.environment = os.getenv("MMF_ENVIRONMENT", config.environment)

        # Database configuration
        if db_url := os.getenv("DATABASE_URL"):
            config.database.connection_string = db_url
        config.database.pool_size = int(os.getenv("DB_POOL_SIZE", config.database.pool_size))
        config.database.echo_sql = os.getenv("DB_ECHO_SQL", "false").lower() == "true"

        # Event store configuration
        if es_url := os.getenv("EVENT_STORE_URL"):
            config.event_store.connection_string = es_url
        config.event_store.enable_snapshots = os.getenv("ES_ENABLE_SNAPSHOTS", "true").lower() == "true"

        # Message broker configuration
        config.message_broker.broker_type = os.getenv("MESSAGE_BROKER_TYPE", config.message_broker.broker_type)
        if kafka_brokers := os.getenv("KAFKA_BROKERS"):
            config.message_broker.brokers = kafka_brokers.split(",")

        # Saga configuration
        config.saga.worker_count = int(os.getenv("SAGA_WORKERS", config.saga.worker_count))
        config.saga.enable_parallel_execution = os.getenv("SAGA_PARALLEL", "true").lower() == "true"

        # CQRS configuration
        config.cqrs.enable_query_caching = os.getenv("CQRS_ENABLE_CACHE", "true").lower() == "true"
        config.cqrs.cache_ttl_seconds = int(os.getenv("CQRS_CACHE_TTL", config.cqrs.cache_ttl_seconds))

        # Outbox configuration
        config.outbox.worker_count = int(os.getenv("OUTBOX_WORKERS", config.outbox.worker_count))
        config.outbox.enable_dead_letter_queue = os.getenv("OUTBOX_DLQ", "true").lower() == "true"

        # Global settings
        consistency_level = os.getenv("CONSISTENCY_LEVEL", config.global_consistency_level.value)
        config.global_consistency_level = ConsistencyLevel(consistency_level)

        config.enable_metrics = os.getenv("ENABLE_METRICS", "true").lower() == "true"
        config.enable_debug_logging = os.getenv("DEBUG_LOGGING", "false").lower() == "true"
        config.log_level = os.getenv("LOG_LEVEL", config.log_level)

        return config

    @classmethod
    def from_file(cls, config_path: str | Path) -> "DataConsistencyConfig":
        """Load configuration from YAML or JSON file."""


        config_path = Path(config_path)

        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")

        with open(config_path) as f:
            if config_path.suffix.lower() in ['.yaml', '.yml']:
                data = yaml.safe_load(f)
            elif config_path.suffix.lower() == '.json':
                data = json.load(f)
            else:
                raise ValueError(f"Unsupported configuration file format: {config_path.suffix}")

        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "DataConsistencyConfig":
        """Create configuration from dictionary."""
        config = cls()

        # Service settings
        if 'service' in data:
            service_data = data['service']
            config.service_name = service_data.get('name', config.service_name)
            config.service_version = service_data.get('version', config.service_version)
            config.environment = service_data.get('environment', config.environment)

        # Database configuration
        if 'database' in data:
            db_data = data['database']
            config.database = DatabaseConfig(**db_data)

        # Event store configuration
        if 'event_store' in data:
            es_data = data['event_store']
            config.event_store = EventStoreConfig(**es_data)

        # Message broker configuration
        if 'message_broker' in data:
            mb_data = data['message_broker']
            config.message_broker = MessageBrokerConfig(**mb_data)

        # Pattern configurations
        if 'saga' in data:
            saga_data = data['saga']
            config.saga = SagaConfig(**saga_data)

        if 'outbox' in data:
            outbox_data = data['outbox']
            config.outbox = OutboxConfig(**outbox_data)

        if 'cqrs' in data:
            cqrs_data = data['cqrs']
            config.cqrs = CQRSConfig(**cqrs_data)

        # Global settings
        if 'global' in data:
            global_data = data['global']
            if 'consistency_level' in global_data:
                config.global_consistency_level = ConsistencyLevel(global_data['consistency_level'])
            config.enable_metrics = global_data.get('enable_metrics', config.enable_metrics)
            config.enable_debug_logging = global_data.get('enable_debug_logging', config.enable_debug_logging)
            config.log_level = global_data.get('log_level', config.log_level)

        return config

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            'service': {
                'name': self.service_name,
                'version': self.service_version,
                'environment': self.environment
            },
            'database': {
                'connection_string': self.database.connection_string,
                'pool_size': self.database.pool_size,
                'max_overflow': self.database.max_overflow,
                'pool_timeout': self.database.pool_timeout,
                'echo_sql': self.database.echo_sql,
                'transaction_timeout_seconds': self.database.transaction_timeout_seconds,
                'isolation_level': self.database.isolation_level
            },
            'event_store': {
                'connection_string': self.event_store.connection_string,
                'stream_page_size': self.event_store.stream_page_size,
                'enable_snapshots': self.event_store.enable_snapshots,
                'compression_enabled': self.event_store.compression_enabled,
                'batch_size': self.event_store.batch_size
            },
            'message_broker': {
                'broker_type': self.message_broker.broker_type,
                'brokers': self.message_broker.brokers,
                'kafka_security_protocol': self.message_broker.kafka_security_protocol,
                'enable_ssl': self.message_broker.enable_ssl
            },
            'saga': {
                'orchestrator_id': self.saga.orchestrator_id,
                'worker_count': self.saga.worker_count,
                'enable_parallel_execution': self.saga.enable_parallel_execution,
                'step_timeout_seconds': self.saga.step_timeout_seconds,
                'max_retry_attempts': self.saga.max_retry_attempts,
                'enable_dead_letter_queue': self.saga.enable_dead_letter_queue
            },
            'outbox': {
                'worker_count': self.outbox.worker_count,
                'enable_parallel_processing': self.outbox.enable_parallel_processing,
                'poll_interval_ms': self.outbox.poll_interval_ms,
                'enable_dead_letter_queue': self.outbox.enable_dead_letter_queue,
                'auto_cleanup_enabled': self.outbox.auto_cleanup_enabled
            },
            'cqrs': {
                'default_query_mode': self.cqrs.default_query_mode.value,
                'query_timeout_seconds': self.cqrs.query_timeout_seconds,
                'enable_query_caching': self.cqrs.enable_query_caching,
                'cache_ttl_seconds': self.cqrs.cache_ttl_seconds,
                'read_model_consistency': self.cqrs.read_model_consistency.value,
                'enable_read_model_versioning': self.cqrs.enable_read_model_versioning
            },
            'global': {
                'consistency_level': self.global_consistency_level.value,
                'enable_distributed_tracing': self.enable_distributed_tracing,
                'enable_metrics': self.enable_metrics,
                'metrics_port': self.metrics_port,
                'enable_health_checks': self.enable_health_checks,
                'enable_debug_logging': self.enable_debug_logging,
                'log_level': self.log_level
            }
        }

    def save_to_file(self, config_path: str | Path, format: str = "yaml") -> None:
        """Save configuration to file."""


        config_path = Path(config_path)
        config_data = self.to_dict()

        with open(config_path, 'w') as f:
            if format.lower() in ['yaml', 'yml']:
                yaml.dump(config_data, f, default_flow_style=False, sort_keys=False)
            elif format.lower() == 'json':
                json.dump(config_data, f, indent=2, sort_keys=False)
            else:
                raise ValueError(f"Unsupported format: {format}")

    def validate(self) -> list[str]:
        """Validate configuration and return list of issues."""
        issues = []

        # Validate database configuration
        if not self.database.connection_string:
            issues.append("Database connection string is required")

        if self.database.pool_size <= 0:
            issues.append("Database pool size must be positive")

        # Validate message broker configuration
        if not self.message_broker.brokers:
            issues.append("Message broker brokers list cannot be empty")

        # Validate saga configuration
        if self.saga.worker_count <= 0:
            issues.append("Saga worker count must be positive")

        if self.saga.step_timeout_seconds <= 0:
            issues.append("Saga step timeout must be positive")

        # Validate outbox configuration
        if self.outbox.worker_count <= 0:
            issues.append("Outbox worker count must be positive")

        if self.outbox.poll_interval_ms <= 0:
            issues.append("Outbox poll interval must be positive")

        # Validate CQRS configuration
        if self.cqrs.query_timeout_seconds <= 0:
            issues.append("CQRS query timeout must be positive")

        if self.cqrs.cache_ttl_seconds <= 0:
            issues.append("CQRS cache TTL must be positive")

        return issues


# Configuration profiles for different environments
def create_development_config() -> DataConsistencyConfig:
    """Create configuration optimized for development."""
    config = DataConsistencyConfig()

    # Development-friendly settings
    config.environment = "development"
    config.enable_debug_logging = True
    config.log_level = "DEBUG"
    config.database.echo_sql = True

    # Reduced resource usage
    config.saga.worker_count = 1
    config.outbox.worker_count = 1
    config.database.pool_size = 5

    # Faster feedback loops
    config.outbox.poll_interval_ms = 500
    config.saga.step_timeout_seconds = 10
    config.cqrs.cache_ttl_seconds = 60

    return config


def create_production_config() -> DataConsistencyConfig:
    """Create configuration optimized for production."""
    config = DataConsistencyConfig()

    # Production settings
    config.environment = "production"
    config.enable_debug_logging = False
    config.log_level = "INFO"
    config.database.echo_sql = False

    # Optimized resource usage
    config.saga.worker_count = 5
    config.outbox.worker_count = 3
    config.database.pool_size = 20
    config.database.max_overflow = 30

    # Production timeouts
    config.saga.step_timeout_seconds = 60
    config.saga.saga_timeout_seconds = 600
    config.cqrs.query_timeout_seconds = 30
    config.cqrs.cache_ttl_seconds = 300

    # Security and reliability
    config.enable_encryption_in_transit = True
    config.message_broker.enable_ssl = True
    config.saga.enable_dead_letter_queue = True
    config.outbox.enable_dead_letter_queue = True

    # Monitoring
    config.enable_metrics = True
    config.enable_health_checks = True
    config.enable_distributed_tracing = True

    return config


def create_testing_config() -> DataConsistencyConfig:
    """Create configuration optimized for testing."""
    config = DataConsistencyConfig()

    # Testing settings
    config.environment = "testing"
    config.enable_debug_logging = True
    config.log_level = "DEBUG"

    # In-memory where possible for speed
    config.saga.persistence_mode = PersistenceMode.IN_MEMORY
    config.cqrs.enable_query_caching = False  # Predictable behavior

    # Fast execution
    config.saga.worker_count = 1
    config.outbox.worker_count = 1
    config.outbox.poll_interval_ms = 100
    config.saga.step_timeout_seconds = 5

    # Minimal external dependencies
    config.message_broker.broker_type = "in_memory"
    config.database.connection_string = "sqlite:///:memory:"

    return config


# Global configuration instance
class DataConsistencyConfigService(ConfigService):
    """
    Typed configuration service for data consistency patterns.

    Replaces global configuration variables with proper dependency injection.
    """

    def __init__(self) -> None:
        super().__init__()
        self._data_config: DataConsistencyConfig | None = None

    def load_from_env(self) -> None:
        """Load configuration from environment variables."""
        self._data_config = DataConsistencyConfig.from_env()
        self._mark_loaded()

    def load_from_file(self, config_path: str | Path) -> None:
        """Load configuration from file."""
        self._data_config = DataConsistencyConfig.from_file(config_path)
        self._mark_loaded()

    def validate(self) -> bool:
        """Validate the current configuration."""
        return self._data_config is not None

    def get_data_config(self) -> DataConsistencyConfig:
        """Get the data consistency configuration."""
        if self._data_config is None:
            self.load_from_env()
        assert self._data_config is not None, "Configuration not loaded"
        return self._data_config

    def set_data_config(self, config: DataConsistencyConfig) -> None:
        """Set the data consistency configuration."""
        self._data_config = config
        self._mark_loaded()


def get_config_service() -> DataConsistencyConfigService:
    """Get the configuration service instance from DI container."""
    return container.get_or_create(
        "data_consistency_config_service",
        lambda: DataConsistencyConfigService()
    )


def get_config() -> DataConsistencyConfig:
    """Get the data consistency configuration - compatibility function."""
    return get_config_service().get_data_config()


def set_config(config: DataConsistencyConfig) -> None:
    """Set the data consistency configuration - compatibility function."""
    get_config_service().set_data_config(config)


def load_config_from_file(config_path: str | Path) -> DataConsistencyConfig:
    """Load and set configuration from file - compatibility function."""
    service = get_config_service()
    service.load_from_file(config_path)
    return service.get_data_config()
