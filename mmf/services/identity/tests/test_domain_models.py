"""Unit tests for identity domain models."""

from datetime import datetime, timedelta

import pytest

from mmf.services.identity.domain.models import (
    AuthenticationResult,
    AuthenticationStatus,
    Credentials,
    Principal,
    UserId,
)


class TestUserId:
    """Tests for UserId value object."""

    def test_valid_user_id(self):
        """Test creating a valid UserId."""
        user_id = UserId("user123")
        assert user_id.value == "user123"

    def test_empty_user_id_raises_error(self):
        """Test that empty UserId raises ValueError."""
        with pytest.raises(ValueError, match="UserId cannot be empty"):
            UserId("")

    def test_whitespace_user_id_raises_error(self):
        """Test that whitespace-only UserId raises ValueError."""
        with pytest.raises(ValueError, match="UserId cannot be empty"):
            UserId("   ")


class TestCredentials:
    """Tests for Credentials value object."""

    def test_valid_credentials(self):
        """Test creating valid credentials."""
        creds = Credentials("testuser", "password123")
        assert creds.username == "testuser"
        assert creds.password == "password123"

    def test_empty_username_raises_error(self):
        """Test that empty username raises ValueError."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            Credentials("", "password")

    def test_empty_password_raises_error(self):
        """Test that empty password raises ValueError."""
        with pytest.raises(ValueError, match="Password cannot be empty"):
            Credentials("user", "")


class TestPrincipal:
    """Tests for Principal entity."""

    def test_principal_not_expired(self):
        """Test principal that has not expired."""
        user_id = UserId("user123")
        now = datetime.utcnow()
        future = now + timedelta(hours=1)

        principal = Principal(
            user_id=user_id,
            username="testuser",
            authenticated_at=now,
            expires_at=future,
        )

        assert not principal.is_expired(now)

    def test_principal_expired(self):
        """Test principal that has expired."""
        user_id = UserId("user123")
        now = datetime.utcnow()
        past = now - timedelta(hours=1)

        principal = Principal(
            user_id=user_id, username="testuser", authenticated_at=past, expires_at=past
        )

        assert principal.is_expired(now)

    def test_principal_no_expiry(self):
        """Test principal with no expiry time."""
        user_id = UserId("user123")
        now = datetime.utcnow()

        principal = Principal(user_id=user_id, username="testuser", authenticated_at=now)

        assert not principal.is_expired(now)


class TestAuthenticationResult:
    """Tests for AuthenticationResult."""

    def test_successful_result_requires_principal(self):
        """Test that successful result must include principal."""
        with pytest.raises(ValueError, match="Successful authentication must include a principal"):
            AuthenticationResult(status=AuthenticationStatus.SUCCESS)

    def test_failed_result_requires_error_message(self):
        """Test that failed result must include error message."""
        with pytest.raises(ValueError, match="Failed authentication must include an error message"):
            AuthenticationResult(status=AuthenticationStatus.FAILED)

    def test_valid_successful_result(self):
        """Test valid successful authentication result."""
        user_id = UserId("user123")
        principal = Principal(
            user_id=user_id, username="testuser", authenticated_at=datetime.utcnow()
        )

        result = AuthenticationResult(status=AuthenticationStatus.SUCCESS, principal=principal)

        assert result.status == AuthenticationStatus.SUCCESS
        assert result.principal == principal
        assert result.error_message is None

    def test_valid_failed_result(self):
        """Test valid failed authentication result."""
        result = AuthenticationResult(
            status=AuthenticationStatus.FAILED, error_message="Invalid credentials"
        )

        assert result.status == AuthenticationStatus.FAILED
        assert result.principal is None
        assert result.error_message == "Invalid credentials"
