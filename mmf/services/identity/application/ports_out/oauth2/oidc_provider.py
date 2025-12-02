"""
OIDC Provider Port Interface.

This module defines the port interface for OpenID Connect provider
functionality, extending OAuth2 with identity features.
"""

from abc import ABC, abstractmethod
from typing import Any

from mmf.services.identity.domain.models.oauth2 import (
    OAuth2AccessToken,
    OIDCAuthenticationRequest,
    OIDCDiscoveryDocument,
    OIDCIdToken,
    OIDCUserInfo,
)


class OIDCProvider(ABC):
    """
    OIDC Provider port interface.

    Defines the contract for OpenID Connect provider operations
    including ID token generation, user info, and discovery.
    """

    @abstractmethod
    async def create_id_token(
        self,
        user_id: str,
        client_id: str,
        scopes: set[str],
        nonce: str | None = None,
        auth_time: int | None = None,
        claims: dict[str, Any] | None = None,
    ) -> OIDCIdToken:
        """
        Create an OIDC ID token.

        Args:
            user_id: The user's identifier (subject)
            client_id: The client ID (audience)
            scopes: Granted scopes
            nonce: Optional nonce from authentication request
            auth_time: Time when user authentication occurred
            claims: Additional claims to include

        Returns:
            OIDCIdToken containing identity information

        Raises:
            ValueError: If required parameters are invalid
        """
        pass

    @abstractmethod
    async def get_user_info(self, access_token: OAuth2AccessToken) -> OIDCUserInfo:
        """
        Get user information for an access token.

        Args:
            access_token: Valid access token with appropriate scopes

        Returns:
            OIDCUserInfo containing user claims

        Raises:
            ValueError: If token is invalid or lacks required scopes
        """
        pass

    @abstractmethod
    async def get_discovery_document(self) -> OIDCDiscoveryDocument:
        """
        Get the OIDC discovery document.

        Returns:
            OIDCDiscoveryDocument with provider configuration
        """
        pass

    @abstractmethod
    async def get_jwks(self) -> dict[str, Any]:
        """
        Get the JSON Web Key Set (JWKS) for token verification.

        Returns:
            JWKS document containing public keys
        """
        pass

    @abstractmethod
    async def sign_id_token(self, id_token: OIDCIdToken) -> str:
        """
        Sign an ID token and return it as a JWT string.

        Args:
            id_token: The ID token to sign

        Returns:
            Signed JWT string

        Raises:
            RuntimeError: If signing fails
        """
        pass

    @abstractmethod
    async def verify_id_token(self, jwt_token: str) -> OIDCIdToken | None:
        """
        Verify and decode an ID token JWT.

        Args:
            jwt_token: The JWT token to verify

        Returns:
            OIDCIdToken if valid, None if invalid
        """
        pass

    @abstractmethod
    async def get_user_claims(
        self, user_id: str, scopes: set[str], requested_claims: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """
        Get user claims based on scopes and requested claims.

        Args:
            user_id: The user identifier
            scopes: Granted scopes
            requested_claims: Specific claims requested by client

        Returns:
            Dictionary of user claims
        """
        pass

    @abstractmethod
    async def validate_authentication_request(self, request: OIDCAuthenticationRequest) -> bool:
        """
        Validate an OIDC authentication request.

        Args:
            request: The OIDC authentication request

        Returns:
            True if request is valid, False otherwise
        """
        pass

    @abstractmethod
    async def get_issuer(self) -> str:
        """
        Get the OIDC issuer identifier.

        Returns:
            The issuer URL
        """
        pass

    @abstractmethod
    async def supports_scope(self, scope: str) -> bool:
        """
        Check if the provider supports a specific scope.

        Args:
            scope: The scope to check

        Returns:
            True if scope is supported, False otherwise
        """
        pass

    @abstractmethod
    async def supports_response_type(self, response_type: str) -> bool:
        """
        Check if the provider supports a specific response type.

        Args:
            response_type: The response type to check

        Returns:
            True if response type is supported, False otherwise
        """
        pass

    @abstractmethod
    async def get_supported_claims(self) -> list[str]:
        """
        Get the list of claims supported by this provider.

        Returns:
            list of supported claim names
        """
        pass
