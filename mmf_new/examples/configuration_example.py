#!/usr/bin/env python3
"""
Example: Configuration System Usage

This example demonstrates how to use the new MMF configuration system
for loading and using configuration in services.
"""

from pathlib import Path

from mmf_new.core.infrastructure.config import (
    MMFConfiguration,
    load_platform_configuration,
    load_service_configuration,
)


def example_basic_configuration():
    """Example of basic configuration loading."""
    print("=== Basic Configuration Loading ===")

    # Auto-detect config directory
    config_dir = Path(__file__).parent / "config"

    try:
        # Load service configuration
        config = load_service_configuration(
            service_name="identity-service",
            environment="development",
            config_dir=config_dir,
        )

        print(f"Service Name: {config.get_service_name()}")
        print(f"Service Version: {config.get_service_version()}")
        print(f"Environment: {config.get_environment_name()}")
        print(f"Debug Mode: {config.is_debug_enabled()}")

        # Access specific configuration values
        db_host = config.get("database.host", "localhost")
        db_port = config.get("database.port", 5432)
        jwt_secret = config.get("security.authentication.jwt.secret", "default")

        print(f"Database: {db_host}:{db_port}")
        print(f"JWT Secret: {'***' if jwt_secret else 'Not configured'}")

    except FileNotFoundError as e:
        print(f"Configuration file not found: {e}")
    except Exception as e:
        print(f"Error loading configuration: {e}")


def example_platform_configuration():
    """Example of platform configuration loading."""
    print("\n=== Platform Configuration Loading ===")

    config_dir = Path(__file__).parent / "config"

    try:
        # Load platform configuration
        platform_config = load_platform_configuration(
            environment="development",
            config_dir=config_dir,
        )

        # Access platform settings
        telemetry = platform_config.get("platform.telemetry.tracing.provider", "jaeger")
        messaging = platform_config.get("platform.messaging.broker_type", "redis")

        print(f"Tracing Provider: {telemetry}")
        print(f"Message Broker: {messaging}")

        # Access secrets configuration
        secret_backends = platform_config.get("platform.secrets.manager", "environment")
        print(f"Secret Manager: {secret_backends}")

    except Exception as e:
        print(f"Error loading platform configuration: {e}")


def example_environment_specific_configuration():
    """Example of loading configuration for different environments."""
    print("\n=== Environment-Specific Configuration ===")

    config_dir = Path(__file__).parent / "config"
    environments = ["development", "testing", "production"]

    for env in environments:
        try:
            config = load_service_configuration(
                service_name="api-gateway",
                environment=env,
                config_dir=config_dir,
            )

            tls_enabled = config.get("security.tls.enabled", False)
            auth_required = config.get("security.authentication.required", True)
            log_level = config.get("observability.logging.level", "INFO")

            print(f"\n{env.upper()}:")
            print(f"  TLS Enabled: {tls_enabled}")
            print(f"  Auth Required: {auth_required}")
            print(f"  Log Level: {log_level}")

        except Exception as e:
            print(f"  Error: {e}")


def example_configuration_validation():
    """Example of configuration validation and error handling."""
    print("\n=== Configuration Validation ===")

    config_dir = Path(__file__).parent / "config"

    # Test with non-existent service
    try:
        load_service_configuration(
            service_name="non-existent-service",
            environment="development",
            config_dir=config_dir,
        )
        print("Non-existent service config loaded (using defaults)")

    except Exception as e:
        print(f"Expected error for non-existent service: {e}")

    # Test with invalid config directory
    try:
        MMFConfiguration.load(
            config_dir="/invalid/path",
            environment="development",
            service_name="identity-service",
        )

    except Exception as e:
        print(f"Expected error for invalid config directory: {e}")


def example_service_configuration_sections():
    """Example of accessing different configuration sections."""
    print("\n=== Configuration Sections ===")

    config_dir = Path(__file__).parent / "config"

    try:
        config = load_service_configuration(
            service_name="identity-service",
            environment="development",
            config_dir=config_dir,
        )

        print("Database Configuration:")
        db_config = config.database
        for key, value in db_config.items():
            if "password" not in key.lower():  # Don't print sensitive values
                print(f"  {key}: {value}")

        print("\nSecurity Configuration:")
        security_config = config.security
        print(
            f"  Authentication Required: {security_config.get('authentication', {}).get('required', 'Unknown')}"
        )
        print(f"  TLS Enabled: {security_config.get('tls', {}).get('enabled', 'Unknown')}")

        print("\nObservability Configuration:")
        observability_config = config.observability
        print(f"  Log Level: {observability_config.get('logging', {}).get('level', 'Unknown')}")
        print(
            f"  Metrics Enabled: {observability_config.get('metrics', {}).get('enabled', 'Unknown')}"
        )

    except Exception as e:
        print(f"Error accessing configuration sections: {e}")


def main():
    """Run all configuration examples."""
    print("MMF Configuration System Examples")
    print("=" * 50)

    example_basic_configuration()
    example_platform_configuration()
    example_environment_specific_configuration()
    example_configuration_validation()
    example_service_configuration_sections()

    print("\n" + "=" * 50)
    print("Examples completed!")


if __name__ == "__main__":
    main()
