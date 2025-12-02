"""
Authentication Configuration Integration Example.

This demonstrates how to configure and use the multi-method authentication
system with different configuration approaches and environments.
"""

import asyncio
import os
from datetime import datetime, timezone

from mmf.infrastructure.config_manager import Environment
from mmf.services.identity.application import (
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    authentication_manager,
)
from mmf.services.identity.config import (
    AuthenticationProviderType,
    create_development_config,
    create_production_config,
    create_sample_config_file,
    create_testing_config,
    get_authentication_settings,
    load_config_from_file,
)
from mmf.services.identity.infrastructure.adapters import (
    APIKeyAdapter,
    APIKeyConfig,
    BasicAuthAdapter,
    BasicAuthConfig,
)


def demo_configuration_loading():
    """Demonstrate different configuration loading methods."""
    print("🔧 Configuration Loading Demo")
    print("-" * 40)

    # 1. Environment-based configuration
    dev_config = create_development_config()
    print(f"Development Config:")
    print(f"  Enabled providers: {[p.value for p in dev_config.enabled_providers]}")
    print(f"  Default provider: {dev_config.default_provider.value}")
    print(f"  Create demo keys: {dev_config.api_key.create_demo_keys}")
    print(f"  Rate limiting: {dev_config.security.enable_rate_limiting}")

    # 2. Production configuration with environment variables
    os.environ["ADMIN_PASSWORD"] = "super-secure-password"  # pragma: allowlist secret
    os.environ["JWT_SECRET_KEY"] = "production-jwt-secret-key-xyz"  # pragma: allowlist secret

    prod_config = create_production_config()
    print(f"\nProduction Config:")
    print(f"  Create demo keys: {prod_config.api_key.create_demo_keys}")
    print(f"  Rate limiting: {prod_config.security.enable_rate_limiting}")
    print(f"  Admin password: {'***HIDDEN***' if prod_config.basic_auth.default_admin_password != 'admin123' else 'DEFAULT'}")  # pragma: allowlist secret

    # 3. Pydantic settings from environment
    os.environ["MMF_AUTH_ENABLED_PROVIDERS"] = '["basic", "jwt"]'
    os.environ["MMF_AUTH_DEFAULT_PROVIDER"] = "basic"
    os.environ["MMF_AUTH_JWT_SECRET_KEY"] = "env-jwt-secret"  # pragma: allowlist secret

    settings = get_authentication_settings()
    print(f"\nPydantic Settings (from ENV):")
    print(f"  Enabled providers: {settings.auth_enabled_providers}")
    print(f"  Default provider: {settings.auth_default_provider}")
    print(f"  JWT secret: {'***HIDDEN***' if 'secret' in settings.auth_jwt_secret_key else settings.auth_jwt_secret_key}")

    # Cleanup environment
    for key in ["ADMIN_PASSWORD", "JWT_SECRET_KEY", "MMF_AUTH_ENABLED_PROVIDERS", "MMF_AUTH_DEFAULT_PROVIDER", "MMF_AUTH_JWT_SECRET_KEY"]:
        os.environ.pop(key, None)


async def demo_provider_configuration():
    """Demonstrate configuring authentication providers with custom settings."""
    print("\n⚙️ Provider Configuration Demo")
    print("-" * 40)

    # Create custom configuration
    config = create_development_config(
        **{
            "basic_auth.password_min_length": 10,
            "basic_auth.max_login_attempts": 3,
            "api_key.key_length": 64,
            "api_key.key_prefix": "custom_",
            "security.login_rate_limit": 10,
        }
    )

    print(f"Custom Configuration:")
    print(f"  Password min length: {config.basic_auth.password_min_length}")
    print(f"  Max login attempts: {config.basic_auth.max_login_attempts}")
    print(f"  API key length: {config.api_key.key_length}")
    print(f"  API key prefix: {config.api_key.key_prefix}")
    print(f"  Login rate limit: {config.security.login_rate_limit}")

    # Configure providers with custom settings

    basic_auth_config = BasicAuthConfig(
        password_hash_rounds=config.basic_auth.password_hash_rounds,
        password_min_length=config.basic_auth.password_min_length,
        max_login_attempts=config.basic_auth.max_login_attempts,
        password_require_special_chars=True
    )

    api_key_config = APIKeyConfig(
        key_length=config.api_key.key_length,
        key_prefix=config.api_key.key_prefix,
        default_expiry_days=config.api_key.default_expiry_days,
        max_keys_per_user=config.api_key.max_keys_per_user
    )

    # Create and register providers
    basic_provider = BasicAuthAdapter(basic_auth_config)
    api_key_provider = APIKeyAdapter(api_key_config)

    authentication_manager.register_provider(
        AuthenticationMethod.BASIC,
        basic_provider
    )
    authentication_manager.register_provider(
        AuthenticationMethod.API_KEY,
        api_key_provider
    )

    print(f"✅ Providers registered with custom configuration")

    # Test authentication with custom settings
    credentials = AuthenticationCredentials(
        method=AuthenticationMethod.BASIC,
        credentials={
            "username": "admin",
            "password": "admin123"  # Should work with default user  # pragma: allowlist secret
        }
    )

    result = await authentication_manager.authenticate(credentials)

    if result.success:
        print(f"✅ Authentication successful with custom provider")
    else:
        print(f"❌ Authentication failed: {result.error_message}")


async def demo_environment_specific_configuration():
    """Demonstrate configuration differences across environments."""
    print("\n🌍 Environment-Specific Configuration Demo")
    print("-" * 40)

    environments = {
        "Development": create_development_config(),
        "Testing": create_testing_config(),
        "Production": create_production_config()
    }

    print("Configuration Differences:")
    print("Environment        | Demo Keys | Rate Limit | Token Expiry | Audit Log")
    print("-" * 70)

    for env_name, config in environments.items():
        print(f"{env_name:<18} | {str(config.api_key.create_demo_keys):<9} | {str(config.security.enable_rate_limiting):<10} | {config.jwt.access_token_expire_minutes:<12} | {str(config.security.enable_audit_logging)}")


def demo_configuration_validation():
    """Demonstrate configuration validation and error handling."""
    print("\n✅ Configuration Validation Demo")
    print("-" * 40)

    try:
        # Test valid configuration
        valid_config = create_development_config()
        print(f"✅ Valid configuration created successfully")
        print(f"   Service: {valid_config.service_name}")
        print(f"   Environment: {valid_config.environment.value}")

        # Test configuration with custom overrides
        custom_config = create_production_config(**{
            "basic_auth.password_min_length": 12,
            "jwt.access_token_expire_minutes": 30
        })
        print(f"✅ Custom configuration applied successfully")
        print(f"   Password min length: {custom_config.basic_auth.password_min_length}")
        print(f"   Token expiry: {custom_config.jwt.access_token_expire_minutes} minutes")

    except Exception as error:
        print(f"❌ Configuration error: {error}")


def demo_configuration_file_operations():
    """Demonstrate configuration file creation and loading."""
    print("\n📄 Configuration File Demo")
    print("-" * 40)


    # Create sample configuration files
    config_files = [
        ("auth_config_dev.yaml", Environment.DEVELOPMENT),
        ("auth_config_test.yaml", Environment.TESTING),
        ("auth_config_prod.yaml", Environment.PRODUCTION)
    ]

    for file_name, environment in config_files:
        try:
            create_sample_config_file(file_name, environment)
            print(f"✅ Created {file_name} for {environment.value}")

            # Try to load it back
            loaded_config = load_config_from_file(file_name)
            print(f"   Loaded - Environment: {loaded_config.environment.value}")
            print(f"   Loaded - Providers: {[p.value for p in loaded_config.enabled_providers]}")

        except Exception as error:
            print(f"❌ Error with {file_name}: {error}")


async def demo_runtime_configuration_changes():
    """Demonstrate runtime configuration updates."""
    print("\n🔄 Runtime Configuration Demo")
    print("-" * 40)

    # Start with development config
    config = create_development_config()

    # Set up authentication manager with initial config

    initial_config = BasicAuthConfig(
        password_hash_rounds=config.basic_auth.password_hash_rounds,
        password_min_length=config.basic_auth.password_min_length
    )

    basic_provider = BasicAuthAdapter(initial_config)
    authentication_manager.register_provider(
        AuthenticationMethod.BASIC,
        basic_provider
    )

    print(f"Initial configuration:")
    print(f"  Password min length: {config.basic_auth.password_min_length}")
    print(f"  Hash rounds: {config.basic_auth.password_hash_rounds}")

    # Test with short password (should fail)
    short_password_creds = AuthenticationCredentials(
        method=AuthenticationMethod.BASIC,
        credentials={
            "username": "test",
            "password": "123"  # Too short
        }
    )

    result = await authentication_manager.validate_credentials(short_password_creds)
    print(f"Short password validation: {'✅ Valid' if result else '❌ Invalid (expected)'}")

    # Simulate configuration update
    updated_config = create_development_config(**{
        "basic_auth.password_min_length": 12,  # More strict
        "basic_auth.password_hash_rounds": 14   # More secure
    })

    print(f"\nUpdated configuration:")
    print(f"  Password min length: {updated_config.basic_auth.password_min_length}")
    print(f"  Hash rounds: {updated_config.basic_auth.password_hash_rounds}")

    # In a real application, you would reload the provider with new config
    print(f"📝 Note: In production, implement configuration hot-reloading")


async def main():
    """Run all configuration demos."""
    print("🚀 Authentication Configuration System Demo")
    print("=" * 50)

    demo_configuration_loading()
    await demo_provider_configuration()
    await demo_environment_specific_configuration()
    demo_configuration_validation()
    demo_configuration_file_operations()
    await demo_runtime_configuration_changes()

    print("\n🎉 Configuration demos completed!")


if __name__ == "__main__":
    asyncio.run(main())
