"""
Tests for Authentication Providers.

This module contains comprehensive tests for all authentication provider
implementations including basic auth, API keys, and provider abstractions.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from mmf_new.services.identity.application.ports_out import (
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    AuthenticationProviderError,
    AuthenticationResult,
)
from mmf_new.services.identity.domain.models import AuthenticatedUser
from mmf_new.services.identity.infrastructure.adapters import (
    APIKeyAdapter,
    APIKeyConfig,
    BasicAuthAdapter,
    BasicAuthConfig,
)


class TestBasicAuthenticationProvider:
    """Test basic authentication provider functionality."""

    @pytest.fixture
    def basic_config(self):
        """Create basic auth configuration for testing."""
        return BasicAuthConfig(
            password_hash_rounds=4,  # Faster for tests
            password_min_length=6,
            create_default_users=True,
        )

    @pytest.fixture
    def basic_provider(self, basic_config):
        """Create basic authentication provider."""
        return BasicAuthAdapter(basic_config)

    @pytest.fixture
    def valid_credentials(self):
        """Create valid basic auth credentials."""
        return AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={
                "username": "admin",
                "password": "admin123",  # pragma: allowlist secret
            },
        )

    @pytest.fixture
    def auth_context(self):
        """Create authentication context."""
        return AuthenticationContext(
            client_ip="192.168.1.100",
            user_agent="Test Client",
            timestamp=datetime.now(timezone.utc),
        )

    def test_provider_supports_basic_method(self, basic_provider):
        """Test that provider supports basic authentication method."""
        assert basic_provider.supports_method(AuthenticationMethod.BASIC)
        assert not basic_provider.supports_method(AuthenticationMethod.API_KEY)
        assert not basic_provider.supports_method(AuthenticationMethod.JWT)

    def test_supported_methods_property(self, basic_provider):
        """Test supported methods property."""
        methods = basic_provider.supported_methods
        assert AuthenticationMethod.BASIC in methods
        assert len(methods) == 1

    @pytest.mark.asyncio
    async def test_successful_authentication(self, basic_provider, valid_credentials, auth_context):
        """Test successful authentication with valid credentials."""
        result = await basic_provider.authenticate(valid_credentials, auth_context)

        assert result.success
        assert result.user is not None
        assert result.user.username == "admin"
        assert result.user.user_id == "user_admin"
        assert result.method == AuthenticationMethod.BASIC
        assert result.error_message is None

    @pytest.mark.asyncio
    async def test_failed_authentication_wrong_password(self, basic_provider, auth_context):
        """Test failed authentication with wrong password."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={
                "username": "admin",
                "password": "wrongpassword",  # pragma: allowlist secret
            },
        )

        result = await basic_provider.authenticate(credentials, auth_context)

        assert not result.success
        assert result.user is None
        assert result.error_code == "INVALID_CREDENTIALS"
        assert "Invalid username or password" in result.error_message

    @pytest.mark.asyncio
    async def test_failed_authentication_nonexistent_user(self, basic_provider, auth_context):
        """Test failed authentication with non-existent user."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={
                "username": "nonexistent",
                "password": "anypassword",  # pragma: allowlist secret
            },
        )

        result = await basic_provider.authenticate(credentials, auth_context)

        assert not result.success
        assert result.user is None
        assert result.error_code == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_authentication_with_unsupported_method(self, basic_provider, auth_context):
        """Test authentication fails with unsupported method."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY,
            credentials={"api_key": "some-key"},  # pragma: allowlist secret
        )

        result = await basic_provider.authenticate(credentials, auth_context)

        assert not result.success
        assert result.error_code == "METHOD_NOT_SUPPORTED"
        assert "not supported" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_credentials_valid_format(self, basic_provider):
        """Test credential validation with valid format."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={
                "username": "testuser",
                "password": "testpassword",  # pragma: allowlist secret
            },
        )

        is_valid = await basic_provider.validate_credentials(credentials)
        assert is_valid

    @pytest.mark.asyncio
    async def test_validate_credentials_missing_username(self, basic_provider):
        """Test credential validation with missing username."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={"password": "testpassword"},  # pragma: allowlist secret
        )

        is_valid = await basic_provider.validate_credentials(credentials)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_validate_credentials_missing_password(self, basic_provider):
        """Test credential validation with missing password."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC, credentials={"username": "testuser"}
        )

        is_valid = await basic_provider.validate_credentials(credentials)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_validate_credentials_password_too_short(self, basic_provider):
        """Test credential validation with password too short."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={
                "username": "testuser",
                "password": "123",  # Less than min length
            },
        )

        is_valid = await basic_provider.validate_credentials(credentials)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_refresh_authentication(self, basic_provider, auth_context):
        """Test authentication refresh functionality."""
        # First authenticate
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={"username": "admin", "password": "admin123"},  # pragma: allowlist secret
        )

        auth_result = await basic_provider.authenticate(credentials, auth_context)
        assert auth_result.success

        # Then refresh
        refresh_result = await basic_provider.refresh_authentication(auth_result.user, auth_context)

        assert refresh_result.success
        assert refresh_result.user.user_id == auth_result.user.user_id
        assert refresh_result.expires_at > auth_result.expires_at

    def test_password_hashing_and_verification(self, basic_provider):
        """Test password hashing and verification."""
        password = "testpassword123"  # pragma: allowlist secret

        # Hash password
        hashed = basic_provider._hash_password(password)

        # Verify password
        assert basic_provider._verify_password(password, hashed)
        assert not basic_provider._verify_password("wrongpassword", hashed)

    def test_password_policy_validation(self, basic_provider):
        """Test password policy validation."""
        config = basic_provider._config

        # Valid password
        valid_password = "StrongP@ss123"  # pragma: allowlist secret
        assert basic_provider._validate_password_policy(valid_password)

        # Too short
        short_password = "123"
        assert not basic_provider._validate_password_policy(short_password)

        # Missing special characters (if required)
        if config.password_require_special_chars:
            no_special = "StrongPass123"
            assert not basic_provider._validate_password_policy(no_special)


class TestAPIKeyAuthenticationProvider:
    """Test API key authentication provider functionality."""

    @pytest.fixture
    def api_key_config(self):
        """Create API key configuration for testing."""
        return APIKeyConfig(
            key_length=16,  # Shorter for tests
            key_prefix="test_",
            create_demo_keys=True,
        )

    @pytest.fixture
    def api_key_provider(self, api_key_config):
        """Create API key authentication provider."""
        return APIKeyAdapter(api_key_config)

    @pytest.fixture
    def auth_context(self):
        """Create authentication context."""
        return AuthenticationContext(
            client_ip="192.168.1.200",
            user_agent="API Test Client",
            timestamp=datetime.now(timezone.utc),
        )

    def test_provider_supports_api_key_method(self, api_key_provider):
        """Test that provider supports API key authentication method."""
        assert api_key_provider.supports_method(AuthenticationMethod.API_KEY)
        assert not api_key_provider.supports_method(AuthenticationMethod.BASIC)
        assert not api_key_provider.supports_method(AuthenticationMethod.JWT)

    @pytest.mark.asyncio
    async def test_successful_authentication_with_demo_key(self, api_key_provider, auth_context):
        """Test successful authentication with demo API key."""
        # Get demo admin key
        demo_key = "test_demo_c6481e22ec20abc47b9fe"  # Predictable demo key

        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY, credentials={"api_key": demo_key}
        )

        result = await api_key_provider.authenticate(credentials, auth_context)

        assert result.success
        assert result.user is not None
        assert result.user.user_id == "user_admin"
        assert result.method == AuthenticationMethod.API_KEY
        assert "key_name" in result.metadata

    @pytest.mark.asyncio
    async def test_failed_authentication_invalid_key(self, api_key_provider, auth_context):
        """Test failed authentication with invalid API key."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY,
            credentials={"api_key": "test_invalid_key"},  # pragma: allowlist secret
        )

        result = await api_key_provider.authenticate(credentials, auth_context)

        assert not result.success
        assert result.user is None
        assert result.error_code == "INVALID_CREDENTIALS"
        assert "Invalid API key" in result.error_message

    @pytest.mark.asyncio
    async def test_failed_authentication_missing_key(self, api_key_provider, auth_context):
        """Test failed authentication with missing API key."""
        credentials = AuthenticationCredentials(method=AuthenticationMethod.API_KEY, credentials={})

        result = await api_key_provider.authenticate(credentials, auth_context)

        assert not result.success
        assert result.error_code == "MISSING_CREDENTIALS"
        assert "API key is required" in result.error_message

    @pytest.mark.asyncio
    async def test_validate_credentials_valid_format(self, api_key_provider):
        """Test credential validation with valid API key format."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY,
            credentials={
                "api_key": "test_1234567890abcdef1234567890abcdef"  # pragma: allowlist secret
            },
        )

        is_valid = await api_key_provider.validate_credentials(credentials)
        assert is_valid

    @pytest.mark.asyncio
    async def test_validate_credentials_invalid_format(self, api_key_provider):
        """Test credential validation with invalid format."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY,
            credentials={"api_key": "invalid_key"},  # pragma: allowlist secret
        )

        is_valid = await api_key_provider.validate_credentials(credentials)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_validate_credentials_wrong_prefix(self, api_key_provider):
        """Test credential validation with wrong prefix."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY,
            credentials={"api_key": "wrong_1234567890abcdef"},  # pragma: allowlist secret
        )

        is_valid = await api_key_provider.validate_credentials(credentials)
        assert not is_valid

    @pytest.mark.asyncio
    async def test_create_api_key(self, api_key_provider, auth_context):
        """Test API key creation."""
        new_key = await api_key_provider.create_api_key(
            user_id="test_user",
            key_name="Test Key",
            permissions=["read", "write"],
            context=auth_context,
        )

        assert new_key.startswith("test_")
        assert len(new_key) > len("test_")

        # Test authentication with new key
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY, credentials={"api_key": new_key}
        )

        result = await api_key_provider.authenticate(credentials, auth_context)
        assert result.success

    @pytest.mark.asyncio
    async def test_revoke_api_key(self, api_key_provider, auth_context):
        """Test API key revocation."""
        # Create a key
        new_key = await api_key_provider.create_api_key(
            user_id="test_user", key_name="Test Key for Revocation", context=auth_context
        )

        # Verify it works
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY, credentials={"api_key": new_key}
        )

        result = await api_key_provider.authenticate(credentials, auth_context)
        assert result.success

        # Revoke it
        revoked = await api_key_provider.revoke_api_key(new_key, auth_context)
        assert revoked

        # Verify it no longer works
        result = await api_key_provider.authenticate(credentials, auth_context)
        assert not result.success

    @pytest.mark.asyncio
    async def test_api_key_expiration(self, api_key_provider, auth_context):
        """Test API key expiration."""
        # Create a key that expires quickly
        expired_time = datetime.now(timezone.utc) - timedelta(days=1)

        new_key = await api_key_provider.create_api_key(
            user_id="test_user",
            key_name="Expired Test Key",
            expires_at=expired_time,
            context=auth_context,
        )

        # Try to authenticate with expired key
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.API_KEY, credentials={"api_key": new_key}
        )

        result = await api_key_provider.authenticate(credentials, auth_context)
        assert not result.success

    @pytest.mark.asyncio
    async def test_max_keys_per_user_limit(self, api_key_provider, auth_context):
        """Test maximum API keys per user limit."""
        user_id = "test_user_limit"
        max_keys = api_key_provider._config.max_keys_per_user

        # Create maximum number of keys
        created_keys = []
        for i in range(max_keys):
            key = await api_key_provider.create_api_key(
                user_id=user_id, key_name=f"Test Key {i + 1}", context=auth_context
            )
            created_keys.append(key)

        # Try to create one more (should fail)
        with pytest.raises(AuthenticationProviderError) as exc_info:
            await api_key_provider.create_api_key(
                user_id=user_id, key_name="Excess Key", context=auth_context
            )

        assert "maximum API key limit" in str(exc_info.value)

    def test_api_key_generation_security(self, api_key_provider):
        """Test API key generation security properties."""
        # Generate multiple keys
        keys = []
        for _ in range(10):
            key = api_key_provider._generate_api_key()
            keys.append(key)
            assert key.startswith(api_key_provider._config.key_prefix)

        # Ensure all keys are unique
        assert len(set(keys)) == len(keys)

        # Ensure keys have appropriate length
        expected_length = len(api_key_provider._config.key_prefix) + (
            api_key_provider._config.key_length * 2
        )
        for key in keys:
            assert len(key) == expected_length


class TestAuthenticationProviderError:
    """Test authentication provider error handling."""

    def test_authentication_provider_error_creation(self):
        """Test creating authentication provider errors."""
        error = AuthenticationProviderError("Test error message")
        assert str(error) == "Test error message"

    def test_authentication_provider_error_inheritance(self):
        """Test error inheritance from Exception."""
        error = AuthenticationProviderError("Test error")
        assert isinstance(error, Exception)


@pytest.mark.asyncio
async def test_provider_with_none_context():
    """Test providers work correctly with None context."""
    basic_config = BasicAuthConfig(create_default_users=True)
    basic_provider = BasicAuthAdapter(basic_config)

    credentials = AuthenticationCredentials(
        method=AuthenticationMethod.BASIC,
        credentials={"username": "admin", "password": "admin123"},  # pragma: allowlist secret
    )

    # Should work with None context
    result = await basic_provider.authenticate(credentials, None)
    assert result.success


if __name__ == "__main__":
    pytest.main([__file__])
