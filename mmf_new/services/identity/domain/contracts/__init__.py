"""Domain-level contracts for identity management."""

from abc import ABC, abstractmethod

from mmf_new.services.identity.domain.models import Credentials, Principal, UserId


class AuthenticationService(ABC):
    """Domain service for authentication logic."""

    @abstractmethod
    def authenticate(self, credentials: Credentials) -> Principal | None:
        """Authenticate a user with the given credentials."""

    @abstractmethod
    def validate_principal(self, principal: Principal) -> bool:
        """Validate that a principal is still valid."""


class UserRepository(ABC):
    """Domain contract for user persistence."""

    @abstractmethod
    def find_by_username(self, username: str) -> UserId | None:
        """Find a user by username."""

    @abstractmethod
    def verify_credentials(self, credentials: Credentials) -> bool:
        """Verify that credentials are valid."""
