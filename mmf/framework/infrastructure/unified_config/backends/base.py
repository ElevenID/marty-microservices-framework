from abc import ABC, abstractmethod
from typing import Any

from mmf.framework.infrastructure.unified_config.models import SecretMetadata


class SecretBackendInterface(ABC):
    """Abstract interface for secret backends."""

    @abstractmethod
    async def get_secret(self, key: str) -> str | None:
        """Retrieve a secret value."""

    @abstractmethod
    async def set_secret(
        self, key: str, value: str, metadata: SecretMetadata | None = None
    ) -> bool:
        """Store a secret value."""

    @abstractmethod
    async def delete_secret(self, key: str) -> bool:
        """Delete a secret."""

    @abstractmethod
    async def list_secrets(self, prefix: str = "") -> list[str]:
        """List available secrets."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Check backend health."""


class ConfigurationBackendInterface(ABC):
    """Abstract interface for configuration backends."""

    @abstractmethod
    async def load_config(self, name: str) -> dict[str, Any]:
        """Load configuration from backend."""

    @abstractmethod
    async def save_config(self, name: str, config: dict[str, Any]) -> bool:
        """Save configuration to backend."""
