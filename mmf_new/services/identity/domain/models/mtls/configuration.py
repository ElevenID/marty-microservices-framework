"""
mTLS configuration domain models.

This module contains configuration models for mTLS authentication including
certificate validation policies, trust store management, and security settings.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from mmf_new.core.domain.entity import ValueObject


class TrustStoreType(Enum):
    """Trust store backend types."""

    FILE_SYSTEM = "file_system"  # File-based certificate storage
    PKCS11 = "pkcs11"  # PKCS#11 hardware security modules
    WINDOWS_CERT_STORE = "windows"  # Windows Certificate Store
    MACOS_KEYCHAIN = "macos_keychain"  # macOS Keychain
    DATABASE = "database"  # Database-backed storage
    LDAP = "ldap"  # LDAP directory
    CUSTOM = "custom"  # Custom implementation


class RevocationCheckMethod(Enum):
    """Certificate revocation check methods."""

    CRL = "crl"  # Certificate Revocation List
    OCSP = "ocsp"  # Online Certificate Status Protocol
    BOTH = "both"  # Both CRL and OCSP
    NONE = "none"  # No revocation checking


class CertificateSource(Enum):
    """Source of client certificates."""

    HTTP_HEADER = "http_header"  # X.509 certificate in HTTP header
    TLS_HANDSHAKE = "tls_handshake"  # Certificate from TLS handshake
    REQUEST_BODY = "request_body"  # Certificate in request body
    QUERY_PARAMETER = "query_param"  # Certificate in query parameter
    CUSTOM = "custom"  # Custom extraction method


@dataclass(frozen=True)
class TrustStoreConfiguration(ValueObject):
    """Trust store configuration for CA certificates."""

    # Trust store type and location
    store_type: TrustStoreType = TrustStoreType.FILE_SYSTEM
    store_path: str | None = None
    store_password: str | None = None

    # File-based configuration
    ca_cert_files: list[str] = field(default_factory=list)
    ca_cert_directory: str | None = None

    # PKCS#11 configuration
    pkcs11_module: str | None = None
    pkcs11_slot: int | None = None
    pkcs11_pin: str | None = None

    # Database configuration
    db_connection_string: str | None = None
    ca_table_name: str = "trusted_cas"

    # LDAP configuration
    ldap_server_url: str | None = None
    ldap_base_dn: str | None = None
    ldap_bind_dn: str | None = None
    ldap_bind_password: str | None = None

    # Cache settings
    enable_ca_cache: bool = True
    ca_cache_ttl: timedelta = field(default_factory=lambda: timedelta(hours=24))
    max_cached_cas: int = 1000

    # Reload settings
    auto_reload_cas: bool = True
    reload_interval: timedelta = field(default_factory=lambda: timedelta(hours=1))

    def __post_init__(self):
        """Validate trust store configuration."""
        if self.store_type == TrustStoreType.FILE_SYSTEM:
            if not self.ca_cert_files and not self.ca_cert_directory:
                raise ValueError("File-based trust store requires CA cert files or directory")

        elif self.store_type == TrustStoreType.PKCS11:
            if not self.pkcs11_module:
                raise ValueError("PKCS#11 trust store requires module path")

        elif self.store_type == TrustStoreType.DATABASE:
            if not self.db_connection_string:
                raise ValueError("Database trust store requires connection string")

        elif self.store_type == TrustStoreType.LDAP:
            if not self.ldap_server_url or not self.ldap_base_dn:
                raise ValueError("LDAP trust store requires server URL and base DN")

        if self.ca_cache_ttl.total_seconds() <= 0:
            raise ValueError("CA cache TTL must be positive")

        if self.max_cached_cas <= 0:
            raise ValueError("Max cached CAs must be positive")


@dataclass(frozen=True)
class RevocationCheckConfiguration(ValueObject):
    """Certificate revocation checking configuration."""

    # Revocation check method
    check_method: RevocationCheckMethod = RevocationCheckMethod.CRL

    # CRL configuration
    crl_cache_enabled: bool = True
    crl_cache_ttl: timedelta = field(default_factory=lambda: timedelta(hours=1))
    crl_download_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    crl_max_size_mb: int = 50

    # OCSP configuration
    ocsp_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=10))
    ocsp_max_retries: int = 3
    ocsp_cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=30))

    # Fallback behavior
    fail_on_revocation_check_error: bool = False
    allow_revocation_check_bypass: bool = False

    # Performance settings
    parallel_revocation_checks: bool = True
    max_concurrent_checks: int = 10

    def __post_init__(self):
        """Validate revocation check configuration."""
        if self.crl_cache_ttl.total_seconds() <= 0:
            raise ValueError("CRL cache TTL must be positive")

        if self.crl_download_timeout.total_seconds() <= 0:
            raise ValueError("CRL download timeout must be positive")

        if self.crl_max_size_mb <= 0:
            raise ValueError("CRL max size must be positive")

        if self.ocsp_timeout.total_seconds() <= 0:
            raise ValueError("OCSP timeout must be positive")

        if self.max_concurrent_checks <= 0:
            raise ValueError("Max concurrent checks must be positive")


@dataclass(frozen=True)
class CertificateValidationConfiguration(ValueObject):
    """Configuration for certificate validation policies."""

    # Basic validation settings
    strict_validation: bool = True
    allow_self_signed: bool = False
    require_key_usage: bool = True
    require_extended_key_usage: bool = True

    # Chain validation
    max_chain_length: int = 10
    verify_chain_signatures: bool = True
    require_complete_chain: bool = True

    # Time validation
    check_validity_period: bool = True
    allow_not_yet_valid: bool = False
    clock_skew_tolerance: timedelta = field(default_factory=lambda: timedelta(minutes=5))

    # Key and algorithm requirements
    min_rsa_key_size: int = 2048
    min_ecc_key_size: int = 256
    allowed_signature_algorithms: set[str] = field(
        default_factory=lambda: {
            "sha256WithRSAEncryption",
            "sha384WithRSAEncryption",
            "sha512WithRSAEncryption",
            "ecdsa-with-SHA256",
            "ecdsa-with-SHA384",
            "ecdsa-with-SHA512",
            "rsaPSS",
        }
    )

    # Key usage requirements
    required_key_usages: set[str] = field(default_factory=lambda: {"digital_signature"})
    required_extended_key_usages: set[str] = field(default_factory=lambda: {"client_auth"})

    # Subject and SAN validation
    require_common_name: bool = False
    allow_wildcard_cn: bool = False
    validate_subject_alt_names: bool = True

    # Trust and issuer validation
    require_trusted_issuer: bool = True
    allowed_issuers: set[str] = field(default_factory=set)
    blocked_issuers: set[str] = field(default_factory=set)

    def __post_init__(self):
        """Validate configuration settings."""
        if self.max_chain_length <= 0:
            raise ValueError("Max chain length must be positive")

        if self.min_rsa_key_size < 1024:
            raise ValueError("Minimum RSA key size must be at least 1024 bits")

        if self.min_ecc_key_size < 256:
            raise ValueError("Minimum ECC key size must be at least 256 bits")

        if self.clock_skew_tolerance.total_seconds() < 0:
            raise ValueError("Clock skew tolerance cannot be negative")


@dataclass(frozen=True)
class CertificateExtractionConfiguration(ValueObject):
    """Configuration for extracting certificates from requests."""

    # Certificate source
    certificate_source: CertificateSource = CertificateSource.TLS_HANDSHAKE

    # HTTP header configuration
    certificate_header_name: str = "X-Client-Cert"
    certificate_header_encoding: str = "pem"  # pem, der, base64

    # Query parameter configuration
    certificate_param_name: str = "client_cert"
    certificate_param_encoding: str = "url_encoded_pem"

    # Request body configuration
    certificate_body_field: str = "client_certificate"
    certificate_body_format: str = "json"  # json, form, raw

    # Certificate format handling
    auto_detect_format: bool = True
    support_certificate_chain: bool = True

    # Validation on extraction
    validate_on_extraction: bool = True
    require_certificate: bool = True

    def __post_init__(self):
        """Validate extraction configuration."""
        if self.certificate_header_encoding not in ["pem", "der", "base64"]:
            raise ValueError("Invalid certificate header encoding")

        if self.certificate_body_format not in ["json", "form", "raw"]:
            raise ValueError("Invalid certificate body format")


@dataclass(frozen=True)
class MTLSConfiguration(ValueObject):
    """
    Complete mTLS authentication configuration.

    This aggregates all mTLS-related configuration including certificate
    validation, trust stores, and extraction settings.
    """

    # Core configuration components
    trust_store: TrustStoreConfiguration = field(default_factory=TrustStoreConfiguration)
    revocation_check: RevocationCheckConfiguration = field(
        default_factory=RevocationCheckConfiguration
    )
    certificate_validation: CertificateValidationConfiguration = field(
        default_factory=CertificateValidationConfiguration
    )
    certificate_extraction: CertificateExtractionConfiguration = field(
        default_factory=CertificateExtractionConfiguration
    )

    # Feature flags
    enable_mtls_auth: bool = True
    enable_certificate_caching: bool = True
    enable_revocation_checking: bool = True
    enable_certificate_pinning: bool = False

    # Performance settings
    certificate_cache_size: int = 1000
    certificate_cache_ttl: timedelta = field(default_factory=lambda: timedelta(minutes=30))
    validation_timeout: timedelta = field(default_factory=lambda: timedelta(seconds=30))

    # Security settings
    log_certificate_details: bool = True
    log_validation_failures: bool = True
    audit_certificate_usage: bool = True

    # User mapping configuration
    map_certificate_to_user: bool = True
    user_id_source: str = "subject_cn"  # subject_cn, subject_email, subject_serial, san_email
    user_role_mapping: dict[str, list[str]] = field(default_factory=dict)

    # Development settings
    development_mode: bool = False
    allow_untrusted_certs: bool = False  # Only for development
    skip_hostname_verification: bool = False  # Only for development

    # Certificate pinning (if enabled)
    pinned_certificates: dict[str, str] = field(
        default_factory=dict
    )  # hostname -> cert fingerprint
    pinned_ca_certificates: set[str] = field(default_factory=set)  # CA cert fingerprints

    def __post_init__(self):
        """Validate mTLS configuration."""
        # Development mode validations
        if not self.development_mode:
            if self.allow_untrusted_certs:
                raise ValueError("Untrusted certificates not allowed in production mode")

            if self.skip_hostname_verification:
                raise ValueError("Hostname verification cannot be skipped in production mode")

        # Cache configuration validation
        if self.certificate_cache_size <= 0:
            raise ValueError("Certificate cache size must be positive")

        if self.certificate_cache_ttl.total_seconds() <= 0:
            raise ValueError("Certificate cache TTL must be positive")

        if self.validation_timeout.total_seconds() <= 0:
            raise ValueError("Validation timeout must be positive")

        # User ID source validation
        valid_user_id_sources = {
            "subject_cn",
            "subject_email",
            "subject_serial",
            "san_email",
            "custom",
        }
        if self.user_id_source not in valid_user_id_sources:
            raise ValueError(f"Invalid user ID source: {self.user_id_source}")

    @classmethod
    def create_development_config(cls) -> MTLSConfiguration:
        """Create a development-friendly configuration."""
        return cls(
            development_mode=True,
            trust_store=TrustStoreConfiguration(
                store_type=TrustStoreType.FILE_SYSTEM,
                ca_cert_directory="./dev_certs/ca",
                enable_ca_cache=False,  # Disable cache for dev
            ),
            certificate_validation=CertificateValidationConfiguration(
                strict_validation=False,
                allow_self_signed=True,
                require_key_usage=False,
                require_extended_key_usage=False,
                clock_skew_tolerance=timedelta(hours=1),  # More tolerant
            ),
            revocation_check=RevocationCheckConfiguration(
                check_method=RevocationCheckMethod.NONE,  # Skip for dev
                fail_on_revocation_check_error=False,
            ),
            allow_untrusted_certs=True,
            skip_hostname_verification=True,
            log_certificate_details=True,
            audit_certificate_usage=False,
        )

    @classmethod
    def create_production_config(cls) -> MTLSConfiguration:
        """Create a production-ready configuration."""
        return cls(
            development_mode=False,
            trust_store=TrustStoreConfiguration(
                store_type=TrustStoreType.FILE_SYSTEM,
                ca_cert_directory="/etc/ssl/certs",
                enable_ca_cache=True,
                auto_reload_cas=True,
            ),
            certificate_validation=CertificateValidationConfiguration(
                strict_validation=True,
                allow_self_signed=False,
                require_key_usage=True,
                require_extended_key_usage=True,
                min_rsa_key_size=2048,
                verify_chain_signatures=True,
            ),
            revocation_check=RevocationCheckConfiguration(
                check_method=RevocationCheckMethod.BOTH,
                fail_on_revocation_check_error=True,
                crl_cache_enabled=True,
            ),
            certificate_extraction=CertificateExtractionConfiguration(
                certificate_source=CertificateSource.TLS_HANDSHAKE,
                validate_on_extraction=True,
                require_certificate=True,
            ),
            log_certificate_details=True,
            log_validation_failures=True,
            audit_certificate_usage=True,
        )

    @classmethod
    def create_high_security_config(cls) -> MTLSConfiguration:
        """Create a high-security configuration."""
        return cls(
            development_mode=False,
            trust_store=TrustStoreConfiguration(
                store_type=TrustStoreType.PKCS11,  # Hardware security module
                enable_ca_cache=True,
                ca_cache_ttl=timedelta(minutes=30),  # Shorter cache
            ),
            certificate_validation=CertificateValidationConfiguration(
                strict_validation=True,
                allow_self_signed=False,
                require_key_usage=True,
                require_extended_key_usage=True,
                min_rsa_key_size=4096,  # Higher security
                min_ecc_key_size=384,
                max_chain_length=5,  # Shorter chains
                clock_skew_tolerance=timedelta(minutes=1),  # Strict timing
            ),
            revocation_check=RevocationCheckConfiguration(
                check_method=RevocationCheckMethod.BOTH,
                fail_on_revocation_check_error=True,
                ocsp_timeout=timedelta(seconds=5),  # Faster timeout
                crl_cache_ttl=timedelta(minutes=15),  # Shorter cache
            ),
            enable_certificate_pinning=True,
            certificate_cache_ttl=timedelta(minutes=5),  # Short cache
            validation_timeout=timedelta(seconds=10),  # Quick validation
            log_certificate_details=True,
            log_validation_failures=True,
            audit_certificate_usage=True,
        )


# Utility functions for common configuration tasks


def create_mtls_config(
    trust_store_path: str | None = None,
    ca_cert_files: list[str] | None = None,
    strict_validation: bool = True,
    check_revocation: bool = True,
) -> MTLSConfiguration:
    """Create mTLS configuration with common settings."""
    trust_store = TrustStoreConfiguration(
        store_type=TrustStoreType.FILE_SYSTEM,
        store_path=trust_store_path,
        ca_cert_files=ca_cert_files or [],
    )

    validation_config = CertificateValidationConfiguration(
        strict_validation=strict_validation,
        require_trusted_issuer=strict_validation,
    )

    revocation_config = RevocationCheckConfiguration(
        check_method=RevocationCheckMethod.CRL if check_revocation else RevocationCheckMethod.NONE,
    )

    return MTLSConfiguration(
        trust_store=trust_store,
        certificate_validation=validation_config,
        revocation_check=revocation_config,
    )


def create_file_based_trust_store(
    ca_cert_directory: str,
    ca_cert_files: list[str] | None = None,
) -> TrustStoreConfiguration:
    """Create file-based trust store configuration."""
    return TrustStoreConfiguration(
        store_type=TrustStoreType.FILE_SYSTEM,
        ca_cert_directory=ca_cert_directory,
        ca_cert_files=ca_cert_files or [],
        enable_ca_cache=True,
        auto_reload_cas=True,
    )


def create_pkcs11_trust_store(
    module_path: str,
    slot: int = 0,
    pin: str | None = None,
) -> TrustStoreConfiguration:
    """Create PKCS#11 trust store configuration."""
    return TrustStoreConfiguration(
        store_type=TrustStoreType.PKCS11,
        pkcs11_module=module_path,
        pkcs11_slot=slot,
        pkcs11_pin=pin,
        enable_ca_cache=True,
    )
