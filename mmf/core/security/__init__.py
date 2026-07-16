"""
Core Security Module

This module provides the core security infrastructure for the MMF framework.
It follows hexagonal architecture with clear separation of domain, ports, and adapters.

Key components:
- ports/: Interface definitions (IKMSProvider, IAuthKeyStore, etc.)
- domain/: Security domain models and logic
- session_keys: ECDH-based session key establishment

Key ID Namespacing:
- auth:* - Authentication keys (MMF infrastructure)
- cred:* - Credential keys (application layer)
"""

from .session_keys import (
    ECDHSessionEstablishment,
    EllipticCurve,
    EphemeralKeyPair,
    ISessionKeyEstablishment,
    KeyAgreementError,
    SessionExpiredError,
    SessionKeyError,
    SessionKeyMaterial,
    SessionKeyPrefix,
)

__all__ = [
    # Session key establishment
    "ISessionKeyEstablishment",
    "ECDHSessionEstablishment",
    "EllipticCurve",
    "EphemeralKeyPair",
    "SessionKeyMaterial",
    "SessionKeyPrefix",
    # Exceptions
    "SessionKeyError",
    "KeyAgreementError",
    "SessionExpiredError",
]
