"""
Unit tests for security domain models.

Tests AuthenticatedUser, SecurityPrincipal, enums, and related models.
"""

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from mmf.core.security.domain.enums import (
    AuthenticationMethod,
    ComplianceFramework,
    IdentityProviderType,
    PermissionAction,
    PolicyEngineType,
    SecurityPolicyType,
    UserType,
)
from mmf.core.security.domain.models.user import AuthenticatedUser, SecurityPrincipal


class TestAuthenticationMethod:
    """Tests for AuthenticationMethod enum."""

    def test_method_values(self):
        """Test authentication method string values."""
        assert AuthenticationMethod.PASSWORD.value == "password"
        assert AuthenticationMethod.TOKEN.value == "token"
        assert AuthenticationMethod.CERTIFICATE.value == "certificate"
        assert AuthenticationMethod.OAUTH2.value == "oauth2"
        assert AuthenticationMethod.OIDC.value == "oidc"
        assert AuthenticationMethod.SAML.value == "saml"

    def test_all_methods_exist(self):
        """Test all expected methods are defined."""
        methods = list(AuthenticationMethod)
        assert len(methods) == 6


class TestPermissionAction:
    """Tests for PermissionAction enum."""

    def test_action_values(self):
        """Test permission action string values."""
        assert PermissionAction.READ.value == "read"
        assert PermissionAction.WRITE.value == "write"
        assert PermissionAction.DELETE.value == "delete"
        assert PermissionAction.EXECUTE.value == "execute"
        assert PermissionAction.ADMIN.value == "admin"


class TestPolicyEngineType:
    """Tests for PolicyEngineType enum."""

    def test_engine_values(self):
        """Test policy engine type string values."""
        assert PolicyEngineType.BUILTIN.value == "builtin"
        assert PolicyEngineType.OPA.value == "opa"
        assert PolicyEngineType.OSO.value == "oso"
        assert PolicyEngineType.ACL.value == "acl"
        assert PolicyEngineType.CUSTOM.value == "custom"


class TestComplianceFramework:
    """Tests for ComplianceFramework enum."""

    def test_framework_values(self):
        """Test compliance framework string values."""
        assert ComplianceFramework.GDPR.value == "gdpr"
        assert ComplianceFramework.HIPAA.value == "hipaa"
        assert ComplianceFramework.SOX.value == "sox"
        assert ComplianceFramework.PCI_DSS.value == "pci_dss"
        assert ComplianceFramework.ISO27001.value == "iso27001"
        assert ComplianceFramework.NIST.value == "nist"


class TestIdentityProviderType:
    """Tests for IdentityProviderType enum."""

    def test_provider_values(self):
        """Test identity provider type string values."""
        assert IdentityProviderType.OIDC.value == "oidc"
        assert IdentityProviderType.OAUTH2.value == "oauth2"
        assert IdentityProviderType.SAML.value == "saml"
        assert IdentityProviderType.LDAP.value == "ldap"
        assert IdentityProviderType.LOCAL.value == "local"


class TestSecurityPolicyType:
    """Tests for SecurityPolicyType enum."""

    def test_policy_values(self):
        """Test security policy type string values."""
        assert SecurityPolicyType.RBAC.value == "rbac"
        assert SecurityPolicyType.ABAC.value == "abac"
        assert SecurityPolicyType.ACL.value == "acl"
        assert SecurityPolicyType.CUSTOM.value == "custom"


class TestUserType:
    """Tests for UserType enum."""

    def test_user_type_values(self):
        """Test user type string values."""
        assert UserType.ADMINISTRATOR.value == "administrator"
        assert UserType.APPLICANT.value == "applicant"


class TestAuthenticatedUser:
    """Tests for AuthenticatedUser class."""

    def test_user_required_fields(self):
        """Test user with required fields."""
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
        assert user.created_at is not None
        assert user.user_type is None
        assert user.applicant_id is None

    def test_user_with_all_fields(self):
        """Test user with all fields populated."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        user = AuthenticatedUser(
            user_id="user-123",
            username="testuser",
            email="test@example.com",
            roles={"admin", "user"},
            permissions={"read", "write"},
            session_id="session-456",
            auth_method="password",
            expires_at=expires_at,
            metadata={"key": "value"},
            user_type="administrator",
        )

        assert user.user_id == "user-123"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.roles == {"admin", "user"}
        assert user.permissions == {"read", "write"}
        assert user.session_id == "session-456"
        assert user.auth_method == "password"
        assert user.expires_at == expires_at
        assert user.user_type == "administrator"

    def test_user_with_list_roles(self):
        """Test that list roles are converted to set."""
        user = AuthenticatedUser(
            user_id="user-123",
            roles=["admin", "user"],
        )
        assert isinstance(user.roles, set)
        assert user.roles == {"admin", "user"}

    def test_user_with_list_permissions(self):
        """Test that list permissions are converted to set."""
        user = AuthenticatedUser(
            user_id="user-123",
            permissions=["read", "write"],
        )
        assert isinstance(user.permissions, set)
        assert user.permissions == {"read", "write"}

    def test_user_validation_empty_user_id(self):
        """Test validation rejects empty user_id."""
        with pytest.raises(ValueError, match="User ID cannot be empty"):
            AuthenticatedUser(user_id="   ")

    def test_user_validation_empty_username(self):
        """Test validation rejects empty username."""
        with pytest.raises(ValueError, match="Username cannot be empty"):
            AuthenticatedUser(user_id="user-123", username="   ")

    def test_user_validation_invalid_email(self):
        """Test validation rejects invalid email."""
        with pytest.raises(ValueError, match="Invalid email format"):
            AuthenticatedUser(user_id="user-123", email="invalid-email")

    def test_user_has_role(self):
        """Test has_role method."""
        user = AuthenticatedUser(
            user_id="user-123",
            roles={"admin", "user"},
        )
        assert user.has_role("admin") is True
        assert user.has_role("user") is True
        assert user.has_role("guest") is False

    def test_user_has_permission(self):
        """Test has_permission method."""
        user = AuthenticatedUser(
            user_id="user-123",
            permissions={"read", "write"},
        )
        assert user.has_permission("read") is True
        assert user.has_permission("write") is True
        assert user.has_permission("delete") is False

    def test_user_has_any_role(self):
        """Test has_any_role method."""
        user = AuthenticatedUser(
            user_id="user-123",
            roles={"admin"},
        )
        assert user.has_any_role({"admin", "superadmin"}) is True
        assert user.has_any_role({"user", "guest"}) is False

    def test_user_has_all_roles(self):
        """Test has_all_roles method."""
        user = AuthenticatedUser(
            user_id="user-123",
            roles={"admin", "user", "moderator"},
        )
        assert user.has_all_roles({"admin", "user"}) is True
        assert user.has_all_roles({"admin", "superadmin"}) is False

    def test_user_has_any_permission(self):
        """Test has_any_permission method."""
        user = AuthenticatedUser(
            user_id="user-123",
            permissions={"read"},
        )
        assert user.has_any_permission({"read", "write"}) is True
        assert user.has_any_permission({"delete", "admin"}) is False

    def test_user_has_all_permissions(self):
        """Test has_all_permissions method."""
        user = AuthenticatedUser(
            user_id="user-123",
            permissions={"read", "write", "delete"},
        )
        assert user.has_all_permissions({"read", "write"}) is True
        assert user.has_all_permissions({"read", "admin"}) is False

    def test_user_is_administrator(self):
        """Test is_administrator method."""
        admin_by_type = AuthenticatedUser(
            user_id="user-123",
            user_type="administrator",
        )
        assert admin_by_type.is_administrator() is True

        admin_by_role = AuthenticatedUser(
            user_id="user-456",
            roles={"administrator"},
        )
        assert admin_by_role.is_administrator() is True

        not_admin = AuthenticatedUser(user_id="user-789")
        assert not_admin.is_administrator() is False

    def test_user_is_applicant(self):
        """Test is_applicant method."""
        applicant_by_type = AuthenticatedUser(
            user_id="user-123",
            user_type="applicant",
        )
        assert applicant_by_type.is_applicant() is True

        applicant_by_role = AuthenticatedUser(
            user_id="user-456",
            roles={"applicant"},
        )
        assert applicant_by_role.is_applicant() is True

        not_applicant = AuthenticatedUser(user_id="user-789")
        assert not_applicant.is_applicant() is False

    def test_user_is_expired(self):
        """Test is_expired method."""
        # No expiry set
        user_no_expiry = AuthenticatedUser(user_id="user-123")
        assert user_no_expiry.is_expired() is False

        # Future expiry
        user_future = AuthenticatedUser(
            user_id="user-123",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        assert user_future.is_expired() is False

        # Past expiry
        user_expired = AuthenticatedUser(
            user_id="user-123",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert user_expired.is_expired() is True

    def test_user_time_until_expiry(self):
        """Test time_until_expiry method."""
        # No expiry set
        user_no_expiry = AuthenticatedUser(user_id="user-123")
        assert user_no_expiry.time_until_expiry() is None

        # Future expiry
        user_future = AuthenticatedUser(
            user_id="user-123",
            expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
        time_left = user_future.time_until_expiry()
        assert time_left is not None
        assert 3500 < time_left <= 3600  # Approximately 1 hour

        # Past expiry
        user_expired = AuthenticatedUser(
            user_id="user-123",
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )
        assert user_expired.time_until_expiry() == 0.0

    def test_user_with_session(self):
        """Test with_session method creates new instance."""
        original = AuthenticatedUser(
            user_id="user-123",
            username="testuser",
            session_id="old-session",
        )
        updated = original.with_session("new-session")

        assert updated.session_id == "new-session"
        assert original.session_id == "old-session"  # Original unchanged
        assert updated.user_id == original.user_id
        assert updated.username == original.username

    def test_user_with_expiry(self):
        """Test with_expiry method creates new instance."""
        original = AuthenticatedUser(user_id="user-123")
        new_expiry = datetime.now(timezone.utc) + timedelta(hours=2)
        updated = original.with_expiry(new_expiry)

        assert updated.expires_at == new_expiry
        assert original.expires_at is None  # Original unchanged

    def test_user_add_role(self):
        """Test add_role method creates new instance."""
        original = AuthenticatedUser(
            user_id="user-123",
            roles={"user"},
        )
        updated = original.add_role("admin")

        assert "admin" in updated.roles
        assert "user" in updated.roles
        assert "admin" not in original.roles  # Original unchanged

    def test_user_add_permission(self):
        """Test add_permission method creates new instance."""
        original = AuthenticatedUser(
            user_id="user-123",
            permissions={"read"},
        )
        updated = original.add_permission("write")

        assert "write" in updated.permissions
        assert "read" in updated.permissions
        assert "write" not in original.permissions  # Original unchanged

    def test_user_to_dict(self):
        """Test to_dict serialization."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
        user = AuthenticatedUser(
            user_id="user-123",
            username="testuser",
            email="test@example.com",
            roles={"admin"},
            permissions={"read"},
            session_id="session-456",
            auth_method="password",
            expires_at=expires_at,
            metadata={"key": "value"},
            user_type="administrator",
            applicant_id=None,
        )

        data = user.to_dict()

        assert data["user_id"] == "user-123"
        assert data["username"] == "testuser"
        assert data["email"] == "test@example.com"
        assert set(data["roles"]) == {"admin"}
        assert set(data["permissions"]) == {"read"}
        assert data["session_id"] == "session-456"
        assert data["auth_method"] == "password"
        assert data["user_type"] == "administrator"
        assert data["metadata"] == {"key": "value"}

    def test_user_from_dict(self):
        """Test from_dict deserialization."""
        created_at = datetime.now(timezone.utc)
        expires_at = created_at + timedelta(hours=1)
        data = {
            "user_id": "user-123",
            "username": "testuser",
            "email": "test@example.com",
            "roles": ["admin"],
            "permissions": ["read"],
            "session_id": "session-456",
            "auth_method": "password",
            "expires_at": expires_at.isoformat(),
            "metadata": {"key": "value"},
            "created_at": created_at.isoformat(),
            "user_type": "administrator",
            "applicant_id": None,
        }

        user = AuthenticatedUser.from_dict(data)

        assert user.user_id == "user-123"
        assert user.username == "testuser"
        assert user.email == "test@example.com"
        assert user.roles == {"admin"}
        assert user.permissions == {"read"}
        assert user.auth_method == "password"
        assert user.user_type == "administrator"

    def test_user_roundtrip_serialization(self):
        """Test to_dict/from_dict roundtrip."""
        original = AuthenticatedUser(
            user_id="user-123",
            username="testuser",
            email="test@example.com",
            roles={"admin", "user"},
            permissions={"read", "write"},
        )

        data = original.to_dict()
        restored = AuthenticatedUser.from_dict(data)

        assert restored.user_id == original.user_id
        assert restored.username == original.username
        assert restored.email == original.email
        assert restored.roles == original.roles
        assert restored.permissions == original.permissions

    def test_user_is_frozen(self):
        """Test that AuthenticatedUser is immutable (frozen)."""
        user = AuthenticatedUser(user_id="user-123")

        with pytest.raises(AttributeError):
            user.user_id = "new-id"


class TestSecurityPrincipal:
    """Tests for SecurityPrincipal class."""

    def test_principal_required_fields(self):
        """Test principal with required fields."""
        principal = SecurityPrincipal(id="principal-123", type="user")

        assert principal.id == "principal-123"
        assert principal.type == "user"
        assert principal.roles == set()
        assert principal.attributes == {}
        assert principal.permissions == set()
        assert principal.created_at is not None
        assert principal.identity_provider is None
        assert principal.session_id is None
        assert principal.expires_at is None

    def test_principal_with_all_fields(self):
        """Test principal with all fields populated."""
        expires_at = datetime.now(timezone.utc) + timedelta(hours=24)
        principal = SecurityPrincipal(
            id="service-123",
            type="service",
            roles={"service", "internal"},
            attributes={"environment": "production"},
            permissions={"read", "write"},
            identity_provider="local",
            session_id="session-456",
            expires_at=expires_at,
        )

        assert principal.id == "service-123"
        assert principal.type == "service"
        assert principal.roles == {"service", "internal"}
        assert principal.attributes["environment"] == "production"
        assert principal.permissions == {"read", "write"}
        assert principal.identity_provider == "local"
        assert principal.session_id == "session-456"
        assert principal.expires_at == expires_at

    def test_principal_types(self):
        """Test different principal types."""
        user_principal = SecurityPrincipal(id="user-1", type="user")
        service_principal = SecurityPrincipal(id="svc-1", type="service")
        device_principal = SecurityPrincipal(id="device-1", type="device")

        assert user_principal.type == "user"
        assert service_principal.type == "service"
        assert device_principal.type == "device"
