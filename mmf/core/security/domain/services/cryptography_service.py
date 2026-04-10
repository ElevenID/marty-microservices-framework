"""
Cryptography Domain Service

Advanced cryptography management for the security framework including
encryption, decryption, digital signatures, password hashing, and key rotation.
"""

import base64
import logging
import secrets
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import bcrypt
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa

from mmf.core.security.ports.cryptography import ICryptographyManager

logger = logging.getLogger(__name__)


class CryptographyService(ICryptographyManager):
    """
    Advanced cryptography management implementation.

    Implements the ICryptographyManager port using standard cryptography libraries.
    """

    def __init__(self, service_name: str):
        """Initialize cryptography manager."""
        self.service_name = service_name

        # Key management
        self.master_key = self._generate_master_key()
        self.encryption_keys: dict[str, bytes] = {}
        self.signing_keys: dict[str, rsa.RSAPrivateKey] = {}

        # Encryption instances
        self.fernet = Fernet(self.master_key)

        # Key rotation tracking
        self.key_versions: dict[str, int] = defaultdict(int)
        self.key_rotation_schedule: dict[str, datetime] = {}

    def _generate_master_key(self) -> bytes:
        """Generate or load master encryption key."""
        # In production, this should be loaded from secure key management service
        return Fernet.generate_key()

    def encrypt_data(self, data: str | bytes, key_id: str = "default") -> str:
        """Encrypt data using specified key."""
        if isinstance(data, str):
            data = data.encode("utf-8")

        # Get or create encryption key
        if key_id not in self.encryption_keys:
            self.encryption_keys[key_id] = Fernet.generate_key()

        fernet = Fernet(self.encryption_keys[key_id])
        encrypted_data = fernet.encrypt(data)

        # Return base64 encoded encrypted data with key version
        key_version = self.key_versions[key_id]
        return base64.b64encode(f"{key_version}:".encode() + encrypted_data).decode("utf-8")

    def decrypt_data(self, encrypted_data: str, key_id: str = "default") -> str:
        """Decrypt data using specified key."""
        try:
            # Decode base64
            decoded_data = base64.b64decode(encrypted_data.encode("utf-8"))

            # Extract key version and encrypted content
            if b":" in decoded_data:
                key_version_bytes, encrypted_content = decoded_data.split(b":", 1)
                # We could verify key version here if we stored history
                # int(key_version_bytes.decode("utf-8"))
            else:
                encrypted_content = decoded_data

            # Get appropriate key
            if key_id not in self.encryption_keys:
                raise ValueError(f"Encryption key {key_id} not found")

            fernet = Fernet(self.encryption_keys[key_id])
            decrypted_data = fernet.decrypt(encrypted_content)

            return decrypted_data.decode("utf-8")

        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")

    def generate_signing_key(self, key_id: str) -> rsa.RSAPrivateKey:
        """Generate RSA signing key."""
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=2048,
        )

        self.signing_keys[key_id] = private_key
        return private_key

    def sign_data(self, data: str | bytes, key_id: str) -> str:
        """Sign data using RSA private key."""
        if isinstance(data, str):
            data = data.encode("utf-8")

        if key_id not in self.signing_keys:
            self.generate_signing_key(key_id)

        private_key = self.signing_keys[key_id]
        signature = private_key.sign(
            data,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.MAX_LENGTH),
            hashes.SHA256(),
        )

        return base64.b64encode(signature).decode("utf-8")

    def verify_signature(self, data: str | bytes, signature: str, key_id: str) -> bool:
        """Verify signature using RSA public key."""
        try:
            if isinstance(data, str):
                data = data.encode("utf-8")

            if key_id not in self.signing_keys:
                return False

            private_key = self.signing_keys[key_id]
            public_key = private_key.public_key()

            signature_bytes = base64.b64decode(signature.encode("utf-8"))

            public_key.verify(
                signature_bytes,
                data,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )

            return True

        except Exception:
            logger.exception("Signature verification failed with unexpected error")
            return False

    def hash_password(self, password: str) -> str:
        """Hash password using bcrypt."""
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
        return hashed.decode("utf-8")

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """Verify password against hash."""
        try:
            return bcrypt.checkpw(password.encode("utf-8"), hashed_password.encode("utf-8"))
        except Exception:
            logger.exception("Password verification failed with unexpected error")
            return False

    def generate_secure_token(self, length: int = 32) -> str:
        """Generate cryptographically secure random token."""
        return secrets.token_urlsafe(length)

    def rotate_key(self, key_id: str) -> None:
        """Rotate encryption key."""
        # Increment key version
        self.key_versions[key_id] += 1

        # Generate new key
        self.encryption_keys[key_id] = Fernet.generate_key()

        # Schedule next rotation
        self.key_rotation_schedule[key_id] = datetime.now(timezone.utc) + timedelta(days=90)

    def should_rotate_key(self, key_id: str) -> bool:
        """Check if key should be rotated."""
        if key_id not in self.key_rotation_schedule:
            return True

        return datetime.now(timezone.utc) >= self.key_rotation_schedule[key_id]
