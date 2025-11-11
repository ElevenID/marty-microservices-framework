"""Platform core contracts for cross-cutting concerns."""

from abc import ABC, abstractmethod
from typing import Optional


class SecretStore(ABC):
    """Abstract interface for secret storage."""

    @abstractmethod
    def get_secret(self, key: str) -> str | None:
        """Get a secret by key."""

    @abstractmethod
    def set_secret(self, key: str, value: str) -> None:
        """Set a secret."""


class TelemetryProvider(ABC):
    """Abstract interface for telemetry collection."""

    @abstractmethod
    def record_metric(self, name: str, value: float, tags: dict[str, str]) -> None:
        """Record a metric."""

    @abstractmethod
    def record_event(self, name: str, attributes: dict[str, any]) -> None:
        """Record an event."""


class PolicyEngine(ABC):
    """Abstract interface for policy enforcement."""

    @abstractmethod
    def evaluate(self, policy: str, context: dict[str, any]) -> bool:
        """Evaluate a policy against a context."""
