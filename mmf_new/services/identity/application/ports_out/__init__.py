"""Outbound ports for external dependencies."""

from abc import ABC, abstractmethod

from mmf_new.services.identity.domain.models import Credentials, UserId


class UserRepository(ABC):
    """Port for user data persistence."""

    @abstractmethod
    def find_by_username(self, username: str) -> UserId | None:
        """Find a user by username."""

    @abstractmethod
    def verify_credentials(self, credentials: Credentials) -> bool:
        """Verify user credentials."""


class EventBus(ABC):
    """Port for publishing domain events."""

    @abstractmethod
    def publish(self, event: dict[str, any]) -> None:
        """Publish an event."""
