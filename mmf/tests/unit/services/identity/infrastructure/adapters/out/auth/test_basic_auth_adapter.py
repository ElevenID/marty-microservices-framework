from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

import pytest

from mmf.services.identity.application.ports_out import (
    AuthenticationContext,
    AuthenticationCredentials,
    AuthenticationMethod,
    CredentialValidationError,
)
from mmf.services.identity.domain.models import AuthenticatedUser
from mmf.services.identity.infrastructure.adapters.out.auth.basic_auth_adapter import (
    BasicAuthAdapter,
    BasicAuthConfig,
)


class TestBasicAuthAdapter:
    @pytest.fixture
    def config(self):
        return BasicAuthConfig(
            password_min_length=8,
            password_require_uppercase=True,
            password_require_lowercase=True,
            password_require_digits=True,
            password_require_special=False,
            bcrypt_rounds=4,  # Low rounds for faster tests
            enable_user_registration=False,
        )

    @pytest.fixture
    def adapter(self, config):
        return BasicAuthAdapter(config)

    @pytest.fixture
    def context(self):
        return AuthenticationContext(
            client_ip="127.0.0.1", user_agent="TestAgent", request_id="req-123"
        )

    def test_initialization_creates_default_users(self, adapter):
        """Test that default users are created upon initialization."""
        assert "admin" in adapter._users
        assert "user" in adapter._users
        assert adapter._users["admin"]["email"] == "admin@example.com"

    def test_supports_method(self, adapter):
        """Test supported authentication methods."""
        assert adapter.supports_method(AuthenticationMethod.BASIC)
        assert not adapter.supports_method(AuthenticationMethod.JWT)
        assert not adapter.supports_method(AuthenticationMethod.API_KEY)
        assert adapter.supported_methods == [AuthenticationMethod.BASIC]

    @pytest.mark.asyncio
    async def test_authenticate_success(self, adapter, context):
        """Test successful authentication with valid credentials."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={"username": "admin", "password": "admin123"},  # pragma: allowlist secret
        )

        result = await adapter.authenticate(credentials, context)

        assert result.success
        assert result.user is not None
        assert result.user.username == "admin"
        assert "admin" in result.user.roles
        assert result.method_used == AuthenticationMethod.BASIC
        assert result.error_code is None

    @pytest.mark.asyncio
    async def test_authenticate_failure_invalid_password(self, adapter, context):
        """Test authentication failure with incorrect password."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={
                "username": "admin",
                "password": "wrongpassword",  # pragma: allowlist secret
            },
        )

        result = await adapter.authenticate(credentials, context)

        assert not result.success
        assert result.user is None
        assert result.error_code == "INVALID_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_authenticate_failure_user_not_found(self, adapter, context):
        """Test authentication failure with non-existent user."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={
                "username": "nonexistent",
                "password": "password123",  # pragma: allowlist secret
            },
        )

        result = await adapter.authenticate(credentials, context)

        assert not result.success
        assert result.error_code == "INVALID_CREDENTIALS"  # Should be same error for security

    @pytest.mark.asyncio
    async def test_authenticate_failure_missing_credentials(self, adapter, context):
        """Test authentication failure with missing username or password."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={"username": "admin"},  # Missing password
        )

        result = await adapter.authenticate(credentials, context)

        assert not result.success
        assert result.error_code == "MISSING_CREDENTIALS"

    @pytest.mark.asyncio
    async def test_authenticate_failure_wrong_method(self, adapter, context):
        """Test authentication failure when using unsupported method."""
        credentials = AuthenticationCredentials(
            method=AuthenticationMethod.JWT, credentials={"token": "some.jwt.token"}
        )

        result = await adapter.authenticate(credentials, context)

        assert not result.success
        assert result.error_code == "METHOD_NOT_SUPPORTED"

    @pytest.mark.asyncio
    async def test_validate_credentials_format(self, adapter):
        """Test credential format validation."""
        # Valid format
        valid_creds = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={"username": "user", "password": "password123"},  # pragma: allowlist secret
        )
        assert await adapter.validate_credentials(valid_creds)

        # Invalid format (short password)
        invalid_creds = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={"username": "user", "password": "short"},  # pragma: allowlist secret
        )
        assert not await adapter.validate_credentials(invalid_creds)

        # Invalid format (empty username)
        empty_user = AuthenticationCredentials(
            method=AuthenticationMethod.BASIC,
            credentials={"username": "", "password": "password123"},  # pragma: allowlist secret
        )
        assert not await adapter.validate_credentials(empty_user)

    @pytest.mark.asyncio
    async def test_refresh_authentication(self, adapter, context):
        """Test refreshing an authenticated user session."""
        user = AuthenticatedUser(
            user_id="user_admin",
            username="admin",
            email="admin@example.com",
            roles={"admin"},
            permissions={"read"},
            auth_method="basic",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
            metadata={},
        )

        result = await adapter.refresh_authentication(user, context)

        assert result.success
        assert result.user.username == "admin"
        assert result.user.expires_at > user.expires_at
        assert result.metadata.get("refreshed") is not None

    @pytest.mark.asyncio
    async def test_refresh_authentication_user_not_found(self, adapter, context):
        """Test refreshing session for deleted/non-existent user."""
        user = AuthenticatedUser(
            user_id="user_deleted",
            username="deleted_user",
            email="deleted@example.com",
            roles=set(),
            permissions=set(),
            auth_method="basic",
            created_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc),
            metadata={},
        )

        result = await adapter.refresh_authentication(user, context)

        assert not result.success
        assert result.error_code == "USER_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_change_password_success(self, adapter, context):
        """Test successful password change."""
        username = "user"
        old_pass = "user123"
        new_pass = "NewPassword123"

        success = await adapter.change_password(username, old_pass, new_pass, context)
        assert success

        # Verify old password no longer works
        assert not await adapter.verify_password(username, old_pass)
        # Verify new password works
        assert await adapter.verify_password(username, new_pass)

    @pytest.mark.asyncio
    async def test_change_password_invalid_old_password(self, adapter, context):
        """Test password change with incorrect old password."""
        with pytest.raises(CredentialValidationError, match="Current password is incorrect"):
            await adapter.change_password("user", "wrongpass", "NewPassword123", context)

    @pytest.mark.asyncio
    async def test_change_password_policy_violation(self, adapter, context):
        """Test password change with weak new password."""
        with pytest.raises(
            CredentialValidationError, match="New password does not meet policy requirements"
        ):
            await adapter.change_password("user", "user123", "weak", context)
