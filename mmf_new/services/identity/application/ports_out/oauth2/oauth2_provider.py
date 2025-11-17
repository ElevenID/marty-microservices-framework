"""
OAuth2 Provider Port Interface.

This module defines the port interface for OAuth2 authorization server
functionality, including authorization flows and token management.
"""

from abc import ABC, abstractmethod
from typing import Optional

from mmf_new.services.identity.domain.models.oauth2 import (
    OAuth2AccessToken,
    OAuth2Authorization,
    OAuth2AuthorizationRequest,
    OAuth2AuthorizationResponse,
    OAuth2RefreshToken,
    OAuth2TokenIntrospection,
    OAuth2TokenRequest,
    OAuth2TokenResponse,
)


class OAuth2Provider(ABC):
    """
    OAuth2 Provider port interface.

    Defines the contract for OAuth2 authorization server operations
    including authorization flows, token issuance, and validation.
    """

    @abstractmethod
    async def authorize(
        self,
        request: OAuth2AuthorizationRequest,
        user_id: str,
        approved_scopes: set[str] | None = None,
    ) -> OAuth2AuthorizationResponse:
        """
        Process an OAuth2 authorization request.

        Args:
            request: The authorization request from the client
            user_id: The authenticated user's ID
            approved_scopes: Scopes approved by the user (defaults to requested scopes)

        Returns:
            OAuth2AuthorizationResponse containing authorization code or error

        Raises:
            ValueError: If request is invalid or client is not authorized
        """
        pass

    @abstractmethod
    async def exchange_code_for_tokens(self, request: OAuth2TokenRequest) -> OAuth2TokenResponse:
        """
        Exchange authorization code for access and refresh tokens.

        Args:
            request: Token request containing authorization code

        Returns:
            OAuth2TokenResponse containing tokens or error

        Raises:
            ValueError: If code is invalid, expired, or already used
        """
        pass

    @abstractmethod
    async def refresh_tokens(self, request: OAuth2TokenRequest) -> OAuth2TokenResponse:
        """
        Refresh access token using refresh token.

        Args:
            request: Token request containing refresh token

        Returns:
            OAuth2TokenResponse containing new tokens or error

        Raises:
            ValueError: If refresh token is invalid or expired
        """
        pass

    @abstractmethod
    async def client_credentials_grant(self, request: OAuth2TokenRequest) -> OAuth2TokenResponse:
        """
        Issue tokens for client credentials grant.

        Args:
            request: Token request with client credentials

        Returns:
            OAuth2TokenResponse containing access token or error

        Raises:
            ValueError: If client credentials are invalid
        """
        pass

    @abstractmethod
    async def introspect_token(
        self, token: str, client_id: str | None = None
    ) -> OAuth2TokenIntrospection:
        """
        Introspect an access token to get its metadata.

        Args:
            token: The access token to introspect
            client_id: Optional client ID for additional validation

        Returns:
            OAuth2TokenIntrospection with token metadata
        """
        pass

    @abstractmethod
    async def revoke_token(
        self, token: str, client_id: str, client_secret: str | None = None
    ) -> bool:
        """
        Revoke an access or refresh token.

        Args:
            token: The token to revoke
            client_id: Client ID requesting revocation
            client_secret: Client secret for authentication

        Returns:
            True if token was successfully revoked

        Raises:
            ValueError: If client authentication fails
        """
        pass

    @abstractmethod
    async def validate_access_token(
        self, token: str, required_scopes: set[str] | None = None
    ) -> OAuth2AccessToken | None:
        """
        Validate an access token and optionally check scopes.

        Args:
            token: The access token to validate
            required_scopes: Optional scopes that must be present

        Returns:
            OAuth2AccessToken if valid, None otherwise
        """
        pass

    @abstractmethod
    async def get_authorization(self, authorization_code: str) -> OAuth2Authorization | None:
        """
        Retrieve authorization by code.

        Args:
            authorization_code: The authorization code

        Returns:
            OAuth2Authorization if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_access_token(self, token: str) -> OAuth2AccessToken | None:
        """
        Retrieve access token by token value.

        Args:
            token: The access token value

        Returns:
            OAuth2AccessToken if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_refresh_token(self, token: str) -> OAuth2RefreshToken | None:
        """
        Retrieve refresh token by token value.

        Args:
            token: The refresh token value

        Returns:
            OAuth2RefreshToken if found, None otherwise
        """
        pass
