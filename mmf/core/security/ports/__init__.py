"""
Security Ports

This package contains port interfaces for the security module.

Key interfaces:
- IKMSProvider: KMS/HSM provider abstraction for key management
- IAuthKeyStore: Authentication-specific key store
- ICryptographyManager: High-level crypto operations
"""

from .kms import (
    AuthKeyPrefix,
    IAuthKeyStore,
    IKMSProvider,
    KeyAlgorithm,
    KeyMaterial,
    KeyMetadata,
    KeyOperation,
    KMSProviderType,
)

__all__ = [
    # KMS/HSM interfaces
    "IKMSProvider",
    "IAuthKeyStore",
    "AuthKeyPrefix",
    # KMS types
    "KMSProviderType",
    "KeyAlgorithm",
    "KeyOperation",
    "KeyMetadata",
    "KeyMaterial",
]
