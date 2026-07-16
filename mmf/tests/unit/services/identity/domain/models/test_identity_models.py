from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from mmf.services.identity.domain.models.authenticated_user import AuthenticatedUser
from mmf.services.identity.domain.models.authentication_result import (
    AuthenticationErrorCode,
    AuthenticationResult,
    AuthenticationStatus,
)


class TestAuthenticatedUser:
    def test_initialization_success(self):
        """Test successful initialization of AuthenticatedUser."""
        user_id = str(uuid4())
        user = AuthenticatedUser(
            user_id=user_id,
            username="testuser",
            email="test@example.com",
            roles={"admin", "user"},
            permissions={"read", "write"},
        )

        assert user.user_id == user_id
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert "admin" in user.roles
        assert "read" in user.permissions
        assert user.created_at.tzinfo == timezone.utc

    def test_validation_failures(self):
        """Test validation failures during initialization."""
        # Test empty user_id
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            AuthenticatedUser(user_id="  ")

        # Test invalid user_id type
        with pytest.raises(TypeError, match="User ID must be a string"):
            AuthenticatedUser(user_id=123)

        # Test invalid email format
        with pytest.raises(ValueError, match="Invalid email format"):
            AuthenticatedUser(user_id="user1", email="invalid-email")

    def test_role_checks(self):
        """Test role checking methods."""
        user = AuthenticatedUser(user_id="user1", roles={"admin", "editor"})

        assert user.has_role("admin") is True
        assert user.has_role("viewer") is False

        assert user.has_any_role({"admin", "viewer"}) is True
        assert user.has_any_role({"viewer", "guest"}) is False

        assert user.has_all_roles({"admin", "editor"}) is True
        assert user.has_all_roles({"admin", "viewer"}) is False

    def test_permission_checks(self):
        """Test permission checking methods."""
        user = AuthenticatedUser(user_id="user1", permissions={"read", "write"})

        assert user.has_permission("read") is True
        assert user.has_permission("delete") is False

        assert user.has_any_permission({"read", "delete"}) is True
        assert user.has_any_permission({"delete", "execute"}) is False

        assert user.has_all_permissions({"read", "write"}) is True
        assert user.has_all_permissions({"read", "delete"}) is False

    def test_expiration(self):
        """Test expiration logic."""
        # Not expired
        future_time = datetime.now(timezone.utc) + timedelta(hours=1)
        user = AuthenticatedUser(user_id="user1", expires_at=future_time)
        assert user.is_expired() is False

        # Expired
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        user_expired = AuthenticatedUser(user_id="user1", expires_at=past_time)
        assert user_expired.is_expired() is True

        # No expiration
        user_no_expiry = AuthenticatedUser(user_id="user1")
        assert user_no_expiry.is_expired() is False


class TestAuthenticationResult:
    def test_success_result(self):
        """Test creating a successful authentication result."""
        user = AuthenticatedUser(user_id="user1")
        result = AuthenticationResult(status=AuthenticationStatus.SUCCESS, authenticated_user=user)

        assert result.status == AuthenticationStatus.SUCCESS
        assert result.authenticated_user == user
        assert result.error_message is None
        assert result.error_code is None

    def test_success_validation_failure(self):
        """Test validation for invalid success result."""
        # Missing user
        with pytest.raises(
            ValueError, match="Successful authentication must include an authenticated user"
        ):
            AuthenticationResult(status=AuthenticationStatus.SUCCESS)

        # Including error details
        user = AuthenticatedUser(user_id="user1")
        with pytest.raises(
            ValueError, match="Successful authentication should not include error details"
        ):
            AuthenticationResult(
                status=AuthenticationStatus.SUCCESS, authenticated_user=user, error_message="Error"
            )

    def test_failure_result(self):
        """Test creating a failed authentication result."""
        result = AuthenticationResult(
            status=AuthenticationStatus.FAILED,
            error_message="Invalid password",
            error_code=AuthenticationErrorCode.INVALID_PASSWORD,
        )

        assert result.status == AuthenticationStatus.FAILED
        assert result.authenticated_user is None
        assert result.error_message == "Invalid password"
        assert result.error_code == AuthenticationErrorCode.INVALID_PASSWORD

    def test_failure_validation_failure(self):
        """Test validation for invalid failure result."""
        # Including user
        user = AuthenticatedUser(user_id="user1")
        with pytest.raises(
            ValueError, match="Failed authentication should not include user details"
        ):
            AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                authenticated_user=user,
                error_message="Error",
                error_code=AuthenticationErrorCode.INVALID_PASSWORD,
            )

        # Missing error message
        with pytest.raises(ValueError, match="Failed authentication must include an error message"):
            AuthenticationResult(
                status=AuthenticationStatus.FAILED,
                error_code=AuthenticationErrorCode.INVALID_PASSWORD,
            )

        # Missing error code
        with pytest.raises(ValueError, match="Failed authentication must include an error code"):
            AuthenticationResult(status=AuthenticationStatus.FAILED, error_message="Error")
