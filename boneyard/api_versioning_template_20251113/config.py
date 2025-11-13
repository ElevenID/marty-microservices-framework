"""
Configuration management for API Versioning and Contract Testing service.

This module provides comprehensive configuration management with support for:
- Multiple versioning strategies
- Contract storage backends
- Testing configurations
- Monitoring and observability settings
- Security configurations
- Performance tuning
- Environment-specific settings

Author: Marty Framework Team
Version: 1.0.0
"""

import builtins
import logging
import os
from enum import Enum
from typing import Any, list

from pydantic import BaseModel, Field, root_validator, validator
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """Deployment environments."""

    DEVELOPMENT = "development"
    TESTING = "testing"
    STAGING = "staging"
    PRODUCTION = "production"


class VersioningStrategy(str, Enum):
    """API versioning strategies."""

    URL_PATH = "url_path"
    HEADER = "header"
    QUERY_PARAMETER = "query"
    MEDIA_TYPE = "media_type"
    CUSTOM_HEADER = "custom_header"


class ContractStorageBackend(str, Enum):
    """Contract storage backend types."""

    MEMORY = "memory"
    FILE = "file"
    POSTGRESQL = "postgresql"
    MONGODB = "mongodb"
    REDIS = "redis"
    S3 = "s3"


class LogLevel(str, Enum):
    """Logging levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class VersioningConfig(BaseModel):
    """API versioning configuration."""

    strategy: VersioningStrategy = VersioningStrategy.URL_PATH
    default_version: str = "v1"
    supported_versions: builtins.list[str] = Field(default_factory=lambda: ["v1", "v2"])
    version_prefix: str = "v"
    header_name: str = "X-API-Version"
    query_parameter_name: str = "version"
    media_type_pattern: str = r"application/vnd\.api\.v(\d+)\+json"
    enforce_version: bool = True
    allow_version_fallback: bool = True
    fallback_version: str = "v1"


class ContractConfig(BaseModel):
    """Contract management configuration."""

    storage_backend: ContractStorageBackend = ContractStorageBackend.MEMORY
    auto_generate_contracts: bool = True
    validate_requests: bool = True
    validate_responses: bool = True
    strict_validation: bool = False
    contract_discovery_enabled: bool = True
    contract_cache_ttl: int = 3600  # seconds
    max_contract_size: int = 10485760  # 10MB
    contract_versioning: bool = True
    backup_contracts: bool = True


class TestingConfig(BaseModel):
    """Contract testing configuration."""

    enabled: bool = True
    auto_test_on_deploy: bool = True
    test_timeout: int = 30  # seconds
    max_concurrent_tests: int = 10
    retry_failed_tests: bool = True
    max_test_retries: int = 3
    test_environments: builtins.list[str] = Field(
        default_factory=lambda: ["staging", "production"]
    )
    consumer_test_enabled: bool = True
    provider_test_enabled: bool = True
    contract_test_schedule: str = "0 */6 * * *"  # Every 6 hours
    test_data_retention_days: int = 30


class StorageConfig(BaseModel):
    """Storage backend configuration."""

    # PostgreSQL settings
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "api_contracts"
    postgres_user: str = "postgres"
    postgres_password: str = ""
    postgres_ssl_mode: str = "prefer"
    postgres_pool_size: int = 10
    postgres_max_overflow: int = 20

    # MongoDB settings
    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_database: str = "api_contracts"
    mongodb_collection_prefix: str = "marty_"
    mongodb_replica_set: str | None = None
    mongodb_auth_source: str = "admin"

    # Redis settings
    redis_url: str = "redis://localhost:6379"
    redis_db: int = 0
    redis_password: str | None = None
    redis_ssl: bool = False
    redis_pool_size: int = 10

    # File storage settings
    file_storage_path: str = "./contracts"
    file_backup_enabled: bool = True
    file_backup_path: str = "./contracts/backup"
    file_compression: bool = True

    # S3 settings
    s3_bucket: str = "api-contracts"
    s3_region: str = "us-east-1"
    s3_access_key: str | None = None
    s3_secret_key: str | None = None
    s3_endpoint_url: str | None = None
    s3_use_ssl: bool = True
    s3_prefix: str = "contracts/"


class SecurityConfig(BaseModel):
    """Security configuration."""

    enable_authentication: bool = False
    authentication_backend: str = "jwt"  # jwt, api_key, oauth2
    jwt_secret_key: str = Field(default_factory=lambda: os.urandom(32).hex())
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    api_key_header: str = "X-API-Key"
    require_https: bool = False
    cors_origins: builtins.list[str] = Field(default_factory=lambda: ["*"])
    cors_methods: builtins.list[str] = Field(
        default_factory=lambda: ["GET", "POST", "PUT", "DELETE"]
    )
    cors_headers: builtins.list[str] = Field(default_factory=lambda: ["*"])
    rate_limiting_enabled: bool = True
    rate_limit_requests_per_minute: int = 100
    rate_limit_storage: str = "memory"  # memory, redis
    audit_logging: bool = True
    encrypt_sensitive_data: bool = True
    data_encryption_key: str = Field(default_factory=lambda: os.urandom(32).hex())


class MonitoringConfig(BaseModel):
    """Monitoring and observability configuration."""

    metrics_enabled: bool = True
    metrics_endpoint: str = "/metrics"
    prometheus_pushgateway_url: str | None = None
    tracing_enabled: bool = True
    tracing_backend: str = "jaeger"  # jaeger, zipkin, datadog
    jaeger_endpoint: str = "http://localhost:14268/api/traces"
    jaeger_service_name: str = "api-versioning-service"
    sampling_rate: float = 0.1
    log_level: LogLevel = LogLevel.INFO
    structured_logging: bool = True
    log_format: str = "json"  # json, text
    health_check_enabled: bool = True
    health_check_endpoint: str = "/health"
    readiness_check_enabled: bool = True
    readiness_check_endpoint: str = "/ready"


class PerformanceConfig(BaseModel):
    """Performance optimization configuration."""

    enable_caching: bool = True
    cache_backend: str = "redis"  # memory, redis, memcached
    cache_ttl: int = 3600  # seconds
    cache_key_prefix: str = "api_versioning:"
    max_request_size: int = 10485760  # 10MB
    request_timeout: int = 30  # seconds
    worker_processes: int = 1
    worker_connections: int = 1000
    keepalive_timeout: int = 5
    graceful_timeout: int = 30
    max_concurrent_requests: int = 1000
    connection_pool_size: int = 20
    enable_compression: bool = True
    compression_level: int = 6


class NotificationConfig(BaseModel):
    """Notification configuration."""

    enabled: bool = False
    webhook_urls: builtins.list[str] = Field(default_factory=list)
    slack_webhook_url: str | None = None
    email_enabled: bool = False
    smtp_host: str = "localhost"
    smtp_port: int = 587
    smtp_username: str | None = None
    smtp_password: str | None = None
    smtp_use_tls: bool = True
    notification_channels: builtins.list[str] = Field(default_factory=lambda: ["webhook"])
    alert_on_breaking_changes: bool = True
    alert_on_test_failures: bool = True
    alert_on_deprecated_usage: bool = False


class APIVersioningSettings(BaseSettings):
    """Main configuration settings for the API Versioning service."""

    # Basic settings
    service_name: str = "api-versioning-service"
    environment: Environment = Environment.DEVELOPMENT
    debug: bool = False

    # Service configuration
    host: str = "0.0.0.0"
    port: int = 8060
    reload: bool = False
    workers: int = 1

    # Feature configurations
    versioning: VersioningConfig = Field(default_factory=VersioningConfig)
    contracts: ContractConfig = Field(default_factory=ContractConfig)
    testing: TestingConfig = Field(default_factory=TestingConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    security: SecurityConfig = Field(default_factory=SecurityConfig)
    monitoring: MonitoringConfig = Field(default_factory=MonitoringConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)
    notifications: NotificationConfig = Field(default_factory=NotificationConfig)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        env_nested_delimiter = "__"
        case_sensitive = False

    @root_validator
    def validate_environment_settings(cls, values):
        """Validate settings based on environment."""
        env = values.get("environment")

        if env == Environment.PRODUCTION:
            # Production-specific validations
            if values.get("debug"):
                raise ValueError("Debug mode should not be enabled in production")

            security = values.get("security", SecurityConfig())
            if not security.require_https:
                logging.warning("HTTPS should be required in production")

            if security.jwt_secret_key == SecurityConfig().jwt_secret_key:
                raise ValueError("JWT secret key must be changed in production")

        return values

    @validator("port")
    def validate_port(cls, v):
        """Validate port number."""
        if not (1 <= v <= 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v

    def get_database_url(self) -> str:
        """Get database connection URL based on backend."""
        if self.contracts.storage_backend == ContractStorageBackend.POSTGRESQL:
            return (
                f"postgresql://{self.storage.postgres_user}:"
                f"{self.storage.postgres_password}@"
                f"{self.storage.postgres_host}:{self.storage.postgres_port}/"
                f"{self.storage.postgres_db}"
            )
        elif self.contracts.storage_backend == ContractStorageBackend.MONGODB:
            return self.storage.mongodb_url
        elif self.contracts.storage_backend == ContractStorageBackend.REDIS:
            return self.storage.redis_url
        else:
            return ""

    def get_cache_config(self) -> builtins.dict[str, Any]:
        """Get cache configuration."""
        if self.performance.cache_backend == "redis":
            return {
                "backend": "redis",
                "url": self.storage.redis_url,
                "ttl": self.performance.cache_ttl,
                "prefix": self.performance.cache_key_prefix,
            }
        else:
            return {
                "backend": "memory",
                "ttl": self.performance.cache_ttl,
                "prefix": self.performance.cache_key_prefix,
            }

    def get_tracing_config(self) -> builtins.dict[str, Any]:
        """Get tracing configuration."""
        return {
            "enabled": self.monitoring.tracing_enabled,
            "backend": self.monitoring.tracing_backend,
            "endpoint": self.monitoring.jaeger_endpoint,
            "service_name": self.monitoring.jaeger_service_name,
            "sampling_rate": self.monitoring.sampling_rate,
        }

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment == Environment.PRODUCTION

    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment == Environment.DEVELOPMENT

    def get_supported_versions(self) -> builtins.list[str]:
        """Get list of supported API versions."""
        return self.versioning.supported_versions

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert settings to dictionary."""
        return self.dict()


# Environment-specific configurations
class DevelopmentConfig(APIVersioningSettings):
    """Development environment configuration."""

    environment: Environment = Environment.DEVELOPMENT
    debug: bool = True
    reload: bool = True

    class Config:
        env_file = ".env.development"


class TestingConfig(APIVersioningSettings):
    """Testing environment configuration."""

    environment: Environment = Environment.TESTING
    debug: bool = True

    class Config:
        env_file = ".env.testing"


class StagingConfig(APIVersioningSettings):
    """Staging environment configuration."""

    environment: Environment = Environment.STAGING
    debug: bool = False

    class Config:
        env_file = ".env.staging"


class ProductionConfig(APIVersioningSettings):
    """Production environment configuration."""

    environment: Environment = Environment.PRODUCTION
    debug: bool = False
    reload: bool = False
    workers: int = 4

    class Config:
        env_file = ".env.production"


def get_settings() -> APIVersioningSettings:
    """Get configuration settings based on environment."""
    env = os.getenv("ENVIRONMENT", "development").lower()

    if env == "production":
        return ProductionConfig()
    elif env == "staging":
        return StagingConfig()
    elif env == "testing":
        return TestingConfig()
    else:
        return DevelopmentConfig()


def create_sample_config_file(
    file_path: str = ".env", environment: str = "development"
):
    """Create a sample configuration file."""
    config_content = f"""# API Versioning Service Configuration
# Environment: {environment}

# Basic settings
SERVICE_NAME=api-versioning-service
ENVIRONMENT={environment}
DEBUG={"true" if environment in ["development", "testing"] else "false"}

# Service configuration
HOST=0.0.0.0
PORT=8060
RELOAD={"true" if environment == "development" else "false"}
WORKERS={"1" if environment == "development" else "4"}

# Versioning configuration
VERSIONING__STRATEGY=url_path
VERSIONING__DEFAULT_VERSION=v1
VERSIONING__SUPPORTED_VERSIONS=["v1", "v2"]
VERSIONING__ENFORCE_VERSION=true

# Contract configuration
CONTRACTS__STORAGE_BACKEND=memory
CONTRACTS__AUTO_GENERATE_CONTRACTS=true
CONTRACTS__VALIDATE_REQUESTS=true
CONTRACTS__VALIDATE_RESPONSES=true

# Testing configuration
TESTING__ENABLED=true
TESTING__AUTO_TEST_ON_DEPLOY=true
TESTING__TEST_TIMEOUT=30
TESTING__MAX_CONCURRENT_TESTS=10

# Storage configuration
STORAGE__POSTGRES_HOST=localhost
STORAGE__POSTGRES_PORT=5432
STORAGE__POSTGRES_DB=api_contracts
STORAGE__REDIS_URL=redis://localhost:6379

# Security configuration
SECURITY__ENABLE_AUTHENTICATION=false
SECURITY__REQUIRE_HTTPS={"true" if environment == "production" else "false"}
SECURITY__RATE_LIMITING_ENABLED=true
SECURITY__RATE_LIMIT_REQUESTS_PER_MINUTE=100

# Monitoring configuration
MONITORING__METRICS_ENABLED=true
MONITORING__TRACING_ENABLED=true
MONITORING__LOG_LEVEL={"INFO" if environment == "production" else "DEBUG"}
MONITORING__STRUCTURED_LOGGING=true

# Performance configuration
PERFORMANCE__ENABLE_CACHING=true
PERFORMANCE__CACHE_BACKEND=redis
PERFORMANCE__MAX_REQUEST_SIZE=10485760
PERFORMANCE__REQUEST_TIMEOUT=30

# Notification configuration
NOTIFICATIONS__ENABLED=false
NOTIFICATIONS__ALERT_ON_BREAKING_CHANGES=true
NOTIFICATIONS__ALERT_ON_TEST_FAILURES=true
"""

    with open(file_path, "w") as f:
        f.write(config_content)

    print(f"Sample configuration file created: {file_path}")


if __name__ == "__main__":
    # Create sample configuration files for different environments
    environments = ["development", "testing", "staging", "production"]

    for env in environments:
        create_sample_config_file(f".env.{env}", env)

    # Display current configuration
    settings = get_settings()
    print("Current Configuration:")
    print(f"Environment: {settings.environment}")
    print(f"Service: {settings.service_name}")
    print(f"Host: {settings.host}:{settings.port}")
    print(f"Debug: {settings.debug}")
    print(f"Versioning Strategy: {settings.versioning.strategy}")
    print(f"Storage Backend: {settings.contracts.storage_backend}")
