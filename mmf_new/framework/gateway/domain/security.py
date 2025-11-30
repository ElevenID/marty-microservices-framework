"""
Gateway Security Services

This module provides services for handling security-related tasks in the gateway,
such as credential extraction.
"""

from abc import ABC, abstractmethod
from typing import Any

from .exceptions import AuthenticationError
from .models import AuthenticationType, GatewayRequest


class CredentialExtractor(ABC):
    """Abstract base class for credential extraction strategies."""

    @abstractmethod
    def extract(self, request: GatewayRequest) -> dict[str, Any]:
        """
        Extract credentials from the request.

        Returns:
            dict: A dictionary of credentials suitable for the authenticator.

        Raises:
            AuthenticationError: If credentials are missing or invalid format.
        """


class ApiKeyExtractor(CredentialExtractor):
    """Extracts API Key from headers."""

    def extract(self, request: GatewayRequest) -> dict[str, Any]:
        auth_header = request.get_header("Authorization") or ""
        # Check X-API-Key header first, then Authorization header
        api_key = request.get_header("X-API-Key")

        if not api_key and auth_header.startswith("ApiKey "):
            api_key = auth_header[7:]

        if not api_key:
            raise AuthenticationError("API key required")

        return {"method": "api_key", "api_key": api_key}


class BearerTokenExtractor(CredentialExtractor):
    """Extracts Bearer Token from Authorization header."""

    def extract(self, request: GatewayRequest) -> dict[str, Any]:
        auth_header = request.get_header("Authorization") or ""
        if not auth_header.startswith("Bearer "):
            raise AuthenticationError("Bearer token required")

        token = auth_header[7:]
        return {"method": "bearer", "token": token}


class CredentialExtractorFactory:
    """Factory for creating credential extractors."""

    _extractors = {
        AuthenticationType.API_KEY: ApiKeyExtractor(),
        AuthenticationType.BEARER_TOKEN: BearerTokenExtractor(),
    }

    @classmethod
    def get_extractor(cls, auth_type: AuthenticationType) -> CredentialExtractor | None:
        """Get the appropriate extractor for the auth type."""
        return cls._extractors.get(auth_type)
