"""
Credential Adapters - MMF Interface Re-exports

MMF provides credential port interfaces (IKeyManager, ICredentialIssuer, etc.)
in mmf.core.credentials.ports. Vendor-specific implementations (SpruceID, Multipaz)
belong in the application layer (e.g., marty_plugin.adapters.credentials).

This module re-exports the port interfaces for convenience. For actual adapter
implementations, use marty_plugin.adapters.credentials.

Architecture:
- MMF owns: Interfaces/ports (IKeyManager, ICredentialIssuer, etc.)
- Application owns: Implementations (SpruceID, Multipaz adapters)

Key ID Namespacing:
- auth:* - MMF authentication keys
- cred:* - Application credential keys (Marty)
"""

# Re-export interfaces from core
from mmf.core.credentials.ports import (
    CredentialData,
    CredentialFormat,
    CredentialOffer,
    CredentialSubject,
    ICredentialIssuer,
    ICredentialVerifier,
    ICredentialWallet,
    IKeyManager,
    KeyAlgorithm,
    KeyPair,
    PresentationRequest,
    VerificationResult,
)

__all__ = [
    # Interfaces
    "IKeyManager",
    "ICredentialIssuer",
    "ICredentialWallet",
    "ICredentialVerifier",
    # Data types
    "KeyAlgorithm",
    "KeyPair",
    "CredentialData",
    "CredentialFormat",
    "CredentialOffer",
    "CredentialSubject",
    "PresentationRequest",
    "VerificationResult",
]
