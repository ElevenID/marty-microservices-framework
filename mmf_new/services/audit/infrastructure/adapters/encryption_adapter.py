"""Encryption adapter for audit data."""

import base64
import logging
import os
from typing import Any

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

from mmf_new.services.audit.domain.contracts import IAuditEncryption
from mmf_new.services.audit.domain.entities import RequestAuditEvent

logger = logging.getLogger(__name__)


class AuditEncryptionAdapter(IAuditEncryption):
    """Encryption adapter using Scrypt KDF and AES-256."""

    def __init__(self, encryption_key: bytes | None = None):
        """Initialize encryption adapter.

        Args:
            encryption_key: Optional pre-derived encryption key
        """
        self.encryption_key = encryption_key or self._derive_key()
        self.sensitive_fields = {
            "password",
            "token",
            "secret",
            "key",
            "api_key",
            "credit_card",
            "ssn",
            "email",
            "phone",
            "address",
            "authorization",
            "cookie",
        }

    def _derive_key(self) -> bytes:
        """Derive encryption key using Scrypt KDF.

        Returns:
            32-byte encryption key
        """
        key_material = os.environ.get(
            "AUDIT_ENCRYPTION_KEY", "default-audit-key-change-in-production"
        )
        salt = os.environ.get("AUDIT_SALT", "audit-salt-12345").encode()

        kdf = Scrypt(
            salt=salt,
            length=32,
            n=2**14,  # CPU/memory cost parameter
            r=8,  # Block size parameter
            p=1,  # Parallelization parameter
        )
        return kdf.derive(key_material.encode())

    def is_sensitive_field(self, field_name: str) -> bool:
        """Check if a field name indicates sensitive data.

        Args:
            field_name: Name of the field

        Returns:
            True if field is considered sensitive
        """
        field_lower = field_name.lower()
        return any(sensitive in field_lower for sensitive in self.sensitive_fields)

    def encrypt_field(self, field_name: str, value: Any) -> tuple[str, bool]:
        """Encrypt a field value if it's sensitive.

        Args:
            field_name: Name of the field
            value: Value to potentially encrypt

        Returns:
            Tuple of (encrypted_or_original_value, was_encrypted)
        """
        if not self.is_sensitive_field(field_name):
            return (str(value), False)

        if not isinstance(value, str):
            value = str(value)

        try:
            encrypted_value = self._encrypt_value(value)
            return (encrypted_value, True)
        except Exception as e:
            logger.error(f"Failed to encrypt field {field_name}: {e}")
            return (f"[ENCRYPTION_FAILED:{value[:10]}...]", False)

    def decrypt_field(self, encrypted_value: str) -> str:
        """Decrypt an encrypted field value.

        Args:
            encrypted_value: The encrypted value

        Returns:
            Decrypted value
        """
        try:
            return self._decrypt_value(encrypted_value)
        except Exception as e:
            logger.error(f"Failed to decrypt value: {e}")
            return "[DECRYPTION_FAILED]"

    def encrypt_event(self, event: RequestAuditEvent) -> RequestAuditEvent:
        """Encrypt sensitive fields in an audit event.

        Args:
            event: The audit event to encrypt

        Returns:
            Event with encrypted sensitive fields
        """
        encrypted_fields = []

        # Encrypt details dictionary
        if event.details:
            encrypted_details = {}
            for key, value in event.details.items():
                encrypted_value, was_encrypted = self.encrypt_field(key, value)
                encrypted_details[key] = encrypted_value
                if was_encrypted:
                    encrypted_fields.append(key)
            event.details = encrypted_details

        # Encrypt request context headers if present
        if event.request_context and event.request_context.headers:
            encrypted_headers = {}
            for key, value in event.request_context.headers.items():
                encrypted_value, was_encrypted = self.encrypt_field(key, value)
                encrypted_headers[key] = encrypted_value
                if was_encrypted:
                    encrypted_fields.append(f"request_context.headers.{key}")
            # Note: Since RequestContext is frozen, we can't modify it in-place
            # The caller would need to handle this appropriately

        event.encrypted_fields = encrypted_fields
        return event

    def _encrypt_value(self, value: str) -> str:
        """Encrypt a single value using AES-256-CBC.

        Args:
            value: Value to encrypt

        Returns:
            Base64-encoded encrypted value with IV
        """
        # Generate random IV (16 bytes for AES)
        iv = os.urandom(16)

        # Create cipher
        cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv))
        encryptor = cipher.encryptor()

        # Pad data to block size (PKCS7 padding)
        padded_data = value.encode("utf-8")
        padding_length = 16 - (len(padded_data) % 16)
        padded_data += bytes([padding_length]) * padding_length

        # Encrypt
        encrypted_data = encryptor.update(padded_data) + encryptor.finalize()

        # Return base64 encoded IV + encrypted data
        return base64.b64encode(iv + encrypted_data).decode("utf-8")

    def _decrypt_value(self, encrypted_value: str) -> str:
        """Decrypt a single value using AES-256-CBC.

        Args:
            encrypted_value: Base64-encoded encrypted value with IV

        Returns:
            Decrypted value
        """
        # Decode base64
        raw_data = base64.b64decode(encrypted_value.encode("utf-8"))

        # Extract IV and encrypted data
        iv = raw_data[:16]
        encrypted = raw_data[16:]

        # Create cipher
        cipher = Cipher(algorithms.AES(self.encryption_key), modes.CBC(iv))
        decryptor = cipher.decryptor()

        # Decrypt
        padded_data = decryptor.update(encrypted) + decryptor.finalize()

        # Remove PKCS7 padding
        padding_length = padded_data[-1]
        data = padded_data[:-padding_length]

        return data.decode("utf-8")
