"""
Multi-Method Authentication Integration Examples.

This module demonstrates how to set up and use the new multi-method
authentication system with different providers.
"""

import asyncio
from datetime import datetime, timezone

from mmf_new.services.identity.application import (
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    authentication_manager,
)
from mmf_new.services.identity.infrastructure.adapters import (
    APIKeyAdapter,
    APIKeyConfig,
    BasicAuthAdapter,
    BasicAuthConfig,
)


async def setup_authentication_system():
    """Set up the authentication system with multiple providers."""
    print("🔧 Setting up multi-method authentication system...")

    # Configure and register Basic Authentication provider
    basic_config = BasicAuthConfig(
        password_hash_rounds=12,
        password_min_length=8,
        password_require_special_chars=True
    )
    basic_provider = BasicAuthAdapter(basic_config)
    authentication_manager.register_provider(
        AuthenticationMethod.BASIC,
        basic_provider
    )

    # Configure and register API Key Authentication provider
    api_key_config = APIKeyConfig(
        key_length=32,
        key_prefix="mmf_",
        default_expiry_days=365,
        max_keys_per_user=10
    )
    api_key_provider = APIKeyAdapter(api_key_config)
    authentication_manager.register_provider(
        AuthenticationMethod.API_KEY,
        api_key_provider
    )

    print(f"✅ Registered authentication methods: {[m.value for m in authentication_manager.get_supported_methods()]}")
    return basic_provider, api_key_provider


async def demo_basic_authentication():
    """Demonstrate basic username/password authentication."""
    print("\n🔑 Basic Authentication Demo")
    print("-" * 40)

    # Create authentication context
    context = AuthenticationContext(
        client_ip="192.168.1.100",
        user_agent="Demo Application v1.0",
        timestamp=datetime.now(timezone.utc)
    )

    # Test with demo admin user
    credentials = AuthenticationCredentials(
        method=AuthenticationMethod.BASIC,
        credentials={
            "username": "admin",
            "password": "admin123"  # pragma: allowlist secret
        }
    )

    result = await authentication_manager.authenticate(credentials, context)

    if result.success:
        print(f"✅ Basic authentication successful!")
        print(f"   User ID: {result.user.user_id}")
        print(f"   Username: {result.user.username}")
        print(f"   Roles: {result.user.roles}")
        print(f"   Expires: {result.expires_at}")
    else:
        print(f"❌ Basic authentication failed: {result.error_message}")

    return result


async def demo_api_key_authentication():
    """Demonstrate API key authentication."""
    print("\n🗝️  API Key Authentication Demo")
    print("-" * 40)

    # Create authentication context
    context = AuthenticationContext(
        client_ip="192.168.1.100",
        user_agent="API Client v2.0",
        timestamp=datetime.now(timezone.utc)
    )

    # Test with demo admin API key
    credentials = AuthenticationCredentials(
        method=AuthenticationMethod.API_KEY,
        credentials={
            "api_key": "mmf_demo_c6481e22ec20abc47b9fe"  # pragma: allowlist secret
        }
    )

    result = await authentication_manager.authenticate(credentials, context)

    if result.success:
        print(f"✅ API key authentication successful!")
        print(f"   User ID: {result.user.user_id}")
        print(f"   Key Name: {result.metadata.get('key_name', 'unknown')}")
        print(f"   Roles: {result.user.roles}")
        print(f"   Expires: {result.expires_at}")
    else:
        print(f"❌ API key authentication failed: {result.error_message}")

    return result


async def demo_api_key_management():
    """Demonstrate API key creation and management."""
    print("\n🔧 API Key Management Demo")
    print("-" * 40)

    # Get the API key provider
    api_key_provider = authentication_manager.get_provider(AuthenticationMethod.API_KEY)

    if api_key_provider and hasattr(api_key_provider, 'create_api_key'):
        try:
            # Create a new API key
            new_key = await api_key_provider.create_api_key(
                user_id="user_demo",
                key_name="Demo Integration Key",
                permissions=["read", "write"]
            )

            print(f"✅ Created new API key: {new_key[:16]}...")

            # Test the new key
            test_credentials = AuthenticationCredentials(
                method=AuthenticationMethod.API_KEY,
                credentials={"api_key": new_key}
            )

            test_result = await authentication_manager.authenticate(test_credentials)

            if test_result.success:
                print(f"✅ New API key works correctly!")

                # Revoke the key
                revoked = await api_key_provider.revoke_api_key(new_key)
                if revoked:
                    print(f"✅ API key revoked successfully")

                    # Test revoked key
                    revoke_test = await authentication_manager.authenticate(test_credentials)
                    if not revoke_test.success:
                        print(f"✅ Revoked key correctly rejected")

        except Exception as error:
            print(f"❌ API key management error: {error}")


async def demo_credential_validation():
    """Demonstrate credential validation without full authentication."""
    print("\n✅ Credential Validation Demo")
    print("-" * 40)

    # Test valid basic auth credentials format
    basic_creds = AuthenticationCredentials(
        method=AuthenticationMethod.BASIC,
        credentials={
            "username": "test",
            "password": "validpassword"  # pragma: allowlist secret
        }
    )

    basic_valid = await authentication_manager.validate_credentials(basic_creds)
    print(f"Basic auth format validation: {'✅ Valid' if basic_valid else '❌ Invalid'}")

    # Test valid API key format
    api_creds = AuthenticationCredentials(
        method=AuthenticationMethod.API_KEY,
        credentials={
            "api_key": "mmf_1234567890abcdef1234567890abcdef"  # pragma: allowlist secret
        }
    )

    api_valid = await authentication_manager.validate_credentials(api_creds)
    print(f"API key format validation: {'✅ Valid' if api_valid else '❌ Invalid'}")

    # Test invalid API key format
    invalid_creds = AuthenticationCredentials(
        method=AuthenticationMethod.API_KEY,
        credentials={
            "api_key": "invalid_key_format"  # pragma: allowlist secret
        }
    )

    invalid_valid = await authentication_manager.validate_credentials(invalid_creds)
    print(f"Invalid key format validation: {'✅ Valid' if invalid_valid else '❌ Invalid (correct)'}")


async def demo_authentication_refresh():
    """Demonstrate authentication refresh functionality."""
    print("\n🔄 Authentication Refresh Demo")
    print("-" * 40)

    # First authenticate with API key
    credentials = AuthenticationCredentials(
        method=AuthenticationMethod.API_KEY,
        credentials={
            "api_key": "mmf_demo_c6481e22ec20abc47b9fe"  # pragma: allowlist secret
        }
    )

    result = await authentication_manager.authenticate(credentials)

    if result.success:
        print(f"✅ Initial authentication successful")
        print(f"   Expires at: {result.expires_at}")

        # Refresh the authentication
        refresh_result = await authentication_manager.refresh_authentication(result.user)

        if refresh_result.success:
            print(f"✅ Authentication refreshed successfully")
            print(f"   New expires at: {refresh_result.expires_at}")
            print(f"   Refreshed: {refresh_result.metadata.get('refreshed', False)}")
        else:
            print(f"❌ Authentication refresh failed: {refresh_result.error_message}")
    else:
        print(f"❌ Initial authentication failed: {result.error_message}")


async def demo_multi_method_fallback():
    """Demonstrate multi-method authentication with fallback."""
    print("\n🔀 Multi-Method Fallback Demo")
    print("-" * 40)

    # Create multiple credential sets (first one invalid, second one valid)
    credentials_list = [
        # Invalid API key (should fail)
        AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY,
            credentials={"api_key": "mmf_invalid_key"}  # pragma: allowlist secret
        ),
        # Valid basic auth (should succeed)
        AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={
                "username": "admin",
                "password": "admin123"  # pragma: allowlist secret
            }
        )
    ]

    result = await authentication_manager.try_multiple_methods(credentials_list)

    if result.success:
        print(f"✅ Multi-method authentication successful with: {result.method.value}")
        print(f"   User ID: {result.user.user_id}")
    else:
        print(f"❌ All authentication methods failed: {result.error_message}")


async def demo_provider_information():
    """Display information about registered providers."""
    print("\n📋 Provider Information")
    print("-" * 40)

    provider_info = authentication_manager.get_provider_info()

    for method, info in provider_info.items():
        print(f"Method: {method}")
        print(f"  Provider: {info['provider_class']}")
        print(f"  Supported methods: {info['supported_methods']}")
        print(f"  Is default: {info['is_default']}")
        print()


async def main():
    """Run all authentication demos."""
    print("🚀 Multi-Method Authentication System Demo")
    print("=" * 50)

    # Set up the authentication system
    await setup_authentication_system()

    # Run all demos
    await demo_basic_authentication()
    await demo_api_key_authentication()
    await demo_api_key_management()
    await demo_credential_validation()
    await demo_authentication_refresh()
    await demo_multi_method_fallback()
    await demo_provider_information()

    print("\n🎉 All demos completed!")


if __name__ == "__main__":
    asyncio.run(main())
