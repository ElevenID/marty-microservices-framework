from datetime import datetime, timedelta, timezone

import pytest

from mmf.core.security.domain.models.user import AuthenticatedUser


class TestAuthenticatedUser:
    def test_initialization_defaults(self):
        user = AuthenticatedUser(user_id="user-123")

        assert user.user_id == "user-123"
        assert user.username is None
        assert user.email is None
        assert user.roles == set()
        assert user.permissions == set()
        assert user.session_id is None
        assert user.auth_method is None
        assert user.expires_at is None
        assert user.metadata == {}
        assert isinstance(user.created_at, datetime)

    def test_validation_user_id(self):
        with pytest.raises(TypeError, match="User ID must be a string"):
            AuthenticatedUser(user_id=123)

        with pytest.raises(ValueError, match="User ID cannot be empty"):
            AuthenticatedUser(user_id="  ")

    def test_validation_username(self):
        with pytest.raises(TypeError, match="Username must be a string"):
            AuthenticatedUser(user_id="user-123", username=123)

        with pytest.raises(ValueError, match="Username cannot be empty"):
            AuthenticatedUser(user_id="user-123", username="  ")

    def test_validation_email(self):
        with pytest.raises(ValueError, match="Invalid email format"):
            AuthenticatedUser(user_id="user-123", email="invalid-email")

        user = AuthenticatedUser(user_id="user-123", email="test@example.com")
        assert user.email == "test@example.com"

    def test_roles_permissions_conversion(self):
        user = AuthenticatedUser(
            user_id="user-123", roles=["admin", "user"], permissions=["read", "write"]
        )

        assert isinstance(user.roles, set)
        assert user.roles == {"admin", "user"}
        assert isinstance(user.permissions, set)
        assert user.permissions == {"read", "write"}

    def test_role_checks(self):
        user = AuthenticatedUser(user_id="user-123", roles={"admin", "editor"})

        assert user.has_role("admin") is True
        assert user.has_role("viewer") is False

        assert user.has_any_role({"admin", "viewer"}) is True
        assert user.has_any_role({"viewer", "guest"}) is False

        assert user.has_all_roles({"admin", "editor"}) is True
        assert user.has_all_roles({"admin", "viewer"}) is False

    def test_permission_checks(self):
        user = AuthenticatedUser(user_id="user-123", permissions={"read", "write"})

        assert user.has_permission("read") is True
        assert user.has_permission("delete") is False

        assert user.has_any_permission({"read", "delete"}) is True
        assert user.has_any_permission({"delete", "execute"}) is False

        assert user.has_all_permissions({"read", "write"}) is True
        assert user.has_all_permissions({"read", "delete"}) is False

    def test_expiry_checks(self):
        now = datetime.now(timezone.utc)
        future = now + timedelta(hours=1)
        past = now - timedelta(hours=1)

        user_no_expiry = AuthenticatedUser(user_id="user-1")
        assert user_no_expiry.is_expired() is False

        user_future = AuthenticatedUser(user_id="user-2", expires_at=future)
        assert user_future.is_expired() is False

        user_past = AuthenticatedUser(user_id="user-3", expires_at=past)
        assert user_past.is_expired() is True

    def test_immutability(self):
        user = AuthenticatedUser(user_id="user-123")
        with pytest.raises(AttributeError):
            user.user_id = "new-id"

    def test_with_methods(self):
        user = AuthenticatedUser(user_id="user-123")

        # with_session
        user_session = user.with_session("sess-1")
        assert user_session.session_id == "sess-1"
        assert user_session.user_id == user.user_id
        assert user_session is not user

        # with_expiry
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        user_expiry = user.with_expiry(future)
        assert user_expiry.expires_at == future
        assert user_expiry is not user

        # add_role
        user_role = user.add_role("admin")
        assert "admin" in user_role.roles
        assert user_role is not user

        # add_permission
        user_perm = user.add_permission("read")
        assert "read" in user_perm.permissions
        assert user_perm is not user

    def test_serialization(self):
        now = datetime.now(timezone.utc)
        user = AuthenticatedUser(
            user_id="user-123", username="testuser", roles={"admin"}, expires_at=now
        )

        data = user.to_dict()
        assert data["user_id"] == "user-123"
        assert data["username"] == "testuser"
        assert "admin" in data["roles"]
        assert data["expires_at"] == now.isoformat()

        restored = AuthenticatedUser.from_dict(data)
        assert restored.user_id == user.user_id
        assert restored.username == user.username
        assert restored.roles == user.roles
        assert restored.expires_at == user.expires_at


from mmf.core.security.domain.models.user import SecurityPrincipal


class TestSecurityPrincipal:
    def test_defaults(self):
        principal = SecurityPrincipal(id="p-1", type="service")

        assert principal.id == "p-1"
        assert principal.type == "service"
        assert principal.roles == set()
        assert principal.attributes == {}
        assert principal.permissions == set()
        assert isinstance(principal.created_at, datetime)
        assert principal.identity_provider is None
        assert principal.session_id is None
        assert principal.expires_at is None
