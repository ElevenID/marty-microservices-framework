"""
Configuration Management for Saga Orchestrator

This module provides comprehensive configuration management for the saga orchestrator
with support for different environments, storage backends, and operational settings.

Key Features:
- Environment-specific configurations
- Multiple storage backend options
- Security and authentication settings
- Monitoring and observability configuration
- Circuit breaker and resilience patterns
- Performance tuning parameters
"""

import asyncio
import builtins
import concurrent.futures
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# Import unified configuration system
from marty_msf.framework.config import (
    ConfigurationStrategy,
    Environment,
    create_unified_config_manager,
)


class StorageBackend(Enum):
    """Available storage backends for saga state persistence."""

    MEMORY = "memory"
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    REDIS = "redis"
    ELASTICSEARCH = "elasticsearch"


class SecurityMode(Enum):
    """Security modes for saga orchestrator."""

    NONE = "none"
    API_KEY = "api_key"
    JWT = "jwt"
    MUTUAL_TLS = "mutual_tls"
    OAUTH2 = "oauth2"


class LogLevel(Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class DatabaseConfig:
    """Database configuration for different storage backends."""

    # PostgreSQL Configuration
    postgresql_host: str = "localhost"
    postgresql_port: int = 5432
    postgresql_database: str = "saga_orchestrator"
    postgresql_user: str = "saga_user"
    postgresql_password: str = "saga_password"
    postgresql_pool_size: int = 10
    postgresql_max_overflow: int = 20
    postgresql_pool_timeout: int = 30
    postgresql_ssl_mode: str = "prefer"

    # MongoDB Configuration
    mongodb_host: str = "localhost"
    mongodb_port: int = 27017
    mongodb_database: str = "saga_orchestrator"
    mongodb_user: str | None = None
    mongodb_password: str | None = None
    mongodb_auth_source: str = "admin"
    mongodb_replica_set: str | None = None
    mongodb_ssl: bool = False
    mongodb_ssl_cert_reqs: str = "CERT_REQUIRED"
    mongodb_connection_timeout: int = 20000
    mongodb_server_selection_timeout: int = 20000

    # Redis Configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_database: int = 0
    redis_password: str | None = None
    redis_ssl: bool = False
    redis_ssl_cert_reqs: str | None = None
    redis_ssl_ca_certs: str | None = None
    redis_ssl_certfile: str | None = None
    redis_ssl_keyfile: str | None = None
    redis_connection_pool_size: int = 10
    redis_retry_on_timeout: bool = True
    redis_socket_keepalive: bool = True
    redis_socket_keepalive_options: builtins.dict[str, int] = field(default_factory=lambda: {})

    # Elasticsearch Configuration
    elasticsearch_hosts: builtins.list[str] = field(default_factory=lambda: ["localhost:9200"])
    elasticsearch_username: str | None = None
    elasticsearch_password: str | None = None
    elasticsearch_use_ssl: bool = False
    elasticsearch_verify_certs: bool = True
    elasticsearch_ca_certs: str | None = None
    elasticsearch_client_cert: str | None = None
    elasticsearch_client_key: str | None = None
    elasticsearch_timeout: int = 30
    elasticsearch_max_retries: int = 3
    elasticsearch_retry_on_timeout: bool = True


@dataclass
class SecurityConfig:
    """Security configuration for saga orchestrator."""

    security_mode: SecurityMode = SecurityMode.NONE

    # API Key Configuration
    api_keys: builtins.list[str] = field(default_factory=list)
    api_key_header: str = "X-API-Key"
    api_key_query_param: str = "api_key"

    # JWT Configuration
    jwt_secret_key: str | None = None
    jwt_algorithm: str = "HS256"
    jwt_expiration_minutes: int = 60
    jwt_issuer: str | None = None
    jwt_audience: str | None = None

    # TLS Configuration
    tls_enabled: bool = False
    tls_cert_file: str | None = None
    tls_key_file: str | None = None
    tls_ca_file: str | None = None
    tls_verify_client_cert: bool = False
    tls_ciphers: str | None = None

    # OAuth2 Configuration
    oauth2_provider_url: str | None = None
    oauth2_client_id: str | None = None
    oauth2_client_secret: str | None = None
    oauth2_scope: builtins.list[str] = field(default_factory=list)
    oauth2_token_url: str | None = None
    oauth2_authorization_url: str | None = None

    # RBAC Configuration
    rbac_enabled: bool = False
    rbac_roles: builtins.dict[str, builtins.list[str]] = field(default_factory=dict)
    rbac_permissions: builtins.dict[str, builtins.list[str]] = field(default_factory=dict)


@dataclass
class MonitoringConfig:
    """Monitoring and observability configuration."""

    # Metrics Configuration
    metrics_enabled: bool = True
    metrics_port: int = 9090
    metrics_path: str = "/metrics"
    metrics_namespace: str = "saga_orchestrator"

    # Prometheus Configuration
    prometheus_pushgateway_url: str | None = None
    prometheus_pushgateway_job: str = "saga_orchestrator"
    prometheus_pushgateway_interval: int = 60

    # Tracing Configuration
    tracing_enabled: bool = False
    tracing_service_name: str = "saga-orchestrator"
    tracing_sample_rate: float = 0.1

    # Jaeger Configuration
    jaeger_agent_host: str = "localhost"
    jaeger_agent_port: int = 6831
    jaeger_collector_endpoint: str | None = None
    jaeger_username: str | None = None
    jaeger_password: str | None = None

    # Zipkin Configuration
    zipkin_endpoint: str | None = None

    # OTLP Configuration
    otlp_endpoint: str | None = None
    otlp_headers: builtins.dict[str, str] = field(default_factory=dict)
    otlp_compression: str | None = None

    # Logging Configuration
    log_level: LogLevel = LogLevel.INFO
    log_format: str = "json"  # json or console
    log_file: str | None = None
    log_max_size: int = 100  # MB
    log_backup_count: int = 5
    log_compression: bool = True

    # Health Check Configuration
    health_check_interval: int = 30
    health_check_timeout: int = 5
    health_check_retries: int = 3

    # Alerting Configuration
    alerting_enabled: bool = False
    alert_webhook_url: str | None = None
    alert_slack_webhook: str | None = None
    alert_email_smtp_host: str | None = None
    alert_email_smtp_port: int = 587
    alert_email_username: str | None = None
    alert_email_password: str | None = None
    alert_email_from: str | None = None
    alert_email_to: builtins.list[str] = field(default_factory=list)


@dataclass
class ResilienceConfig:
    """Resilience and fault tolerance configuration."""

    # Circuit Breaker Configuration
    circuit_breaker_enabled: bool = True
    circuit_breaker_failure_threshold: int = 5
    circuit_breaker_recovery_timeout: int = 60
    circuit_breaker_expected_exception: str = "Exception"
    circuit_breaker_fallback_enabled: bool = True

    # Retry Configuration
    retry_enabled: bool = True
    retry_max_attempts: int = 3
    retry_delay_base: float = 1.0
    retry_delay_max: float = 60.0
    retry_backoff_factor: float = 2.0
    retry_jitter: bool = True

    # Timeout Configuration
    default_request_timeout: int = 30
    default_step_timeout: int = 60
    default_saga_timeout: int = 300
    compensation_timeout: int = 60

    # Rate Limiting Configuration
    rate_limiting_enabled: bool = False
    rate_limit_requests_per_minute: int = 100
    rate_limit_burst_size: int = 10
    rate_limit_strategy: str = (
        "token_bucket"  # token_bucket, sliding_window, fixed_window
    )

    # Bulkhead Configuration
    bulkhead_enabled: bool = False
    bulkhead_max_concurrent_sagas: int = 100
    bulkhead_max_concurrent_steps: int = 50
    bulkhead_queue_size: int = 200
    bulkhead_timeout: int = 30


@dataclass
class PerformanceConfig:
    """Performance tuning configuration."""

    # Concurrency Configuration
    max_concurrent_sagas: int = 100
    max_concurrent_steps_per_saga: int = 10
    worker_pool_size: int = 10
    thread_pool_size: int = 20

    # HTTP Client Configuration
    http_client_timeout: int = 30
    http_client_max_connections: int = 100
    http_client_max_keepalive_connections: int = 20
    http_client_keepalive_expiry: int = 30
    http_client_retries: int = 3

    # Caching Configuration
    cache_enabled: bool = True
    cache_backend: str = "memory"  # memory, redis
    cache_ttl: int = 300
    cache_max_size: int = 1000

    # Queue Configuration
    queue_max_size: int = 1000
    queue_timeout: int = 30
    queue_batch_size: int = 10
    queue_consumer_count: int = 5

    # Background Task Configuration
    background_task_enabled: bool = True
    background_task_interval: int = 60
    background_task_batch_size: int = 100

    # Cleanup Configuration
    cleanup_enabled: bool = True
    cleanup_interval: int = 3600  # 1 hour
    cleanup_retention_days: int = 30
    cleanup_batch_size: int = 1000


@dataclass
class SagaOrchestratorConfig:
    """Main configuration for saga orchestrator."""

    # Basic Configuration
    service_name: str = "saga-orchestrator"
    service_version: str = "1.0.0"
    environment: str = "development"
    debug: bool = False

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8080
    workers: int = 1
    reload: bool = False

    # Storage Configuration
    storage_backend: StorageBackend = StorageBackend.MEMORY
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    # Security Configuration
    security: SecurityConfig = field(default_factory=SecurityConfig)

    # Monitoring Configuration
    monitoring: MonitoringConfig = field(default_factory=MonitoringConfig)

    # Resilience Configuration
    resilience: ResilienceConfig = field(default_factory=ResilienceConfig)

    # Performance Configuration
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)

    # Feature Flags
    features: builtins.dict[str, bool] = field(
        default_factory=lambda: {
            "saga_visualization": True,
            "step_parallel_execution": True,
            "compensation_strategies": True,
            "event_sourcing": False,
            "saga_versioning": False,
            "step_conditions": True,
            "saga_templates": True,
            "api_documentation": True,
            "health_checks": True,
            "metrics_collection": True,
            "distributed_locks": False,
            "saga_scheduling": False,
            "webhook_notifications": False,
        }
    )

    # Custom Configuration
    custom: builtins.dict[str, Any] = field(default_factory=dict)

    def get_database_url(self) -> str:
        """Get database connection URL based on storage backend."""
        if self.storage_backend == StorageBackend.POSTGRESQL:
            return (
                f"postgresql://{self.database.postgresql_user}:"
                f"{self.database.postgresql_password}@"
                f"{self.database.postgresql_host}:"
                f"{self.database.postgresql_port}/"
                f"{self.database.postgresql_database}"
            )

        elif self.storage_backend == StorageBackend.MONGODB:
            auth = ""
            if self.database.mongodb_user and self.database.mongodb_password:
                auth = f"{self.database.mongodb_user}:{self.database.mongodb_password}@"

            return (
                f"mongodb://{auth}"
                f"{self.database.mongodb_host}:"
                f"{self.database.mongodb_port}/"
                f"{self.database.mongodb_database}"
            )

        elif self.storage_backend == StorageBackend.REDIS:
            auth = (
                f":{self.database.redis_password}@"
                if self.database.redis_password
                else ""
            )
            return (
                f"redis://{auth}"
                f"{self.database.redis_host}:"
                f"{self.database.redis_port}/"
                f"{self.database.redis_database}"
            )

        elif self.storage_backend == StorageBackend.ELASTICSEARCH:
            host = (
                self.database.elasticsearch_hosts[0]
                if self.database.elasticsearch_hosts
                else "localhost:9200"
            )
            scheme = "https" if self.database.elasticsearch_use_ssl else "http"
            auth = ""
            if (
                self.database.elasticsearch_username
                and self.database.elasticsearch_password
            ):
                auth = f"{self.database.elasticsearch_username}:{self.database.elasticsearch_password}@"

            return f"{scheme}://{auth}{host}"

        else:
            return "memory://"

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"

    def get_log_level(self) -> str:
        """Get logging level as string."""
        return self.monitoring.log_level.value


# Pydantic model for unified configuration
class UnifiedSagaOrchestratorConfig(BaseModel):
    """Unified configuration for saga orchestrator using Pydantic."""

    # Basic service settings
    service_name: str = Field(default="saga-orchestrator")
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8080)
    debug: bool = Field(default=False)
    reload: bool = Field(default=False)
    environment: str = Field(default="development")

    # Database and storage
    database_url: str = Field(default="${SECRET:database_url}")
    storage_backend: str = Field(default="memory")

    # Security
    jwt_secret_key: str = Field(default="${SECRET:jwt_secret}")
    api_key: str = Field(default="${SECRET:api_key}")

    # Saga-specific settings
    max_concurrent_sagas: int = Field(default=100)
    default_saga_timeout: int = Field(default=300)  # 5 minutes
    default_step_timeout: int = Field(default=30)   # 30 seconds

    # Monitoring
    metrics_enabled: bool = Field(default=True)
    tracing_enabled: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # Resilience
    circuit_breaker_enabled: bool = Field(default=True)
    retry_max_attempts: int = Field(default=3)
    rate_limiting_enabled: bool = Field(default=True)


# Factory function for unified configuration
async def create_unified_saga_config(
    config_dir: str = "config",
    environment: str = "development"
) -> UnifiedSagaOrchestratorConfig:
    """Create unified saga orchestrator configuration."""
    config_manager = create_unified_config_manager(
        service_name="saga-orchestrator",
        environment=Environment(environment),
        config_class=UnifiedSagaOrchestratorConfig,
        config_dir=config_dir,
        strategy=ConfigurationStrategy.AUTO_DETECT
    )

    await config_manager.initialize()
    return await config_manager.get_configuration()


def create_development_config() -> SagaOrchestratorConfig:
    """Create development environment configuration."""
    config = SagaOrchestratorConfig(
        environment="development",
        debug=True,
        reload=True,
        storage_backend=StorageBackend.MEMORY,
    )

    # Development-specific settings
    config.monitoring.log_level = LogLevel.DEBUG
    config.monitoring.metrics_enabled = True
    config.monitoring.tracing_enabled = False

    config.resilience.circuit_breaker_enabled = False
    config.resilience.retry_max_attempts = 2
    config.resilience.rate_limiting_enabled = False

    config.performance.max_concurrent_sagas = 10
    config.performance.cache_enabled = False

    config.security.security_mode = SecurityMode.NONE

    return config


def create_testing_config() -> SagaOrchestratorConfig:
    """Create testing environment configuration."""
    config = SagaOrchestratorConfig(
        environment="testing", debug=True, storage_backend=StorageBackend.MEMORY
    )

    # Testing-specific settings
    config.monitoring.log_level = LogLevel.WARNING
    config.monitoring.metrics_enabled = False
    config.monitoring.tracing_enabled = False

    config.resilience.default_request_timeout = 5
    config.resilience.default_step_timeout = 10
    config.resilience.default_saga_timeout = 30

    config.performance.max_concurrent_sagas = 5
    config.performance.http_client_timeout = 5

    return config


def create_production_config() -> SagaOrchestratorConfig:
    """Create production environment configuration."""
    config = SagaOrchestratorConfig(
        environment="production",
        debug=False,
        reload=False,
        workers=4,
        storage_backend=StorageBackend.POSTGRESQL,
    )

    # Production-specific settings
    config.monitoring.log_level = LogLevel.INFO
    config.monitoring.metrics_enabled = True
    config.monitoring.tracing_enabled = True
    config.monitoring.tracing_sample_rate = 0.01  # 1% sampling
    config.monitoring.alerting_enabled = True

    config.security.security_mode = SecurityMode.JWT
    config.security.tls_enabled = True
    config.security.rbac_enabled = True

    config.resilience.circuit_breaker_enabled = True
    config.resilience.retry_enabled = True
    config.resilience.rate_limiting_enabled = True
    config.resilience.bulkhead_enabled = True

    config.performance.max_concurrent_sagas = 1000
    config.performance.cache_enabled = True
    config.performance.cache_backend = "redis"
    config.performance.background_task_enabled = True
    config.performance.cleanup_enabled = True

    # Production database settings
    config.database.postgresql_pool_size = 20
    config.database.postgresql_max_overflow = 50
    config.database.postgresql_ssl_mode = "require"

    return config


def create_kubernetes_config() -> SagaOrchestratorConfig:
    """Create Kubernetes environment configuration."""
    config = create_production_config()
    config.environment = "kubernetes"

    # Kubernetes-specific settings
    config.host = "0.0.0.0"
    config.port = 8080

    config.monitoring.metrics_port = 9090
    config.monitoring.health_check_interval = 10

    # Use environment variables for sensitive configuration
    config.database.postgresql_host = os.getenv("POSTGRES_HOST", "postgres")
    config.database.postgresql_user = os.getenv("POSTGRES_USER", "saga_user")
    config.database.postgresql_password = os.getenv(
        "POSTGRES_PASSWORD", "saga_password"
    )
    config.database.postgresql_database = os.getenv("POSTGRES_DB", "saga_orchestrator")

    config.security.jwt_secret_key = os.getenv("JWT_SECRET_KEY")
    config.security.api_keys = (
        os.getenv("API_KEYS", "").split(",") if os.getenv("API_KEYS") else []
    )

    config.monitoring.jaeger_agent_host = os.getenv("JAEGER_AGENT_HOST", "jaeger-agent")
    config.monitoring.jaeger_collector_endpoint = os.getenv("JAEGER_COLLECTOR_ENDPOINT")

    return config


def get_unified_config() -> UnifiedSagaOrchestratorConfig:
    """Get unified configuration (synchronous helper)."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is already running, create task
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, create_unified_saga_config())
                return future.result()
        else:
            return asyncio.run(create_unified_saga_config())
    except Exception as e:
        print(f"Failed to load unified config, falling back to env config: {e}")
        return load_config_from_env()


def load_config_from_env() -> SagaOrchestratorConfig:
    """Load configuration from environment variables (legacy)."""
    environment = os.getenv("ENVIRONMENT", "development").lower()

    if environment == "production":
        config = create_production_config()
    elif environment == "testing":
        config = create_testing_config()
    elif environment == "kubernetes":
        config = create_kubernetes_config()
    else:
        config = create_development_config()

    # Override with environment variables
    config.host = os.getenv("HOST", config.host)
    config.port = int(os.getenv("PORT", config.port))
    config.debug = os.getenv("DEBUG", str(config.debug)).lower() == "true"

    # Storage configuration
    storage_backend = os.getenv("STORAGE_BACKEND", config.storage_backend.value)
    config.storage_backend = StorageBackend(storage_backend)

    # Security configuration
    security_mode = os.getenv("SECURITY_MODE", config.security.security_mode.value)
    config.security.security_mode = SecurityMode(security_mode)

    if os.getenv("JWT_SECRET_KEY"):
        config.security.jwt_secret_key = os.getenv("JWT_SECRET_KEY")

    if os.getenv("API_KEYS"):
        config.security.api_keys = os.getenv("API_KEYS").split(",")

    # Monitoring configuration
    if os.getenv("LOG_LEVEL"):
        config.monitoring.log_level = LogLevel(os.getenv("LOG_LEVEL"))

    config.monitoring.metrics_enabled = (
        os.getenv("METRICS_ENABLED", str(config.monitoring.metrics_enabled)).lower()
        == "true"
    )
    config.monitoring.tracing_enabled = (
        os.getenv("TRACING_ENABLED", str(config.monitoring.tracing_enabled)).lower()
        == "true"
    )

    return config


# Default configuration instance (for backward compatibility)
config = load_config_from_env()
