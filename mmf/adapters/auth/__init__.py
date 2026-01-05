"""
Authentication Key Adapters

This module provides adapters for authentication key operations including:
- Device registration key management
- Challenge signing for push notifications
- Session key establishment

These are MMF infrastructure operations - credential-specific key operations
belong in the application layer (e.g., marty_plugin.common.crypto).

Key ID Namespacing:
- auth:device:{device_id} - Device identity keys
- auth:session:{session_id} - Session establishment keys
- auth:challenge:{challenge_id} - Challenge-response keys
"""

import base64
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional, Protocol, runtime_checkable

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey

logger = logging.getLogger(__name__)


class AuthKeyError(Exception):
    """Base exception for authentication key errors."""

    pass


class SigningKeyNotConfiguredError(AuthKeyError):
    """Raised when signing key is not configured."""

    pass


@dataclass
class ChallengeSignature:
    """Signed challenge data."""

    challenge_id: str
    signature: str  # Base64-encoded
    key_id: str
    timestamp: datetime


@runtime_checkable
class IChallengeSigner(Protocol):
    """
    Interface for challenge signing operations.

    Used for push notification authentication - server signs challenges
    that mobile clients verify to prove server authenticity.
    """

    @property
    def key_id(self) -> str:
        """Return the key identifier."""
        ...

    def get_public_key_pem(self) -> str:
        """Get the public key in PEM format for client distribution."""
        ...

    def get_public_key_der_base64(self) -> str:
        """Get the public key in base64-encoded DER format (compact for mobile)."""
        ...

    def sign(self, data: str) -> str:
        """
        Sign a string using the configured algorithm.

        Args:
            data: String to sign

        Returns:
            Base64-encoded signature
        """
        ...

    def verify(self, data: str, signature: str) -> bool:
        """
        Verify a signature.

        Args:
            data: Original string
            signature: Base64-encoded signature to verify

        Returns:
            True if signature is valid
        """
        ...


class RSAChallengeSigner:
    """
    RSA-based challenge signer implementation.

    Uses RSA-SHA256 for signing. Suitable for server-side challenge
    signing where the public key is distributed to mobile clients.
    """

    def __init__(
        self,
        private_key: RSAPrivateKey,
        public_key: RSAPublicKey,
        key_id: str = "default",
    ):
        """
        Initialize the signer with an RSA keypair.

        Args:
            private_key: RSA private key for signing
            public_key: RSA public key for distribution
            key_id: Key identifier for key rotation
        """
        self._private_key = private_key
        self._public_key = public_key
        self._key_id = key_id

    @classmethod
    def from_pem(
        cls,
        private_key_pem: str,
        password: bytes | None = None,
        key_id: str = "default",
    ) -> "RSAChallengeSigner":
        """
        Create signer from PEM-encoded private key.

        Args:
            private_key_pem: PEM-encoded RSA private key
            password: Optional password for encrypted keys
            key_id: Key identifier

        Returns:
            RSAChallengeSigner instance
        """
        private_key = serialization.load_pem_private_key(
            private_key_pem.encode("utf-8"),
            password=password,
        )
        if not isinstance(private_key, RSAPrivateKey):
            raise ValueError("Key must be an RSA private key")

        return cls(private_key, private_key.public_key(), key_id)

    @classmethod
    def from_env(cls) -> Optional["RSAChallengeSigner"]:
        """
        Create signer from environment variables.

        Looks for:
        - MMF_AUTH_SIGNING_PRIVATE_KEY: PEM-encoded private key (required)
        - MMF_AUTH_SIGNING_KEY_PASSWORD: Optional key password
        - MMF_AUTH_SIGNING_KEY_ID: Optional key identifier

        Returns:
            RSAChallengeSigner instance or None if not configured
        """
        private_key_pem = os.environ.get("MMF_AUTH_SIGNING_PRIVATE_KEY")
        if not private_key_pem:
            logger.warning(
                "MMF_AUTH_SIGNING_PRIVATE_KEY not set. " "Challenge signing is disabled."
            )
            return None

        password = os.environ.get("MMF_AUTH_SIGNING_KEY_PASSWORD")
        password_bytes = password.encode("utf-8") if password else None
        key_id = os.environ.get("MMF_AUTH_SIGNING_KEY_ID", "default")

        signer = cls.from_pem(private_key_pem, password_bytes, key_id)
        logger.info(f"Auth challenge signer initialized with key ID: {key_id}")
        return signer

    @classmethod
    def generate_keypair(cls, key_size: int = 2048) -> "RSAChallengeSigner":
        """
        Generate a new RSA keypair.

        For development/testing only. In production, use managed keys.

        Args:
            key_size: RSA key size in bits (2048 or 4096 recommended)

        Returns:
            RSAChallengeSigner with newly generated keypair
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )
        return cls(private_key, private_key.public_key(), key_id="generated")

    @property
    def key_id(self) -> str:
        """Return the key identifier."""
        return self._key_id

    def get_public_key_pem(self) -> str:
        """Get the public key in PEM format."""
        return self._public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")

    def get_public_key_der_base64(self) -> str:
        """Get the public key in base64-encoded DER format."""
        der_bytes = self._public_key.public_bytes(
            encoding=serialization.Encoding.DER,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return base64.b64encode(der_bytes).decode("utf-8")

    def sign(self, data: str) -> str:
        """Sign a string using RSA-SHA256."""
        signature = self._private_key.sign(
            data.encode("utf-8"),
            padding.PKCS1v15(),
            hashes.SHA256(),
        )
        return base64.b64encode(signature).decode("utf-8")

    def verify(self, data: str, signature: str) -> bool:
        """Verify a signature using RSA-SHA256."""
        try:
            signature_bytes = base64.b64decode(signature)
            self._public_key.verify(
                signature_bytes,
                data.encode("utf-8"),
                padding.PKCS1v15(),
                hashes.SHA256(),
            )
            return True
        except Exception:
            return False


# =============================================================================
# Auth Key Prefix Constants
# =============================================================================


class AuthKeyPrefix:
    """Key ID prefix constants for authentication keys."""

    DEVICE = "auth:device:"
    SESSION = "auth:session:"
    CHALLENGE = "auth:challenge:"
    API = "auth:api:"

    @classmethod
    def device_key_id(cls, device_id: str) -> str:
        """Create a device key ID."""
        return f"{cls.DEVICE}{device_id}"

    @classmethod
    def session_key_id(cls, session_id: str) -> str:
        """Create a session key ID."""
        return f"{cls.SESSION}{session_id}"

    @classmethod
    def is_auth_key(cls, key_id: str) -> bool:
        """Check if a key ID is an authentication key."""
        return key_id.startswith("auth:")

    @classmethod
    def parse_device_id(cls, key_id: str) -> str | None:
        """Extract device ID from a device key ID."""
        if key_id.startswith(cls.DEVICE):
            return key_id[len(cls.DEVICE) :]
        return None


# =============================================================================
# Global Signer Registry
# =============================================================================


_default_signer: IChallengeSigner | None = None


def configure_default_signer(signer: IChallengeSigner) -> None:
    """Configure the global default challenge signer."""
    global _default_signer  # Transitional: Singleton pattern will migrate to DI
    _default_signer = signer
    logger.info(f"Default auth signer configured with key ID: {signer.key_id}")


def get_default_signer() -> IChallengeSigner:
    """Get the global default challenge signer."""
    if _default_signer is None:
        raise SigningKeyNotConfiguredError(
            "No default signer configured. "
            "Call configure_default_signer() or set MMF_AUTH_SIGNING_PRIVATE_KEY."
        )
    return _default_signer


def get_or_create_default_signer() -> IChallengeSigner | None:
    """Get the default signer, creating from env if not configured."""
    global _default_signer  # Transitional: Singleton pattern will migrate to DI
    if _default_signer is None:
        _default_signer = RSAChallengeSigner.from_env()
    return _default_signer


__all__ = [
    # Exceptions
    "AuthKeyError",
    "SigningKeyNotConfiguredError",
    # Data types
    "ChallengeSignature",
    # Interfaces
    "IChallengeSigner",
    # Implementations
    "RSAChallengeSigner",
    # Prefix constants
    "AuthKeyPrefix",
    # Global signer management
    "configure_default_signer",
    "get_default_signer",
    "get_or_create_default_signer",
]
