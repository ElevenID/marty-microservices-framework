from __future__ import annotations

from datetime import datetime, timedelta, timezone

from mmf.services.identity.domain.models.security_principal import SecurityPrincipal


def test_security_principal_defaults():
    principal = SecurityPrincipal.create(
        principal_id="user-123",
        principal_type="user",
        identity_provider="local",
    )

    assert principal.principal_id == "user-123"
    assert principal.principal_type == "user"
    assert principal.roles == frozenset()
    assert principal.permissions == frozenset()
    assert principal.identity_provider == "local"
    assert principal.created_at.tzinfo == timezone.utc


def test_security_principal_expiration_with_reference_time():
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)
    principal = SecurityPrincipal.create(
        principal_id="user-456",
        principal_type="user",
        identity_provider="local",
        expires_at=expires_at,
    )

    before_expiry = expires_at - timedelta(seconds=1)
    after_expiry = expires_at + timedelta(seconds=1)

    assert principal.is_expired(reference_time=before_expiry) is False
    assert principal.is_expired(reference_time=after_expiry) is True


def test_security_principal_role_and_permission_grants_are_immutable():
    principal = SecurityPrincipal.create(
        principal_id="svc-api",
        principal_type="service",
        identity_provider="oidc",
    )

    updated = principal.with_role("admin").with_permission("credential:issue")

    assert "admin" not in principal.roles
    assert "credential:issue" not in principal.permissions

    assert "admin" in updated.roles
    assert "credential:issue" in updated.permissions
    assert updated is not principal


def test_security_principal_audit_record_contains_expected_fields():
    principal = SecurityPrincipal.create(
        principal_id="auditor-1",
        principal_type="user",
        identity_provider="sso",
    ).with_role("auditor")

    record = principal.to_audit_record(resource="credential", action="view", result="success")

    assert record["principal_id"] == "auditor-1"
    assert record["action"] == "view"
    assert record["resource"] == "credential"
    assert record["result"] == "success"
    assert record["roles"] == ["auditor"]
    assert "timestamp" in record
