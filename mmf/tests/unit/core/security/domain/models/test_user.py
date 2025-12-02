from datetime import datetime, timedelta, timezone

import pytest

from mmf.core.security.domain.models.user import (
    AuthenticatedUser,
    SecurityPrincipal,
    User,
)


class TestAuthenticatedUser:
    def test_authenticated_user_creation(self):
        """Test creating an AuthenticatedUser."""
        user = AuthenticatedUser(
            user_id="user-123",
            username="testuser",
            email="test@example.com",
            roles={"admin", "user"},
            permissions={"read", "write"},
            session_id="sess-123",
            auth_method="password",
            metadata={"key": "value"},
        )

        assert user.user_id == "user-123"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.roles == {"admin", "user"}
        assert user.permissions == {"read", "write"}
        assert user.session_id == "sess-123"
        assert user.auth_method == "password"
        assert user.metadata == {"key": "value"}
        assert isinstance(user.created_at, datetime)
        assert user.created_at.tzinfo == timezone.utc

    def test_authenticated_user_validation(self):
        """Test AuthenticatedUser validation logic."""
        # Test invalid user_id type
        with pytest.raises(TypeError, match="User ID must be a string"):
            AuthenticatedUser(user_id=123)

        # Test empty user_id
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            AuthenticatedUser(user_id="  ")

        # Test invalid username type
        with pytest.raises(TypeError, match="Username must be a string"):
            AuthenticatedUser(user_id="user-123", username=123)

        # Test empty username
        with pytest.raises(ValueError, match="Username cannot be empty"):
            AuthenticatedUser(user_id="user-123", username="  ")

        # Test invalid email format
        with pytest.raises(ValueError, match="Invalid email format"):
            AuthenticatedUser(user_id="user-123", email="invalid-email")

    def test_list_conversion_to_set(self):
        """Test that lists are converted to sets for roles and permissions."""
        user = AuthenticatedUser(
            user_id="user-123",
            roles=["admin", "user", "admin"],
            permissions=["read", "write", "read"],
        )

        assert isinstance(user.roles, set)
        assert user.roles == {"admin", "user"}
        assert isinstance(user.permissions, set)
        assert user.permissions == {"read", "write"}

    def test_timezone_enforcement(self):
        """Test that naive datetimes are converted to UTC."""
        naive_expiry = datetime(2025, 1, 1, 12, 0, 0)
        user = AuthenticatedUser(user_id="user-123", expires_at=naive_expiry)

        assert user.expires_at.tzinfo == timezone.utc

        # Check created_at if passed manually as naive
        naive_created = datetime(2024, 1, 1, 12, 0, 0)
        user2 = AuthenticatedUser(user_id="user-123", created_at=naive_created)
        assert user2.created_at.tzinfo == timezone.utc

    def test_role_checks(self):
        """Test role checking methods."""
        user = AuthenticatedUser(user_id="user-123", roles={"admin", "editor"})

        assert user.has_role("admin") is True
        assert user.has_role("viewer") is False

        assert user.has_any_role({"admin", "viewer"}) is True
        assert user.has_any_role({"viewer", "guest"}) is False

        assert user.has_all_roles({"admin", "editor"}) is True
        assert user.has_all_roles({"admin", "viewer"}) is False

    def test_permission_checks(self):
        """Test permission checking methods."""
        user = AuthenticatedUser(user_id="user-123", permissions={"read", "write"})

        assert user.has_permission("read") is True
        assert user.has_permission("delete") is False

        assert user.has_any_permission({"read", "delete"}) is True
        assert user.has_any_permission({"delete", "execute"}) is False

        assert user.has_all_permissions({"read", "write"}) is True
        assert user.has_all_permissions({"read", "delete"}) is False

    def test_expiry_checks(self):
        """Test expiry checking methods."""
        # Not expired
        future_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        user = AuthenticatedUser(user_id="user-123", expires_at=future_expiry)
        assert user.is_expired() is False
        assert user.time_until_expiry() > 0

        # Expired
        past_expiry = datetime.now(timezone.utc) - timedelta(hours=1)
        user_expired = AuthenticatedUser(user_id="user-123", expires_at=past_expiry)
        assert user_expired.is_expired() is True
        assert user_expired.time_until_expiry() == 0.0

        # No expiry
        user_no_expiry = AuthenticatedUser(user_id="user-123")
        assert user_no_expiry.is_expired() is False
        assert user_no_expiry.time_until_expiry() is None

    def test_immutable_modifications(self):
        """Test methods that return new instances with modifications."""
        user = AuthenticatedUser(user_id="user-123", roles={"user"}, permissions={"read"})

        # with_session
        user_sess = user.with_session("new-sess")
        assert user_sess.session_id == "new-sess"
        assert user_sess.user_id == user.user_id
        assert user_sess is not user

        # with_expiry
        new_expiry = datetime.now(timezone.utc) + timedelta(days=1)
        user_exp = user.with_expiry(new_expiry)
        assert user_exp.expires_at == new_expiry
        assert user_exp is not user

        # add_role
        user_role = user.add_role("admin")
        assert user_role.roles == {"user", "admin"}
        assert user.roles == {"user"}  # Original unchanged

        # add_permission
        user_perm = user.add_permission("write")
        assert user_perm.permissions == {"read", "write"}
        assert user.permissions == {"read"}  # Original unchanged

    def test_serialization(self):
        """Test to_dict and from_dict methods."""
        expiry = datetime.now(timezone.utc).replace(microsecond=0)
        user = AuthenticatedUser(
            user_id="user-123",
            username="testuser",
            email="test@example.com",
            roles={"admin"},
            permissions={"read"},
            session_id="sess-123",
            auth_method="password",
            expires_at=expiry,
            metadata={"key": "value"},
        )

        data = user.to_dict()
        assert data["user_id"] == "user-123"
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert "admin" in data["roles"]
        assert "read" in data["permissions"]
        assert data["session_id"] == "sess-123"
        assert data["auth_method"] == "password"
        assert data["expires_at"] == expiry.isoformat()
        assert data["metadata"] == {"key": "value"}

        user_restored = AuthenticatedUser.from_dict(data)
        assert user_restored.user_id == user.user_id
        assert user_restored.username == user.username
        assert user_restored.email == user.email
        assert user_restored.roles == user.roles
        assert user_restored.permissions == user.permissions
        assert user_restored.session_id == user.session_id
        assert user_restored.auth_method == user.auth_method
        assert user_restored.expires_at == user.expires_at
        assert user_restored.metadata == user.metadata


class TestSecurityPrincipal:
    def test_security_principal_creation(self):
        """Test creating a SecurityPrincipal."""
        principal = SecurityPrincipal(
            id="svc-123",
            type="service",
            roles={"service-role"},
            attributes={"region": "us-east"},
            permissions={"api-access"},
            identity_provider="internal-idp",
            session_id="sess-svc",
        )

        assert principal.id == "svc-123"
        assert principal.type == "service"
        assert principal.roles == {"service-role"}
        assert principal.attributes == {"region": "us-east"}
        assert principal.permissions == {"api-access"}
        assert principal.identity_provider == "internal-idp"
        assert principal.session_id == "sess-svc"
        assert isinstance(principal.created_at, datetime)


class TestUserAlias:
    def test_user_alias(self):
        """Test that User is an alias for AuthenticatedUser."""
        assert User is AuthenticatedUser
