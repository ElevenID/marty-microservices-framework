"""Inbound ports for identity service use cases."""

from abc import ABC, abstractmethod

from mmf.services.identity.domain.models import AuthenticationResult, Credentials


class AuthenticatePrincipal(ABC):
    """Use case port for authenticating a principal."""

    @abstractmethod
    def execute(self, credentials: Credentials) -> AuthenticationResult:
        """Execute the authentication use case."""
