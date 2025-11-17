"""
mTLS authentication domain models.

This module contains domain models for mTLS authentication including
authentication contexts, user identity mapping, and authentication results.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional

from mmf_new.core.domain.entity import DomainEntity, ValueObject
from mmf_new.services.identity.domain.models.mtls.models import (
    CertificateStatus,
    CertificateValidationResult,
    ClientCertificate,
)
from mmf_new.services.identity.domain.models.user import User, UserId


class AuthenticationStatus(Enum):
    """Status of mTLS authentication attempt."""

    SUCCESS = "success"
    FAILED = "failed"
    PENDING = "pending"
    EXPIRED = "expired"
    REVOKED = "revoked"


class UserMappingMethod(Enum):
    """Methods for mapping certificate to user identity."""

    SUBJECT_CN = "subject_cn"  # Common Name from subject
    SUBJECT_EMAIL = "subject_email"  # Email from subject
    SUBJECT_SERIAL = "subject_serial"  # Serial number from subject
    SAN_EMAIL = "san_email"  # Email from Subject Alternative Name
    SAN_UPN = "san_upn"  # User Principal Name from SAN
    ISSUER_SERIAL = "issuer_serial"  # Issuer + serial combination
    FINGERPRINT = "fingerprint"  # Certificate fingerprint
    CUSTOM = "custom"  # Custom mapping logic


@dataclass(frozen=True)
class CertificateIdentity(ValueObject):
    """Identity extracted from client certificate."""

    # Identity fields
    user_id: str
    user_email: str | None = None
    user_name: str | None = None
    user_principal_name: str | None = None

    # Certificate information
    certificate_fingerprint: str = ""
    certificate_serial: str = ""
    certificate_issuer: str = ""
    certificate_subject: str = ""

    # Organizational information
    organization: str | None = None
    organizational_unit: str | None = None
    department: str | None = None
    title: str | None = None

    # Additional attributes
    custom_attributes: dict[str, str] = field(default_factory=dict)
    groups: set[str] = field(default_factory=set)
    roles: set[str] = field(default_factory=set)

    def __post_init__(self):
        """Validate certificate identity."""
        if not self.user_id.strip():
            raise ValueError("User ID cannot be empty")

        if self.user_email and "@" not in self.user_email:
            raise ValueError("Invalid email address format")


@dataclass(frozen=True)
class MTLSAuthenticationContext(ValueObject):
    """Context information for mTLS authentication."""

    # Request context
    request_id: str
    client_ip: str
    user_agent: str | None = None
    request_timestamp: datetime = field(default_factory=datetime.utcnow)

    # TLS context
    tls_version: str | None = None
    cipher_suite: str | None = None
    client_certificate_chain_length: int = 1

    # Certificate source
    certificate_source: str = "tls_handshake"
    certificate_header: str | None = None

    # Authentication metadata
    authentication_method: str = "mtls"
    trust_store_used: str | None = None
    ca_certificate_used: str | None = None

    # Security context
    requires_additional_auth: bool = False
    security_level: str = "standard"  # standard, high, maximum
    compliance_flags: set[str] = field(default_factory=set)

    def __post_init__(self):
        """Validate authentication context."""
        if not self.request_id.strip():
            raise ValueError("Request ID cannot be empty")

        if not self.client_ip.strip():
            raise ValueError("Client IP cannot be empty")


@dataclass
class MTLSAuthenticationResult(DomainEntity):
    """Result of mTLS authentication attempt."""

    # Authentication outcome
    status: AuthenticationStatus
    authenticated: bool = False

    # Certificate and validation
    client_certificate: ClientCertificate | None = None
    validation_result: CertificateValidationResult | None = None

    # User identity
    certificate_identity: CertificateIdentity | None = None
    mapped_user: User | None = None
    user_id: UserId | None = None

    # Authentication context
    context: MTLSAuthenticationContext | None = None

    # Error information
    error_code: str | None = None
    error_message: str | None = None
    error_details: dict[str, Any] = field(default_factory=dict)

    # Security information
    trust_level: str = "none"  # none, low, medium, high, maximum
    authentication_strength: str = "weak"  # weak, moderate, strong
    requires_step_up_auth: bool = False

    # Session information
    session_id: str | None = None
    session_expiry: datetime | None = None
    max_session_duration: timedelta = field(default_factory=lambda: timedelta(hours=8))

    # Audit information
    authenticated_at: datetime = field(default_factory=datetime.utcnow)
    authentication_duration_ms: int = 0
    validation_duration_ms: int = 0

    # Authorization context
    granted_roles: set[str] = field(default_factory=set)
    granted_permissions: set[str] = field(default_factory=set)
    access_constraints: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate authentication result."""
        if self.authenticated and not self.certificate_identity:
            raise ValueError("Authenticated result must have certificate identity")

        if self.authenticated and self.status != AuthenticationStatus.SUCCESS:
            raise ValueError("Authenticated result must have success status")

        if not self.authenticated and self.status == AuthenticationStatus.SUCCESS:
            raise ValueError("Failed authentication cannot have success status")

    @classmethod
    def create_success(
        cls,
        certificate: ClientCertificate,
        validation_result: CertificateValidationResult,
        identity: CertificateIdentity,
        context: MTLSAuthenticationContext,
        user: User | None = None,
    ) -> MTLSAuthenticationResult:
        """Create a successful authentication result."""
        return cls(
            status=AuthenticationStatus.SUCCESS,
            authenticated=True,
            client_certificate=certificate,
            validation_result=validation_result,
            certificate_identity=identity,
            mapped_user=user,
            user_id=user.id if user else None,
            context=context,
            trust_level="high" if validation_result.is_trusted else "medium",
            authentication_strength="strong",
        )

    @classmethod
    def create_failure(
        cls,
        error_code: str,
        error_message: str,
        context: MTLSAuthenticationContext | None = None,
        certificate: ClientCertificate | None = None,
        validation_result: CertificateValidationResult | None = None,
        error_details: dict[str, Any] | None = None,
    ) -> MTLSAuthenticationResult:
        """Create a failed authentication result."""
        return cls(
            status=AuthenticationStatus.FAILED,
            authenticated=False,
            client_certificate=certificate,
            validation_result=validation_result,
            context=context,
            error_code=error_code,
            error_message=error_message,
            error_details=error_details or {},
            trust_level="none",
            authentication_strength="weak",
        )

    @classmethod
    def create_revoked(
        cls,
        certificate: ClientCertificate,
        validation_result: CertificateValidationResult,
        context: MTLSAuthenticationContext,
        revocation_reason: str,
    ) -> MTLSAuthenticationResult:
        """Create a result for revoked certificate."""
        return cls(
            status=AuthenticationStatus.REVOKED,
            authenticated=False,
            client_certificate=certificate,
            validation_result=validation_result,
            context=context,
            error_code="CERTIFICATE_REVOKED",
            error_message=f"Certificate has been revoked: {revocation_reason}",
            error_details={"revocation_reason": revocation_reason},
        )

    def add_role(self, role: str) -> None:
        """Add a role to the authentication result."""
        self.granted_roles.add(role)

    def add_permission(self, permission: str) -> None:
        """Add a permission to the authentication result."""
        self.granted_permissions.add(permission)

    def add_access_constraint(self, key: str, value: Any) -> None:
        """Add an access constraint."""
        self.access_constraints[key] = value

    def has_role(self, role: str) -> bool:
        """Check if authentication result has a specific role."""
        return role in self.granted_roles

    def has_permission(self, permission: str) -> bool:
        """Check if authentication result has a specific permission."""
        return permission in self.granted_permissions

    def get_access_constraint(self, key: str) -> Any:
        """Get an access constraint value."""
        return self.access_constraints.get(key)

    def is_session_valid(self) -> bool:
        """Check if authentication session is still valid."""
        if not self.authenticated:
            return False

        if not self.session_expiry:
            return True

        return datetime.utcnow() < self.session_expiry

    def get_remaining_session_time(self) -> timedelta | None:
        """Get remaining time in authentication session."""
        if not self.session_expiry:
            return None

        remaining = self.session_expiry - datetime.utcnow()
        return remaining if remaining.total_seconds() > 0 else timedelta(0)


@dataclass(frozen=True)
class MTLSUserMapping(ValueObject):
    """Configuration for mapping certificate to user identity."""

    # Primary mapping method
    mapping_method: UserMappingMethod

    # Field extraction patterns
    user_id_pattern: str | None = None
    email_pattern: str | None = None
    name_pattern: str | None = None

    # Subject field mappings
    use_subject_cn: bool = True
    use_subject_email: bool = True
    use_subject_ou: bool = False

    # SAN field mappings
    use_san_email: bool = True
    use_san_upn: bool = True
    use_san_dns: bool = False

    # Default values and transformations
    default_domain: str | None = None
    email_domain_mapping: dict[str, str] = field(default_factory=dict)
    user_id_transformation: str = "lowercase"  # lowercase, uppercase, none

    # Role and group mapping
    role_mapping_enabled: bool = False
    role_mapping_rules: dict[str, list[str]] = field(default_factory=dict)
    default_roles: set[str] = field(default_factory=set)

    # Organizational mapping
    map_organizational_info: bool = True
    department_mapping: dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        """Validate user mapping configuration."""
        valid_transformations = {"lowercase", "uppercase", "none"}
        if self.user_id_transformation not in valid_transformations:
            raise ValueError(f"Invalid user ID transformation: {self.user_id_transformation}")


@dataclass
class MTLSSession(DomainEntity):
    """Active mTLS authentication session."""

    # Session identification
    session_id: str
    user_id: UserId

    # Certificate information
    certificate_fingerprint: str
    certificate_serial: str
    certificate_issuer: str

    # Session lifecycle
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: datetime | None = None
    last_activity: datetime = field(default_factory=datetime.utcnow)
    is_active: bool = True

    # Session context
    client_ip: str = ""
    user_agent: str | None = None
    authentication_context: MTLSAuthenticationContext | None = None

    # Security properties
    trust_level: str = "medium"
    authentication_strength: str = "strong"
    requires_revalidation: bool = False

    # Session data
    session_attributes: dict[str, Any] = field(default_factory=dict)
    granted_roles: set[str] = field(default_factory=set)
    granted_permissions: set[str] = field(default_factory=set)

    def update_activity(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = datetime.utcnow()

    def is_expired(self) -> bool:
        """Check if session has expired."""
        if not self.expires_at:
            return False

        return datetime.utcnow() > self.expires_at

    def invalidate(self) -> None:
        """Invalidate the session."""
        self.is_active = False

    def set_attribute(self, key: str, value: Any) -> None:
        """Set a session attribute."""
        self.session_attributes[key] = value

    def get_attribute(self, key: str, default: Any = None) -> Any:
        """Get a session attribute."""
        return self.session_attributes.get(key, default)

    def add_role(self, role: str) -> None:
        """Add a role to the session."""
        self.granted_roles.add(role)

    def remove_role(self, role: str) -> None:
        """Remove a role from the session."""
        self.granted_roles.discard(role)

    def add_permission(self, permission: str) -> None:
        """Add a permission to the session."""
        self.granted_permissions.add(permission)

    def remove_permission(self, permission: str) -> None:
        """Remove a permission from the session."""
        self.granted_permissions.discard(permission)


# Authentication event types for audit logging


@dataclass(frozen=True)
class MTLSAuthenticationEvent(ValueObject):
    """Event record for mTLS authentication audit."""

    # Event identification
    event_id: str
    event_type: str  # authentication_attempt, authentication_success, authentication_failure
    event_timestamp: datetime = field(default_factory=datetime.utcnow)

    # Authentication details
    authentication_result: MTLSAuthenticationResult
    user_id: UserId | None = None
    client_ip: str = ""

    # Certificate details (for audit)
    certificate_fingerprint: str = ""
    certificate_issuer: str = ""
    certificate_subject: str = ""

    # Security context
    trust_level: str = "none"
    risk_score: int = 0  # 0-100 scale
    anomaly_flags: set[str] = field(default_factory=set)

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)
