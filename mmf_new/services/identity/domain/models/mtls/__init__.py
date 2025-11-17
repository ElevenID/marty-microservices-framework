"""
mTLS authentication domain models.

This package contains domain models for mutual TLS authentication including
certificate validation, authentication contexts, and user identity mapping.
"""

# Authentication models
from .authentication import (
    AuthenticationStatus,
    CertificateIdentity,
    MTLSAuthenticationContext,
    MTLSAuthenticationEvent,
    MTLSAuthenticationResult,
    MTLSSession,
    MTLSUserMapping,
    UserMappingMethod,
)

# Configuration models
from .configuration import (
    CertificateExtractionConfiguration,
    CertificateSource,
    CertificateValidationConfiguration,
    MTLSConfiguration,
    RevocationCheckConfiguration,
    RevocationCheckMethod,
    TrustStoreConfiguration,
    TrustStoreType,
    create_file_based_trust_store,
    create_mtls_config,
    create_pkcs11_trust_store,
)

# Certificate models
from .models import (
    AuthorityInformationAccess,
    AuthorityKeyIdentifier,
    BasicConstraints,
    CertificateAuthority,
    CertificateError,
    CertificateExtension,
    CertificateIssuer,
    CertificatePolicies,
    CertificateStatus,
    CertificateSubject,
    CertificateValidationPolicy,
    CertificateValidationResult,
    ClientCertificate,
    CRLDistributionPoints,
    ExtendedKeyUsage,
    KeyUsage,
    SubjectAlternativeName,
    SubjectKeyIdentifier,
    X509Extension,
)

__all__ = [
    # Certificate models
    "ClientCertificate",
    "CertificateSubject",
    "CertificateIssuer",
    "CertificateValidationResult",
    "CertificateStatus",
    "CertificateAuthority",
    "CertificateError",
    "CertificateExtension",
    "X509Extension",
    "SubjectAlternativeName",
    "BasicConstraints",
    "KeyUsage",
    "ExtendedKeyUsage",
    "AuthorityKeyIdentifier",
    "SubjectKeyIdentifier",
    "CRLDistributionPoints",
    "AuthorityInformationAccess",
    "CertificatePolicies",
    "CertificateValidationPolicy",
    # Authentication models
    "AuthenticationStatus",
    "UserMappingMethod",
    "CertificateIdentity",
    "MTLSAuthenticationContext",
    "MTLSAuthenticationResult",
    "MTLSUserMapping",
    "MTLSSession",
    "MTLSAuthenticationEvent",
    # Configuration models
    "TrustStoreType",
    "RevocationCheckMethod",
    "CertificateSource",
    "TrustStoreConfiguration",
    "RevocationCheckConfiguration",
    "CertificateValidationConfiguration",
    "CertificateExtractionConfiguration",
    "MTLSConfiguration",
    "create_mtls_config",
    "create_file_based_trust_store",
    "create_pkcs11_trust_store",
]
