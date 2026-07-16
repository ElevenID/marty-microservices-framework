"""
Session Key Establishment

This module provides interfaces and utilities for secure session key
establishment using ECDH key agreement.

MMF provides the infrastructure for session establishment (ECDH, key derivation),
while protocol-specific implementations (e.g., ISO 18013-5 mDoc, OID4VP)
remain in the application layer.

Key ID Namespacing:
- auth:session:{session_id} - Session keys for encrypted communication
"""

import secrets
from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.kdf.hkdf import HKDF


class SessionKeyError(Exception):
    """Base exception for session key errors."""

    pass


class KeyAgreementError(SessionKeyError):
    """Error during ECDH key agreement."""

    pass


class SessionExpiredError(SessionKeyError):
    """Session has expired."""

    pass


class EllipticCurve(Enum):
    """Supported elliptic curves for ECDH."""

    P256 = "P-256"
    P384 = "P-384"
    P521 = "P-521"

    def to_cryptography_curve(self) -> ec.EllipticCurve:
        """Convert to cryptography library curve."""
        mapping = {
            EllipticCurve.P256: ec.SECP256R1(),
            EllipticCurve.P384: ec.SECP384R1(),
            EllipticCurve.P521: ec.SECP521R1(),
        }
        return mapping[self]


@dataclass
class SessionKeyMaterial:
    """Derived session key material from ECDH."""

    session_id: str
    encryption_key: bytes  # For encrypting outgoing messages
    decryption_key: bytes  # For decrypting incoming messages
    mac_key: bytes  # For message authentication
    established_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    @property
    def is_expired(self) -> bool:
        """Check if the session has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at


@dataclass
class EphemeralKeyPair:
    """Ephemeral key pair for ECDH key agreement."""

    private_key: ec.EllipticCurvePrivateKey
    public_key: ec.EllipticCurvePublicKey
    curve: EllipticCurve
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def get_public_key_bytes(self) -> bytes:
        """Get the public key as uncompressed bytes."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )

    def get_public_key_pem(self) -> str:
        """Get the public key as PEM string."""
        return self.public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode("utf-8")


@runtime_checkable
class ISessionKeyEstablishment(Protocol):
    """
    Interface for session key establishment.

    Provides ECDH-based key agreement for establishing encrypted
    communication channels.
    """

    def generate_ephemeral_keypair(
        self,
        curve: EllipticCurve = EllipticCurve.P256,
    ) -> EphemeralKeyPair:
        """Generate an ephemeral key pair for ECDH."""
        ...

    def establish_session(
        self,
        local_keypair: EphemeralKeyPair,
        peer_public_key_bytes: bytes,
        session_id: str | None = None,
        expires_in_seconds: int = 3600,
        info_context: bytes = b"",
    ) -> SessionKeyMaterial:
        """
        Establish a session using ECDH key agreement.

        Args:
            local_keypair: Our ephemeral key pair
            peer_public_key_bytes: Peer's public key (X962 uncompressed format)
            session_id: Optional session identifier (generated if not provided)
            expires_in_seconds: Session expiry time
            info_context: Additional context for key derivation

        Returns:
            Derived session key material
        """
        ...


class ECDHSessionEstablishment:
    """
    ECDH-based session key establishment.

    Uses ECDH key agreement with HKDF for key derivation,
    suitable for encrypted communication channels.
    """

    def __init__(
        self,
        default_curve: EllipticCurve = EllipticCurve.P256,
        key_length: int = 32,  # AES-256
    ):
        self.default_curve = default_curve
        self.key_length = key_length

    def generate_ephemeral_keypair(
        self,
        curve: EllipticCurve | None = None,
    ) -> EphemeralKeyPair:
        """Generate an ephemeral key pair for ECDH."""
        curve = curve or self.default_curve
        private_key = ec.generate_private_key(curve.to_cryptography_curve())
        return EphemeralKeyPair(
            private_key=private_key,
            public_key=private_key.public_key(),
            curve=curve,
        )

    def establish_session(
        self,
        local_keypair: EphemeralKeyPair,
        peer_public_key_bytes: bytes,
        session_id: str | None = None,
        expires_in_seconds: int = 3600,
        info_context: bytes = b"",
    ) -> SessionKeyMaterial:
        """
        Establish a session using ECDH key agreement.

        Performs ECDH to derive a shared secret, then uses HKDF to
        derive encryption, decryption, and MAC keys.
        """
        try:
            # Parse peer's public key
            peer_public_key = ec.EllipticCurvePublicKey.from_encoded_point(
                local_keypair.curve.to_cryptography_curve(),
                peer_public_key_bytes,
            )

            # Perform ECDH key agreement
            shared_secret = local_keypair.private_key.exchange(
                ec.ECDH(),
                peer_public_key,
            )

            # Generate session ID if not provided
            if session_id is None:
                session_id = secrets.token_hex(16)

            # Derive keys using HKDF
            session_id_bytes = session_id.encode("utf-8")

            encryption_key = self._derive_key(
                shared_secret,
                info=b"MMF Session Encryption" + info_context + session_id_bytes,
            )

            decryption_key = self._derive_key(
                shared_secret,
                info=b"MMF Session Decryption" + info_context + session_id_bytes,
            )

            mac_key = self._derive_key(
                shared_secret,
                info=b"MMF Session MAC" + info_context + session_id_bytes,
            )

            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)

            return SessionKeyMaterial(
                session_id=session_id,
                encryption_key=encryption_key,
                decryption_key=decryption_key,
                mac_key=mac_key,
                expires_at=expires_at,
            )

        except Exception as e:
            raise KeyAgreementError(f"Session establishment failed: {e}") from e

    def _derive_key(
        self,
        shared_secret: bytes,
        info: bytes,
        salt: bytes | None = None,
    ) -> bytes:
        """Derive a key using HKDF."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=self.key_length,
            salt=salt,
            info=info,
        )
        return hkdf.derive(shared_secret)


# =============================================================================
# Session Key Prefix
# =============================================================================


class SessionKeyPrefix:
    """Key ID prefix for session keys."""

    PREFIX = "auth:session:"

    @classmethod
    def session_key_id(cls, session_id: str) -> str:
        """Create a session key ID."""
        return f"{cls.PREFIX}{session_id}"

    @classmethod
    def is_session_key(cls, key_id: str) -> bool:
        """Check if a key ID is a session key."""
        return key_id.startswith(cls.PREFIX)

    @classmethod
    def parse_session_id(cls, key_id: str) -> str | None:
        """Extract session ID from a session key ID."""
        if key_id.startswith(cls.PREFIX):
            return key_id[len(cls.PREFIX) :]
        return None


__all__ = [
    # Exceptions
    "SessionKeyError",
    "KeyAgreementError",
    "SessionExpiredError",
    # Enums
    "EllipticCurve",
    # Data types
    "SessionKeyMaterial",
    "EphemeralKeyPair",
    # Interfaces
    "ISessionKeyEstablishment",
    # Implementations
    "ECDHSessionEstablishment",
    # Prefix utilities
    "SessionKeyPrefix",
]
