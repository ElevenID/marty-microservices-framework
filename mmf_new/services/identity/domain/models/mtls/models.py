"""
Core mTLS domain models.

This module contains the core domain models for mTLS authentication including
certificate validation, trust chain management, and certificate authority handling.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from mmf_new.core.domain.entity import ValueObject


class CertificateStatus(Enum):
    """Certificate validation status."""

    VALID = "valid"  # Certificate is valid and trusted
    EXPIRED = "expired"  # Certificate has expired
    NOT_YET_VALID = "not_yet_valid"  # Certificate is not yet valid
    REVOKED = "revoked"  # Certificate has been revoked
    UNKNOWN_CA = "unknown_ca"  # Certificate issued by unknown CA
    INVALID_SIGNATURE = "invalid_signature"  # Certificate signature is invalid
    UNTRUSTED_CA = "untrusted_ca"  # CA is not trusted
    CHAIN_INVALID = "chain_invalid"  # Certificate chain is invalid
    PARSING_ERROR = "parsing_error"  # Error parsing certificate


class CertificateType(Enum):
    """Certificate type classification."""

    CLIENT = "client"  # Client authentication certificate
    SERVER = "server"  # Server authentication certificate
    CA = "ca"  # Certificate Authority certificate
    INTERMEDIATE = "intermediate"  # Intermediate CA certificate
    ROOT = "root"  # Root CA certificate


@dataclass(frozen=True)
class CertificateSubject(ValueObject):
    """Certificate subject information."""

    common_name: str | None = None
    organization: str | None = None
    organizational_unit: str | None = None
    country: str | None = None
    state: str | None = None
    locality: str | None = None
    email_address: str | None = None

    # Additional subject attributes
    serial_number: str | None = None
    domain_component: str | None = None
    user_id: str | None = None

    def __post_init__(self):
        """Validate subject information."""
        # At least one field should be populated
        if not any(
            [
                self.common_name,
                self.organization,
                self.organizational_unit,
                self.email_address,
                self.user_id,
            ]
        ):
            raise ValueError("Certificate subject must have at least one identifying field")

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        if self.common_name:
            return self.common_name
        if self.email_address:
            return self.email_address
        if self.user_id:
            return self.user_id
        return self.organization or "Unknown Subject"

    def matches_identity(self, identity: str) -> bool:
        """Check if subject matches a given identity."""
        identity_lower = identity.lower()
        return any(
            [
                self.common_name and self.common_name.lower() == identity_lower,
                self.email_address and self.email_address.lower() == identity_lower,
                self.user_id and self.user_id.lower() == identity_lower,
            ]
        )


@dataclass(frozen=True)
class CertificateIssuer(ValueObject):
    """Certificate issuer (CA) information."""

    common_name: str | None = None
    organization: str | None = None
    organizational_unit: str | None = None
    country: str | None = None
    state: str | None = None
    locality: str | None = None

    # CA-specific attributes
    ca_identifier: str | None = None

    def __post_init__(self):
        """Validate issuer information."""
        # At least one field should be populated
        if not any([self.common_name, self.organization, self.ca_identifier]):
            raise ValueError("Certificate issuer must have at least one identifying field")

    @property
    def display_name(self) -> str:
        """Get human-readable display name."""
        if self.common_name:
            return self.common_name
        if self.organization:
            return self.organization
        return self.ca_identifier or "Unknown Issuer"

    def matches_ca(self, ca_name: str) -> bool:
        """Check if issuer matches a given CA name."""
        ca_name_lower = ca_name.lower()
        return any(
            [
                self.common_name and ca_name_lower in self.common_name.lower(),
                self.organization and ca_name_lower in self.organization.lower(),
                self.ca_identifier and ca_name_lower in self.ca_identifier.lower(),
            ]
        )


@dataclass(frozen=True)
class ClientCertificate(ValueObject):
    """
    Client certificate domain model.

    Represents an X.509 client certificate with all relevant information
    for authentication and validation purposes.
    """

    # Certificate content
    pem_data: str  # PEM-encoded certificate
    der_data: bytes | None = None  # DER-encoded certificate (optional)

    # Certificate metadata
    serial_number: str | None = None
    fingerprint_sha1: str | None = None
    fingerprint_sha256: str | None = None

    # Certificate validity
    not_valid_before: datetime | None = None
    not_valid_after: datetime | None = None

    # Certificate identity
    subject: CertificateSubject | None = None
    issuer: CertificateIssuer | None = None

    # Certificate properties
    certificate_type: CertificateType = CertificateType.CLIENT
    key_usage: list[str] = field(default_factory=list)
    extended_key_usage: list[str] = field(default_factory=list)

    # Subject Alternative Names
    san_dns_names: list[str] = field(default_factory=list)
    san_ip_addresses: list[str] = field(default_factory=list)
    san_email_addresses: list[str] = field(default_factory=list)
    san_uris: list[str] = field(default_factory=list)

    # Additional metadata
    signature_algorithm: str | None = None
    public_key_algorithm: str | None = None
    public_key_size: int | None = None

    # Certificate chain context
    is_self_signed: bool = False
    ca_certificate: ClientCertificate | None = None

    def __post_init__(self):
        """Validate certificate data."""
        if not self.pem_data or not self.pem_data.strip():
            raise ValueError("PEM data is required")

        if not self.pem_data.startswith("-----BEGIN CERTIFICATE-----"):
            raise ValueError("Invalid PEM certificate format")

        # Ensure timezone awareness for timestamps
        if self.not_valid_before and self.not_valid_before.tzinfo is None:
            object.__setattr__(
                self, "not_valid_before", self.not_valid_before.replace(tzinfo=timezone.utc)
            )

        if self.not_valid_after and self.not_valid_after.tzinfo is None:
            object.__setattr__(
                self, "not_valid_after", self.not_valid_after.replace(tzinfo=timezone.utc)
            )

    def is_valid_at(self, timestamp: datetime | None = None) -> bool:
        """Check if certificate is valid at given timestamp."""
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=timezone.utc)

        if self.not_valid_before and timestamp < self.not_valid_before:
            return False

        if self.not_valid_after and timestamp > self.not_valid_after:
            return False

        return True

    def is_expired(self) -> bool:
        """Check if certificate has expired."""
        if not self.not_valid_after:
            return False

        now = datetime.now(timezone.utc)
        return now > self.not_valid_after

    def expires_soon(self, warning_days: int = 30) -> bool:
        """Check if certificate expires within warning period."""
        if not self.not_valid_after:
            return False

        now = datetime.now(timezone.utc)
        warning_threshold = now + timedelta(days=warning_days)

        return self.not_valid_after <= warning_threshold

    def get_fingerprint(self, algorithm: str = "sha256") -> str | None:
        """Get certificate fingerprint using specified algorithm."""
        if algorithm.lower() == "sha1":
            return self.fingerprint_sha1
        elif algorithm.lower() == "sha256":
            return self.fingerprint_sha256
        return None

    def has_key_usage(self, usage: str) -> bool:
        """Check if certificate has specific key usage."""
        return usage.lower() in [ku.lower() for ku in self.key_usage]

    def has_extended_key_usage(self, usage: str) -> bool:
        """Check if certificate has specific extended key usage."""
        return usage.lower() in [eku.lower() for eku in self.extended_key_usage]

    def matches_hostname(self, hostname: str) -> bool:
        """Check if certificate matches a hostname via CN or SAN."""
        hostname_lower = hostname.lower()

        # Check Common Name
        if self.subject and self.subject.common_name:
            if self.subject.common_name.lower() == hostname_lower:
                return True

        # Check DNS Subject Alternative Names
        for dns_name in self.san_dns_names:
            if dns_name.lower() == hostname_lower:
                return True
            # Handle wildcard certificates
            if dns_name.startswith("*."):
                wildcard_domain = dns_name[2:].lower()
                if hostname_lower.endswith(f".{wildcard_domain}"):
                    return True

        return False

    def matches_email(self, email: str) -> bool:
        """Check if certificate matches an email address."""
        email_lower = email.lower()

        # Check subject email
        if self.subject and self.subject.email_address:
            if self.subject.email_address.lower() == email_lower:
                return True

        # Check SAN email addresses
        return email_lower in [e.lower() for e in self.san_email_addresses]

    def get_trust_chain_depth(self) -> int:
        """Get the depth of the certificate trust chain."""
        depth = 0
        current = self.ca_certificate
        while current is not None:
            depth += 1
            current = current.ca_certificate
        return depth


@dataclass(frozen=True)
class CertificateAuthority(ValueObject):
    """Certificate Authority information and trust configuration."""

    # CA identity
    ca_name: str
    ca_certificate: ClientCertificate

    # Trust configuration
    trusted: bool = True
    trust_level: str = "full"  # full, conditional, revoked

    # CA capabilities
    can_issue_client_certs: bool = True
    can_issue_server_certs: bool = True
    can_issue_ca_certs: bool = False

    # Validation settings
    check_revocation: bool = True
    require_valid_chain: bool = True

    # CRL and OCSP settings
    crl_urls: list[str] = field(default_factory=list)
    ocsp_urls: list[str] = field(default_factory=list)

    def __post_init__(self):
        """Validate CA configuration."""
        if not self.ca_name or not self.ca_name.strip():
            raise ValueError("CA name is required")

        if self.trust_level not in ["full", "conditional", "revoked"]:
            raise ValueError("Invalid trust level")

    def is_trusted(self) -> bool:
        """Check if CA is trusted."""
        return self.trusted and self.trust_level != "revoked"

    def can_issue_certificate_type(self, cert_type: CertificateType) -> bool:
        """Check if CA can issue specific certificate types."""
        if cert_type == CertificateType.CLIENT:
            return self.can_issue_client_certs
        elif cert_type == CertificateType.SERVER:
            return self.can_issue_server_certs
        elif cert_type in [CertificateType.CA, CertificateType.INTERMEDIATE, CertificateType.ROOT]:
            return self.can_issue_ca_certs
        return False


@dataclass(frozen=True)
class CertificateRevocationList(ValueObject):
    """Certificate Revocation List (CRL) information."""

    # CRL metadata
    issuer: CertificateIssuer
    this_update: datetime
    next_update: datetime | None = None

    # Revoked certificates
    revoked_serial_numbers: set[str] = field(default_factory=set)

    # CRL source
    crl_url: str | None = None
    crl_data: str | None = None  # PEM-encoded CRL

    def __post_init__(self):
        """Validate CRL data."""
        # Ensure timezone awareness
        if self.this_update.tzinfo is None:
            object.__setattr__(self, "this_update", self.this_update.replace(tzinfo=timezone.utc))

        if self.next_update and self.next_update.tzinfo is None:
            object.__setattr__(self, "next_update", self.next_update.replace(tzinfo=timezone.utc))

    def is_current(self) -> bool:
        """Check if CRL is current (not expired)."""
        if not self.next_update:
            return True  # No expiration specified

        now = datetime.now(timezone.utc)
        return now <= self.next_update

    def is_certificate_revoked(self, serial_number: str) -> bool:
        """Check if a certificate is in the revocation list."""
        return serial_number in self.revoked_serial_numbers


@dataclass(frozen=True)
class CertificateValidationPolicy(ValueObject):
    """Policy for certificate validation."""

    # Basic validation
    check_expiration: bool = True
    check_not_yet_valid: bool = True
    check_signature: bool = True

    # Trust chain validation
    require_trusted_ca: bool = True
    allow_self_signed: bool = False
    max_chain_depth: int = 10

    # Key usage validation
    require_client_auth_eku: bool = True
    allowed_key_usages: set[str] = field(
        default_factory=lambda: {"digital_signature", "key_encipherment", "key_agreement"}
    )

    # Revocation checking
    check_crl: bool = True
    check_ocsp: bool = False
    require_revocation_check: bool = False

    # Hostname/identity validation
    validate_hostname: bool = False
    validate_email: bool = False
    allowed_sans: set[str] = field(default_factory=set)

    # Security requirements
    min_key_size: int = 2048
    allowed_signature_algorithms: set[str] = field(
        default_factory=lambda: {"sha256WithRSAEncryption", "ecdsa-with-SHA256", "rsaPSS"}
    )

    # Time-based validation
    time_tolerance_seconds: int = 300  # 5 minutes clock skew tolerance

    def is_signature_algorithm_allowed(self, algorithm: str) -> bool:
        """Check if signature algorithm is allowed."""
        return algorithm in self.allowed_signature_algorithms

    def is_key_usage_valid(self, key_usages: list[str]) -> bool:
        """Check if certificate key usages are valid."""
        cert_usages = {ku.lower() for ku in key_usages}
        return cert_usages.issubset(self.allowed_key_usages)


@dataclass(frozen=True)
class CertificateValidationResult(ValueObject):
    """Result of certificate validation."""

    # Validation outcome
    status: CertificateStatus
    is_valid: bool

    # Validation details
    validation_errors: list[str] = field(default_factory=list)
    validation_warnings: list[str] = field(default_factory=list)

    # Certificate information
    certificate: ClientCertificate | None = None
    trust_chain: list[ClientCertificate] = field(default_factory=list)

    # Validation context
    validated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    validation_policy: CertificateValidationPolicy | None = None

    # Additional metadata
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """Validate result data."""
        # Ensure timezone awareness
        if self.validated_at.tzinfo is None:
            object.__setattr__(self, "validated_at", self.validated_at.replace(tzinfo=timezone.utc))

    def has_errors(self) -> bool:
        """Check if validation has errors."""
        return len(self.validation_errors) > 0

    def has_warnings(self) -> bool:
        """Check if validation has warnings."""
        return len(self.validation_warnings) > 0

    def get_error_summary(self) -> str:
        """Get summary of validation errors."""
        if not self.validation_errors:
            return "No errors"
        return "; ".join(self.validation_errors)

    def add_error(self, error: str) -> CertificateValidationResult:
        """Add validation error."""
        new_errors = list(self.validation_errors)
        new_errors.append(error)

        return CertificateValidationResult(
            status=CertificateStatus.INVALID_SIGNATURE,  # Mark as invalid
            is_valid=False,
            validation_errors=new_errors,
            validation_warnings=self.validation_warnings,
            certificate=self.certificate,
            trust_chain=self.trust_chain,
            validated_at=self.validated_at,
            validation_policy=self.validation_policy,
            metadata=self.metadata,
        )

    def add_warning(self, warning: str) -> CertificateValidationResult:
        """Add validation warning."""
        new_warnings = list(self.validation_warnings)
        new_warnings.append(warning)

        return CertificateValidationResult(
            status=self.status,
            is_valid=self.is_valid,
            validation_errors=self.validation_errors,
            validation_warnings=new_warnings,
            certificate=self.certificate,
            trust_chain=self.trust_chain,
            validated_at=self.validated_at,
            validation_policy=self.validation_policy,
            metadata=self.metadata,
        )


# Utility functions


def calculate_certificate_fingerprint(cert_data: bytes, algorithm: str = "sha256") -> str:
    """Calculate certificate fingerprint."""
    if algorithm.lower() == "sha1":
        hash_obj = hashlib.sha1()
    elif algorithm.lower() == "sha256":
        hash_obj = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    hash_obj.update(cert_data)
    return hash_obj.hexdigest().upper()


def create_validation_result(
    status: CertificateStatus,
    is_valid: bool,
    certificate: ClientCertificate | None = None,
    errors: list[str] | None = None,
    warnings: list[str] | None = None,
) -> CertificateValidationResult:
    """Create a certificate validation result."""
    return CertificateValidationResult(
        status=status,
        is_valid=is_valid,
        certificate=certificate,
        validation_errors=errors or [],
        validation_warnings=warnings or [],
    )
