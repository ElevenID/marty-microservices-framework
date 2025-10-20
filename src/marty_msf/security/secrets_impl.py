"""
Secrets Management Module

This module contains concrete implementations of secret management providers.
It depends only on the security.api layer, following the level contract principle.

Key Features:
- Environment variable-based secrets
- File-based secrets storage
- In-memory secrets (for testing)
- Encrypted secrets storage
"""

import json
import logging
import os
from pathlib import Path
from typing import Any

from .api import SecretManagerError

logger = logging.getLogger(__name__)


class EnvironmentSecretManager:
    """
    Environment variable-based secret manager.

    This manager retrieves secrets from environment variables,
    making it suitable for containerized deployments.
    """

    def __init__(self, prefix: str = "SECRET_"):
        """
        Initialize the environment secret manager.

        Args:
            prefix: Prefix for environment variable names
        """
        self.prefix = prefix

    def get_secret(self, key: str) -> str | None:
        """
        Retrieve a secret from environment variables.

        Args:
            key: Secret identifier

        Returns:
            Secret value or None if not found
        """
        try:
            env_key = f"{self.prefix}{key.upper()}"
            value = os.getenv(env_key)

            if value is not None:
                logger.debug("Retrieved secret %s from environment", key)
            else:
                logger.debug("Secret %s not found in environment", key)

            return value

        except Exception as e:
            logger.error("Error retrieving secret %s: %s", key, e)
            return None

    def store_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Store a secret (not supported for environment variables).

        Args:
            key: Secret identifier
            value: Secret value
            metadata: Optional metadata

        Returns:
            False (environment variables cannot be set at runtime)
        """
        logger.warning("Cannot store secrets in environment variables at runtime")
        return False

    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret (not supported for environment variables).

        Args:
            key: Secret identifier

        Returns:
            False (environment variables cannot be deleted at runtime)
        """
        logger.warning("Cannot delete environment variables at runtime")
        return False


class FileSecretManager:
    """
    File-based secret manager.

    This manager stores and retrieves secrets from JSON files on disk.
    Suitable for development and testing scenarios.
    """

    def __init__(self, secrets_file: str = "secrets.json"):
        """
        Initialize the file secret manager.

        Args:
            secrets_file: Path to the secrets file
        """
        self.secrets_file = Path(secrets_file)
        self._ensure_secrets_file()

    def get_secret(self, key: str) -> str | None:
        """
        Retrieve a secret from the secrets file.

        Args:
            key: Secret identifier

        Returns:
            Secret value or None if not found
        """
        try:
            secrets = self._load_secrets()
            value = secrets.get(key)

            if value is not None:
                logger.debug("Retrieved secret %s from file", key)
            else:
                logger.debug("Secret %s not found in file", key)

            return value

        except Exception as e:
            logger.error("Error retrieving secret %s from file: %s", key, e)
            return None

    def store_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Store a secret in the secrets file.

        Args:
            key: Secret identifier
            value: Secret value
            metadata: Optional metadata (stored alongside secret)

        Returns:
            True if successfully stored, False otherwise
        """
        try:
            secrets = self._load_secrets()

            # Store secret with metadata
            secret_entry = {
                "value": value,
                "metadata": metadata or {}
            }

            secrets[key] = secret_entry
            self._save_secrets(secrets)

            logger.info("Stored secret %s in file", key)
            return True

        except Exception as e:
            logger.error("Error storing secret %s in file: %s", key, e)
            return False

    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret from the secrets file.

        Args:
            key: Secret identifier

        Returns:
            True if successfully deleted, False otherwise
        """
        try:
            secrets = self._load_secrets()

            if key in secrets:
                del secrets[key]
                self._save_secrets(secrets)
                logger.info("Deleted secret %s from file", key)
                return True
            else:
                logger.warning("Secret %s not found for deletion", key)
                return False

        except Exception as e:
            logger.error("Error deleting secret %s from file: %s", key, e)
            return False

    def _ensure_secrets_file(self) -> None:
        """Ensure the secrets file exists."""
        if not self.secrets_file.exists():
            try:
                self.secrets_file.parent.mkdir(parents=True, exist_ok=True)
                self._save_secrets({})
                logger.debug("Created secrets file: %s", self.secrets_file)
            except Exception as e:
                logger.error("Failed to create secrets file: %s", e)

    def _load_secrets(self) -> dict[str, Any]:
        """Load secrets from the file."""
        try:
            with open(self.secrets_file) as f:
                data = json.load(f)

            # Handle both old format (direct key-value) and new format (with metadata)
            secrets = {}
            for key, value in data.items():
                if isinstance(value, dict) and "value" in value:
                    # New format with metadata
                    secrets[key] = value["value"]
                else:
                    # Old format (direct value)
                    secrets[key] = value

            return secrets

        except (FileNotFoundError, json.JSONDecodeError):
            logger.debug("Secrets file not found or invalid, starting with empty secrets")
            return {}
        except Exception as e:
            logger.error("Error loading secrets file: %s", e)
            return {}

    def _save_secrets(self, secrets: dict[str, Any]) -> None:
        """Save secrets to the file."""
        try:
            with open(self.secrets_file, 'w') as f:
                json.dump(secrets, f, indent=2)
        except Exception as e:
            logger.error("Error saving secrets file: %s", e)
            raise SecretManagerError(f"Failed to save secrets: {e}")


class InMemorySecretManager:
    """
    In-memory secret manager.

    This manager stores secrets in memory, suitable for testing
    and development scenarios where persistence is not required.
    """

    def __init__(self):
        """Initialize the in-memory secret manager."""
        self._secrets: dict[str, dict[str, Any]] = {}

    def get_secret(self, key: str) -> str | None:
        """
        Retrieve a secret from memory.

        Args:
            key: Secret identifier

        Returns:
            Secret value or None if not found
        """
        try:
            secret_entry = self._secrets.get(key)
            if secret_entry:
                logger.debug("Retrieved secret %s from memory", key)
                return secret_entry["value"]
            else:
                logger.debug("Secret %s not found in memory", key)
                return None

        except Exception as e:
            logger.error("Error retrieving secret %s from memory: %s", key, e)
            return None

    def store_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Store a secret in memory.

        Args:
            key: Secret identifier
            value: Secret value
            metadata: Optional metadata

        Returns:
            True if successfully stored
        """
        try:
            self._secrets[key] = {
                "value": value,
                "metadata": metadata or {}
            }
            logger.debug("Stored secret %s in memory", key)
            return True

        except Exception as e:
            logger.error("Error storing secret %s in memory: %s", key, e)
            return False

    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret from memory.

        Args:
            key: Secret identifier

        Returns:
            True if successfully deleted, False otherwise
        """
        try:
            if key in self._secrets:
                del self._secrets[key]
                logger.debug("Deleted secret %s from memory", key)
                return True
            else:
                logger.debug("Secret %s not found for deletion", key)
                return False

        except Exception as e:
            logger.error("Error deleting secret %s from memory: %s", key, e)
            return False

    def clear_all_secrets(self) -> None:
        """Clear all secrets from memory (utility method for testing)."""
        self._secrets.clear()
        logger.debug("Cleared all secrets from memory")

    def list_secret_keys(self) -> list[str]:
        """List all secret keys (utility method for testing)."""
        return list(self._secrets.keys())


class CompositeSecretManager:
    """
    Composite secret manager that tries multiple secret sources.

    This manager attempts to retrieve secrets from multiple sources
    in order of priority, useful for fallback scenarios.
    """

    def __init__(self, managers: list[Any]):
        """
        Initialize the composite secret manager.

        Args:
            managers: List of secret managers in order of priority
        """
        self.managers = managers

    def get_secret(self, key: str) -> str | None:
        """
        Retrieve a secret from the first available source.

        Args:
            key: Secret identifier

        Returns:
            Secret value from first source that has it, or None
        """
        for i, manager in enumerate(self.managers):
            try:
                value = manager.get_secret(key)
                if value is not None:
                    logger.debug("Retrieved secret %s from manager %d", key, i)
                    return value
            except Exception as e:
                logger.warning("Manager %d failed to retrieve secret %s: %s", i, key, e)
                continue

        logger.debug("Secret %s not found in any manager", key)
        return None

    def store_secret(self, key: str, value: str, metadata: dict[str, Any] | None = None) -> bool:
        """
        Store a secret in the first manager that supports storage.

        Args:
            key: Secret identifier
            value: Secret value
            metadata: Optional metadata

        Returns:
            True if any manager successfully stored the secret
        """
        for i, manager in enumerate(self.managers):
            try:
                if manager.store_secret(key, value, metadata):
                    logger.debug("Stored secret %s in manager %d", key, i)
                    return True
            except Exception as e:
                logger.warning("Manager %d failed to store secret %s: %s", i, key, e)
                continue

        logger.warning("No manager could store secret %s", key)
        return False

    def delete_secret(self, key: str) -> bool:
        """
        Delete a secret from all managers.

        Args:
            key: Secret identifier

        Returns:
            True if any manager successfully deleted the secret
        """
        success = False
        for i, manager in enumerate(self.managers):
            try:
                if manager.delete_secret(key):
                    logger.debug("Deleted secret %s from manager %d", key, i)
                    success = True
            except Exception as e:
                logger.warning("Manager %d failed to delete secret %s: %s", i, key, e)
                continue

        return success
