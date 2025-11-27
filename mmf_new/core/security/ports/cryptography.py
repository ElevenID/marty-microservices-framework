"""
Cryptography Port

This module defines the interface for cryptography operations.
"""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ICryptographyManager(Protocol):
    """Interface for cryptography management."""

    def encrypt_data(self, data: str | bytes, key_id: str = "default") -> str:
        """
        Encrypt data using specified key.

        Args:
            data: Data to encrypt (string or bytes)
            key_id: Identifier for the encryption key

        Returns:
            Base64 encoded encrypted string with key version
        """
        ...

    def decrypt_data(self, encrypted_data: str, key_id: str = "default") -> str:
        """
        Decrypt data using specified key.

        Args:
            encrypted_data: Encrypted string to decrypt
            key_id: Identifier for the encryption key

        Returns:
            Decrypted string
        """
        ...

    def sign_data(self, data: str | bytes, key_id: str) -> str:
        """
        Sign data using RSA private key.

        Args:
            data: Data to sign
            key_id: Identifier for the signing key

        Returns:
            Base64 encoded signature
        """
        ...

    def verify_signature(self, data: str | bytes, signature: str, key_id: str) -> bool:
        """
        Verify signature using RSA public key.

        Args:
            data: Original data
            signature: Signature to verify
            key_id: Identifier for the signing key

        Returns:
            True if signature is valid, False otherwise
        """
        ...

    def hash_password(self, password: str) -> str:
        """
        Hash password using secure algorithm (e.g., bcrypt).

        Args:
            password: Plain text password

        Returns:
            Hashed password string
        """
        ...

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Verify password against hash.

        Args:
            password: Plain text password
            hashed_password: Stored password hash

        Returns:
            True if password matches, False otherwise
        """
        ...

    def rotate_key(self, key_id: str) -> None:
        """
        Rotate encryption key for the given ID.

        Args:
            key_id: Identifier for the key to rotate
        """
        ...
