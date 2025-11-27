"""
Example usage of the Unified Configuration and Secret Management System.

This example demonstrates how to use the unified configuration manager
in different hosting environments with automatic backend detection.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from marty_msf.framework.config.manager import Environment
from marty_msf.framework.config.unified import (
    ConfigurationStrategy,
    EnvironmentDetector,
    HostingEnvironment,
    SecretBackend,
    create_unified_config_manager,
)
from pydantic import BaseModel, Field

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Example configuration models
class DatabaseConfig(BaseModel):
    """Database configuration with secret references."""
    host: str = "localhost"
    port: int = 5432
    username: str = "app_user"
    password: str = "${SECRET:database/password}"  # Secret reference
    database: str = "myapp"
    ssl_mode: str = "prefer"


class RedisConfig(BaseModel):
    """Redis configuration."""
    host: str = "localhost"
    port: int = 6379
    password: Optional[str] = "${SECRET:redis/password}"  # Secret reference
    db: int = 0


class ServiceConfig(BaseModel):
    """Complete service configuration."""
    service_name: str = Field(default="example-service")
    environment: str = Field(default="development")
    debug: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    # External service credentials
    api_key: str = "${SECRET:external_api/key}"
    jwt_secret: str = "${SECRET:jwt/signing_key}"

    # Database configuration
    database: DatabaseConfig = Field(default_factory=DatabaseConfig)
    redis: RedisConfig = Field(default_factory=RedisConfig)

    # Feature flags
    enable_metrics: bool = True
    enable_tracing: bool = False


async def demonstrate_auto_detection():
    """Demonstrate automatic environment detection and configuration."""
    logger.info("=== Auto-Detection Demo ===")

    # Detect current environment
    hosting_env = EnvironmentDetector.detect_hosting_environment()
    available_backends = EnvironmentDetector.detect_available_backends()
    recommended_backends = EnvironmentDetector.get_recommended_backends(hosting_env)

    logger.info(f"Hosting Environment: {hosting_env.value}")
    logger.info(f"Available Backends: {[b.value for b in available_backends]}")
    logger.info(f"Recommended Backends: {[b.value for b in recommended_backends]}")

    # Create configuration manager with auto-detection
    config_manager = create_unified_config_manager(
        service_name="demo-service",
        environment=Environment.DEVELOPMENT,
        config_class=ServiceConfig,
        strategy=ConfigurationStrategy.AUTO_DETECT,
        config_dir="examples/config"  # Would contain base.yaml, development.yaml, etc.
    )

    # Initialize and get configuration
    await config_manager.initialize()

    # Check backend health
    health_status = await config_manager.health_check()
    logger.info(f"Backend Health Status: {health_status}")

    # Demonstrate secret management
    await demonstrate_secret_operations(config_manager)

    return config_manager


async def demonstrate_manual_configuration():
    """Demonstrate manual backend configuration for specific environments."""
    logger.info("=== Manual Configuration Demo ===")

    # Example: AWS environment with specific backends
    config_manager = create_unified_config_manager(
        service_name="aws-service",
        environment=Environment.PRODUCTION,
        config_class=ServiceConfig,
        strategy=ConfigurationStrategy.EXPLICIT,
        # AWS-specific configuration
        enable_aws_secrets=True,
        aws_region="us-west-2",
        # Fallback options
        enable_file_secrets=False,  # Disable for production
        # Vault for additional secrets
        enable_vault=True,
        vault_config={
            "url": "https://vault.company.com:8200",
            "auth_method": "aws_iam",
            "role": "my-service-role"
        }
    )

    await config_manager.initialize()
    return config_manager


async def demonstrate_multi_cloud_setup():
    """Demonstrate configuration for multi-cloud deployment."""
    logger.info("=== Multi-Cloud Setup Demo ===")

    # Configuration that works across AWS, GCP, and Azure
    config_manager = create_unified_config_manager(
        service_name="multi-cloud-service",
        environment=Environment.PRODUCTION,
        config_class=ServiceConfig,
        strategy=ConfigurationStrategy.FALLBACK,
        # Enable all cloud backends
        enable_aws_secrets=True,
        aws_region="us-east-1",
        enable_gcp_secrets=True,
        gcp_project_id="my-gcp-project",
        enable_azure_keyvault=True,
        azure_vault_url="https://my-vault.vault.azure.net/",
        # Self-hosted fallback
        enable_vault=True,
        vault_config={
            "url": "https://vault.company.com:8200",
            "auth_method": "kubernetes",
            "role": "multi-cloud-service"
        }
    )

    await config_manager.initialize()
    return config_manager


async def demonstrate_secret_operations(config_manager):
    """Demonstrate secret management operations."""
    logger.info("=== Secret Operations Demo ===")

    # Set some example secrets
    secrets_to_set = {
        "database/password": "super-secure-db-password",
        "redis/password": "redis-secret-123",
        "external_api/key": "sk-api-key-12345",
        "jwt/signing_key": "jwt-secret-key-abcdef"
    }

    for key, value in secrets_to_set.items():
        success = await config_manager.set_secret(key, value)
        if success:
            logger.info(f"✓ Set secret: {key}")
        else:
            logger.warning(f"✗ Failed to set secret: {key}")

    # Retrieve secrets
    for key in secrets_to_set.keys():
        value = await config_manager.get_secret(key)
        if value:
            logger.info(f"✓ Retrieved secret: {key} = {value[:10]}...")
        else:
            logger.warning(f"✗ Failed to retrieve secret: {key}")

    # Get complete configuration with resolved secrets
    try:
        config = await config_manager.get_configuration()
        logger.info("✓ Configuration loaded successfully")
        logger.info(f"Service Name: {config.service_name}")
        logger.info(f"Database Host: {config.database.host}")
        logger.info(f"API Key (masked): {config.api_key[:10]}...")

        # Demonstrate configuration validation
        if config.debug:
            logger.info("Debug mode is enabled")

    except Exception as e:
        logger.error(f"Configuration loading failed: {e}")


async def demonstrate_local_development():
    """Demonstrate local development setup."""
    logger.info("=== Local Development Demo ===")

    # Simple configuration for local development
    config_manager = create_unified_config_manager(
        service_name="local-dev-service",
        environment=Environment.DEVELOPMENT,
        config_class=ServiceConfig,
        hosting_environment=HostingEnvironment.LOCAL,  # Force local mode
        enable_file_secrets=True,
        secrets_dir="./dev-secrets",
        enable_vault=False  # Skip Vault for local dev
    )

    await config_manager.initialize()

    # Set some local development secrets
    await config_manager.set_secret("database/password", "dev-password")
    await config_manager.set_secret("jwt/signing_key", "dev-jwt-key")

    # Get configuration
    config = await config_manager.get_configuration()
    logger.info(f"Local dev configuration loaded for: {config.service_name}")

    return config_manager


async def main():
    """Run all configuration examples."""
    logger.info("Starting Unified Configuration System Examples")

    try:
        # Demonstrate different configuration approaches
        await demonstrate_auto_detection()
        await demonstrate_local_development()

        # These would require actual cloud credentials
        # await demonstrate_manual_configuration()
        # await demonstrate_multi_cloud_setup()

        logger.info("All examples completed successfully!")

    except Exception as e:
        logger.error(f"Example failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
