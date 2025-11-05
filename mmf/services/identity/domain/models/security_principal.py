from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Iterable, Mapping


def _ensure_utc(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


@dataclass(frozen=True)
class SecurityPrincipal:
    """Immutable representation of an authenticated principal within the identity service."""

    principal_id: str
    principal_type: str
    roles: frozenset[str] = field(default_factory=frozenset)
    permissions: frozenset[str] = field(default_factory=frozenset)
    attributes: Mapping[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    identity_provider: str | None = None
    session_id: str | None = None
    expires_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        principal_id: str,
        principal_type: str,
        identity_provider: str | None = None,
        roles: Iterable[str] | None = None,
        permissions: Iterable[str] | None = None,
        attributes: Mapping[str, Any] | None = None,
        session_id: str | None = None,
        expires_at: datetime | None = None,
        created_at: datetime | None = None,
    ) -> "SecurityPrincipal":
        created = _ensure_utc(created_at) or datetime.now(timezone.utc)
        expiry = _ensure_utc(expires_at)

        role_values = frozenset(str(role) for role in (roles or ()))
        permission_values = frozenset(str(permission) for permission in (permissions or ()))

        return cls(
            principal_id=principal_id,
            principal_type=principal_type,
            roles=role_values,
            permissions=permission_values,
            attributes=dict(attributes or {}),
            created_at=created,
            identity_provider=identity_provider,
            session_id=session_id,
            expires_at=expiry,
        )

    def is_expired(self, *, reference_time: datetime | None = None) -> bool:
        if self.expires_at is None:
            return False
        reference = _ensure_utc(reference_time) or datetime.now(timezone.utc)
        return reference >= self.expires_at

    def with_role(self, role: str) -> "SecurityPrincipal":
        if not role:
            return self
        return replace(self, roles=self.roles.union({role}))

    def with_permission(self, permission: str) -> "SecurityPrincipal":
        if not permission:
            return self
        return replace(self, permissions=self.permissions.union({permission}))

    def has_role(self, role: str) -> bool:
        return role in self.roles

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def with_session(self, session_id: str | None) -> "SecurityPrincipal":
        return replace(self, session_id=session_id)

    def to_audit_record(
        self,
        *,
        resource: str,
        action: str,
        result: str,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        record = {
            "principal_id": self.principal_id,
            "principal_type": self.principal_type,
            "identity_provider": self.identity_provider,
            "resource": resource,
            "action": action,
            "result": result,
            "roles": sorted(self.roles),
            "permissions": sorted(self.permissions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if metadata:
            record["metadata"] = dict(metadata)
        if self.session_id:
            record["session_id"] = self.session_id
        return record
