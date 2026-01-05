"""
KMS Provider Interface

This module defines the abstract interface for Key Management System (KMS)
and Hardware Security Module (HSM) providers. MMF owns this interface as
authentication infrastructure, while Marty extends it for credential-specific
key operations.

Key ID Namespacing:
- auth:device:*, auth:session:* - MMF authentication keys
- cred:issuer:*, cred:holder:* - Marty credential keys (enforced by Marty)
"""

from abc import abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol, runtime_checkable


class KMSProviderType(Enum):
    """Supported KMS/HSM provider types."""

    AWS_KMS = "aws_kms"
    AZURE_KEY_VAULT = "azure_key_vault"
    GCP_KMS = "gcp_kms"
    HASHICORP_VAULT = "hashicorp_vault"
    PKCS11_HSM = "pkcs11_hsm"
    SOFTWARE_HSM = "software_hsm"  # For development/testing
    FILE_BASED = "file_based"  # For development only


class KeyAlgorithm(Enum):
    """Supported key algorithms."""

    # Elliptic Curve
    ES256 = "ES256"  # ECDSA P-256
    ES384 = "ES384"  # ECDSA P-384
    ES512 = "ES512"  # ECDSA P-521

    # Edwards Curve
    EDDSA = "EdDSA"  # Ed25519

    # RSA
    RS256 = "RS256"  # RSASSA-PKCS1-v1_5 with SHA-256
    RS384 = "RS384"  # RSASSA-PKCS1-v1_5 with SHA-384
    RS512 = "RS512"  # RSASSA-PKCS1-v1_5 with SHA-512
    PS256 = "PS256"  # RSASSA-PSS with SHA-256
    PS384 = "PS384"  # RSASSA-PSS with SHA-384
    PS512 = "PS512"  # RSASSA-PSS with SHA-512

    # Symmetric (for encryption)
    AES_128 = "A128GCM"
    AES_256 = "A256GCM"


class KeyOperation(Enum):
    """Key operations that can be audited."""

    GENERATE = "generate"
    IMPORT = "import"
    SIGN = "sign"
    ENCRYPT = "encrypt"
    DECRYPT = "decrypt"
    VERIFY = "verify"
    EXPORT_PUBLIC = "export_public"
    DELETE = "delete"
    ROTATE = "rotate"
    DERIVE = "derive"


@dataclass
class KeyMetadata:
    """Metadata about a managed key."""

    key_id: str
    algorithm: KeyAlgorithm
    provider_type: KMSProviderType
    provider_key_id: str
    created_at: datetime
    expires_at: datetime | None = None
    is_hardware_backed: bool = False
    allowed_operations: list[KeyOperation] = field(default_factory=list)
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def is_expired(self) -> bool:
        """Check if the key has expired."""
        if self.expires_at is None:
            return False
        return datetime.now(timezone.utc) > self.expires_at

    @property
    def namespace(self) -> str | None:
        """Extract namespace prefix from key_id (e.g., 'auth' from 'auth:device:123')."""
        if ":" in self.key_id:
            return self.key_id.split(":")[0]
        return None

    @property
    def is_auth_key(self) -> bool:
        """Check if this is an authentication key (MMF domain)."""
        return self.namespace == "auth"

    @property
    def is_credential_key(self) -> bool:
        """Check if this is a credential key (Marty domain)."""
        return self.namespace == "cred"


@dataclass
class KeyMaterial:
    """Key material with public key and metadata."""

    metadata: KeyMetadata
    public_key_pem: bytes
    public_key_jwk: dict[str, Any] | None = None

    @property
    def key_id(self) -> str:
        return self.metadata.key_id


@runtime_checkable
class IKMSProvider(Protocol):
    """
    Abstract interface for KMS/HSM providers.

    This is an MMF infrastructure interface. Implementations handle the
    actual cryptographic operations using various backends (cloud KMS,
    HSMs, or software for development).

    All key IDs should use namespacing:
    - auth:* for authentication keys (MMF)
    - cred:* for credential keys (Marty)
    """

    @property
    def provider_type(self) -> KMSProviderType:
        """Get the provider type."""
        ...

    async def generate_key(
        self,
        key_id: str,
        algorithm: KeyAlgorithm,
        *,
        expires_at: datetime | None = None,
        require_hardware: bool = False,
        labels: dict[str, str] | None = None,
    ) -> KeyMaterial:
        """
        Generate a new key pair.

        Args:
            key_id: Unique identifier with namespace prefix (e.g., "auth:device:123")
            algorithm: Key algorithm to use
            expires_at: Optional expiration time
            require_hardware: If True, raise error if hardware backing unavailable
            labels: Optional key-value labels for the key

        Returns:
            KeyMaterial with public key and metadata
        """
        ...

    async def sign(
        self,
        key_id: str,
        data: bytes,
        *,
        algorithm: KeyAlgorithm | None = None,
    ) -> bytes:
        """
        Sign data using the specified key.

        Args:
            key_id: Key identifier
            data: Data to sign
            algorithm: Override signature algorithm (uses key default if None)

        Returns:
            Signature bytes
        """
        ...

    async def verify(
        self,
        key_id: str,
        data: bytes,
        signature: bytes,
        *,
        algorithm: KeyAlgorithm | None = None,
    ) -> bool:
        """
        Verify a signature.

        Args:
            key_id: Key identifier
            data: Original data
            signature: Signature to verify
            algorithm: Override signature algorithm

        Returns:
            True if signature is valid
        """
        ...

    async def encrypt(
        self,
        key_id: str,
        plaintext: bytes,
        *,
        algorithm: KeyAlgorithm | None = None,
        additional_data: bytes | None = None,
    ) -> bytes:
        """
        Encrypt data using the specified key.

        Args:
            key_id: Key identifier
            plaintext: Data to encrypt
            algorithm: Override encryption algorithm
            additional_data: Additional authenticated data (for AEAD)

        Returns:
            Ciphertext bytes (format depends on algorithm)
        """
        ...

    async def decrypt(
        self,
        key_id: str,
        ciphertext: bytes,
        *,
        algorithm: KeyAlgorithm | None = None,
        additional_data: bytes | None = None,
    ) -> bytes:
        """
        Decrypt data using the specified key.

        Args:
            key_id: Key identifier
            ciphertext: Data to decrypt
            algorithm: Override decryption algorithm
            additional_data: Additional authenticated data (for AEAD)

        Returns:
            Plaintext bytes
        """
        ...

    async def get_public_key(self, key_id: str) -> bytes:
        """
        Get the public key in PEM format.

        Args:
            key_id: Key identifier

        Returns:
            Public key in PEM format
        """
        ...

    async def get_public_key_jwk(self, key_id: str) -> dict[str, Any]:
        """
        Get the public key in JWK format.

        Args:
            key_id: Key identifier

        Returns:
            Public key as JWK dictionary
        """
        ...

    async def get_key_metadata(self, key_id: str) -> KeyMetadata | None:
        """
        Get metadata for a key.

        Args:
            key_id: Key identifier

        Returns:
            KeyMetadata or None if key doesn't exist
        """
        ...

    async def key_exists(self, key_id: str) -> bool:
        """
        Check if a key exists.

        Args:
            key_id: Key identifier

        Returns:
            True if key exists
        """
        ...

    async def delete_key(self, key_id: str) -> bool:
        """
        Delete a key.

        Args:
            key_id: Key identifier

        Returns:
            True if key was deleted, False if it didn't exist
        """
        ...

    async def list_keys(
        self,
        *,
        namespace: str | None = None,
        labels: dict[str, str] | None = None,
    ) -> list[KeyMetadata]:
        """
        List keys matching the filter criteria.

        Args:
            namespace: Filter by namespace prefix (e.g., "auth" or "cred")
            labels: Filter by labels

        Returns:
            List of key metadata
        """
        ...

    async def rotate_key(
        self,
        key_id: str,
        *,
        new_expires_at: datetime | None = None,
    ) -> KeyMaterial:
        """
        Rotate a key, generating a new version.

        Args:
            key_id: Key identifier
            new_expires_at: Expiration for the new key version

        Returns:
            New key material
        """
        ...


@runtime_checkable
class IAuthKeyStore(Protocol):
    """
    Authentication-specific key store built on IKMSProvider.

    This interface provides higher-level operations for authentication
    key management, enforcing the auth: namespace.
    """

    @property
    def kms_provider(self) -> IKMSProvider:
        """Get the underlying KMS provider."""
        ...

    async def generate_device_key(
        self,
        device_id: str,
        *,
        algorithm: KeyAlgorithm = KeyAlgorithm.ES256,
        require_hardware: bool = True,
    ) -> KeyMaterial:
        """
        Generate a device identity key.

        Key ID will be: auth:device:{device_id}
        """
        ...

    async def generate_session_key(
        self,
        session_id: str,
        *,
        algorithm: KeyAlgorithm = KeyAlgorithm.ES256,
        expires_in_seconds: int = 3600,
    ) -> KeyMaterial:
        """
        Generate a session key for encrypted communication.

        Key ID will be: auth:session:{session_id}
        """
        ...

    async def sign_challenge(
        self,
        device_id: str,
        challenge: bytes,
    ) -> bytes:
        """Sign an authentication challenge using the device key."""
        ...

    async def get_device_public_key(self, device_id: str) -> bytes | None:
        """Get the device's public key in PEM format."""
        ...

    async def delete_device_key(self, device_id: str) -> bool:
        """Delete a device key (device will need to re-register)."""
        ...

    async def list_device_keys(self) -> list[KeyMetadata]:
        """List all device keys."""
        ...


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

    @classmethod
    def parse_session_id(cls, key_id: str) -> str | None:
        """Extract session ID from a session key ID."""
        if key_id.startswith(cls.SESSION):
            return key_id[len(cls.SESSION) :]
        return None
