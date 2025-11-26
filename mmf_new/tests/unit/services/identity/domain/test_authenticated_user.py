"""
Unit tests for the AuthenticatedUser domain model.

Tests the validation, immutability, and behavior of the AuthenticatedUser
value object following domain-driven design principles.
"""

from datetime import datetime, timezone

import pytest

from mmf_new.services.identity.domain.models import AuthenticatedUser


class TestAuthenticatedUser:
    """Test suite for AuthenticatedUser domain model."""

    def test_create_minimal_user(self):
        """Test creating a user with minimal required fields."""
        user = AuthenticatedUser(user_id="test-123", username="testuser", auth_method="password")

        assert user.user_id == "test-123"
        assert user.username == "testuser"
        assert user.auth_method == "password"
        assert user.email is None
        assert user.roles == set()
        assert user.permissions == set()

    def test_create_complete_user(self):
        """Test creating a user with all fields populated."""
        user = AuthenticatedUser(
            user_id="user-456",
            username="admin",
            email="admin@example.com",
            roles={"admin", "user"},
            permissions={"read", "write", "delete"},
            session_id="session-789",
            auth_method="jwt",
            metadata={"department": "IT", "level": "senior"},
        )

        assert user.user_id == "user-456"
        assert user.username == "admin"
        assert user.email == "admin@example.com"
        assert user.roles == {"admin", "user"}
        assert user.permissions == {"read", "write", "delete"}
        assert user.session_id == "session-789"
        assert user.auth_method == "jwt"
        assert user.metadata == {"department": "IT", "level": "senior"}

    def test_user_id_validation(self):
        """Test user_id validation."""
        # Empty user_id should raise ValueError
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            AuthenticatedUser(user_id="", username="testuser", auth_method="password")

        # Non-string user_id should raise TypeError
        with pytest.raises(TypeError, match="User ID must be a string"):
            AuthenticatedUser(user_id=123, username="testuser", auth_method="password")

    def test_username_validation(self):
        """Test username validation."""
        # Empty username should raise ValueError
        with pytest.raises(ValueError, match="Username cannot be empty"):
            AuthenticatedUser(user_id="test-123", username="", auth_method="password")

        # Non-string username should raise TypeError
        with pytest.raises(TypeError, match="Username must be a string"):
            AuthenticatedUser(user_id="test-123", username=123, auth_method="password")

    def test_email_validation(self):
        """Test email validation."""
        # Valid email should work
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            email="test@example.com",
            auth_method="password",
        )
        assert user.email == "test@example.com"

        # Invalid email should raise ValueError
        with pytest.raises(ValueError, match="Invalid email format"):
            AuthenticatedUser(
                user_id="test-123",
                username="testuser",
                email="invalid-email",
                auth_method="password",
            )

    def test_roles_normalization(self):
        """Test that roles are normalized to a set."""
        # List input should be converted to set
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            roles=["admin", "user", "admin"],  # Duplicate should be removed
            auth_method="password",
        )
        assert user.roles == {"admin", "user"}

        # Set input should remain unchanged
        user = AuthenticatedUser(
            user_id="test-123", username="testuser", roles={"admin", "user"}, auth_method="password"
        )
        assert user.roles == {"admin", "user"}

    def test_permissions_normalization(self):
        """Test that permissions are normalized to a set."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            permissions=["read", "write", "read"],  # Duplicate should be removed
            auth_method="password",
        )
        assert user.permissions == {"read", "write"}

    def test_created_at_timezone_handling(self):
        """Test that created_at is timezone-aware."""
        # Without timezone
        naive_time = datetime(2023, 1, 1, 12, 0, 0)
        user = AuthenticatedUser(
            user_id="test-123", username="testuser", auth_method="password", created_at=naive_time
        )
        assert user.created_at.tzinfo == timezone.utc

        # With timezone
        aware_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        user = AuthenticatedUser(
            user_id="test-123", username="testuser", auth_method="password", created_at=aware_time
        )
        assert user.created_at.tzinfo == timezone.utc

    def test_expires_at_timezone_handling(self):
        """Test that expires_at is timezone-aware when provided."""
        naive_time = datetime(2023, 1, 1, 12, 0, 0)
        user = AuthenticatedUser(
            user_id="test-123", username="testuser", auth_method="password", expires_at=naive_time
        )
        assert user.expires_at.tzinfo == timezone.utc

    def test_has_role(self):
        """Test the has_role method."""
        user = AuthenticatedUser(
            user_id="test-123", username="testuser", roles={"admin", "user"}, auth_method="password"
        )

        assert user.has_role("admin") is True
        assert user.has_role("user") is True
        assert user.has_role("guest") is False

    def test_has_permission(self):
        """Test the has_permission method."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            permissions={"read", "write"},
            auth_method="password",
        )

        assert user.has_permission("read") is True
        assert user.has_permission("write") is True
        assert user.has_permission("delete") is False

    def test_is_expired(self):
        """Test the is_expired method."""
        # Future expiration
        future_time = datetime.now(timezone.utc).replace(year=2030)
        user = AuthenticatedUser(
            user_id="test-123", username="testuser", auth_method="password", expires_at=future_time
        )
        assert user.is_expired() is False

        # Past expiration
        past_time = datetime.now(timezone.utc).replace(year=2020)
        user = AuthenticatedUser(
            user_id="test-123", username="testuser", auth_method="password", expires_at=past_time
        )
        assert user.is_expired() is True

        # No expiration
        user = AuthenticatedUser(user_id="test-123", username="testuser", auth_method="password")
        assert user.is_expired() is False

    def test_to_dict(self):
        """Test the to_dict method."""
        user = AuthenticatedUser(
            user_id="test-123",
            username="testuser",
            email="test@example.com",
            roles={"admin"},
            permissions={"read"},
            auth_method="password",
            metadata={"key": "value"},
        )

        result = user.to_dict()

        assert result["user_id"] == "test-123"
        assert result["username"] == "testuser"
        assert result["email"] == "test@example.com"
        assert result["roles"] == ["admin"]
        assert result["permissions"] == ["read"]
        assert result["auth_method"] == "password"
        assert result["metadata"] == {"key": "value"}

    def test_immutability(self):
        """Test that the user object is immutable."""
        user = AuthenticatedUser(user_id="test-123", username="testuser", auth_method="password")

        # Should not be able to modify attributes
        with pytest.raises(AttributeError):
            user.username = "newuser"

        with pytest.raises(AttributeError):
            user.user_id = "new-id"

    def test_equality(self):
        """Test equality comparison between users."""
        # Create a fixed timestamp for testing
        fixed_time = datetime(2023, 1, 1, 12, 0, 0, tzinfo=timezone.utc)

        user1 = AuthenticatedUser(
            user_id="test-123", username="testuser", auth_method="password", created_at=fixed_time
        )

        user2 = AuthenticatedUser(
            user_id="test-123", username="testuser", auth_method="password", created_at=fixed_time
        )

        user3 = AuthenticatedUser(
            user_id="test-456", username="testuser", auth_method="password", created_at=fixed_time
        )

        assert user1 == user2
        assert user1 != user3

    def test_repr(self):
        """Test string representation."""
        user = AuthenticatedUser(user_id="test-123", username="testuser", auth_method="password")

        repr_str = repr(user)
        assert "test-123" in repr_str
        assert "testuser" in repr_str
