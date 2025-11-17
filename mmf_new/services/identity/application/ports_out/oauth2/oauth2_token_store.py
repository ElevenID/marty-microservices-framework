"""
OAuth2 Token Store Port Interface.

This module defines the port interface for OAuth2 token persistence
and management operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from mmf_new.services.identity.domain.models.oauth2 import (
    OAuth2AccessToken,
    OAuth2RefreshToken,
)


class OAuth2TokenStore(ABC):
    """
    OAuth2 Token Store port interface.

    Defines the contract for OAuth2 token persistence operations
    including storage, retrieval, and lifecycle management.
    """

    @abstractmethod
    async def save_access_token(self, token: OAuth2AccessToken) -> None:
        """
        Save an access token.

        Args:
            token: The access token to save

        Raises:
            ValueError: If token data is invalid
            RuntimeError: If save operation fails
        """
        pass

    @abstractmethod
    async def save_refresh_token(self, token: OAuth2RefreshToken) -> None:
        """
        Save a refresh token.

        Args:
            token: The refresh token to save

        Raises:
            ValueError: If token data is invalid
            RuntimeError: If save operation fails
        """
        pass

    @abstractmethod
    async def get_access_token(self, token: str) -> OAuth2AccessToken | None:
        """
        Retrieve an access token by token value.

        Args:
            token: The access token value

        Returns:
            OAuth2AccessToken if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_refresh_token(self, token: str) -> OAuth2RefreshToken | None:
        """
        Retrieve a refresh token by token value.

        Args:
            token: The refresh token value

        Returns:
            OAuth2RefreshToken if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_access_token_by_id(self, token_id: str) -> OAuth2AccessToken | None:
        """
        Retrieve an access token by token ID.

        Args:
            token_id: The token ID

        Returns:
            OAuth2AccessToken if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_refresh_token_by_id(self, token_id: str) -> OAuth2RefreshToken | None:
        """
        Retrieve a refresh token by token ID.

        Args:
            token_id: The token ID

        Returns:
            OAuth2RefreshToken if found, None otherwise
        """
        pass

    @abstractmethod
    async def revoke_access_token(self, token: str) -> bool:
        """
        Revoke an access token.

        Args:
            token: The access token value to revoke

        Returns:
            True if token was revoked, False if not found

        Raises:
            RuntimeError: If revocation fails
        """
        pass

    @abstractmethod
    async def revoke_refresh_token(self, token: str) -> bool:
        """
        Revoke a refresh token.

        Args:
            token: The refresh token value to revoke

        Returns:
            True if token was revoked, False if not found

        Raises:
            RuntimeError: If revocation fails
        """
        pass

    @abstractmethod
    async def revoke_tokens_for_user(self, user_id: str, client_id: str | None = None) -> int:
        """
        Revoke all tokens for a user, optionally filtered by client.

        Args:
            user_id: The user ID
            client_id: Optional client ID to filter tokens

        Returns:
            Number of tokens revoked

        Raises:
            RuntimeError: If revocation fails
        """
        pass

    @abstractmethod
    async def revoke_tokens_for_client(self, client_id: str) -> int:
        """
        Revoke all tokens for a client.

        Args:
            client_id: The client ID

        Returns:
            Number of tokens revoked

        Raises:
            RuntimeError: If revocation fails
        """
        pass

    @abstractmethod
    async def get_tokens_for_user(
        self, user_id: str, client_id: str | None = None, active_only: bool = True
    ) -> list[OAuth2AccessToken]:
        """
        Get access tokens for a user.

        Args:
            user_id: The user ID
            client_id: Optional client ID to filter tokens
            active_only: Whether to include only active tokens

        Returns:
            List of OAuth2AccessToken instances
        """
        pass

    @abstractmethod
    async def get_tokens_for_client(
        self, client_id: str, active_only: bool = True
    ) -> list[OAuth2AccessToken]:
        """
        Get access tokens for a client.

        Args:
            client_id: The client ID
            active_only: Whether to include only active tokens

        Returns:
            List of OAuth2AccessToken instances
        """
        pass

    @abstractmethod
    async def cleanup_expired_tokens(self, before: datetime | None = None) -> int:
        """
        Clean up expired tokens.

        Args:
            before: Clean up tokens expired before this time (defaults to now)

        Returns:
            Number of tokens cleaned up

        Raises:
            RuntimeError: If cleanup fails
        """
        pass

    @abstractmethod
    async def update_access_token(self, token: OAuth2AccessToken) -> None:
        """
        Update an access token.

        Args:
            token: The updated access token

        Raises:
            ValueError: If token doesn't exist or data is invalid
            RuntimeError: If update operation fails
        """
        pass

    @abstractmethod
    async def update_refresh_token(self, token: OAuth2RefreshToken) -> None:
        """
        Update a refresh token.

        Args:
            token: The updated refresh token

        Raises:
            ValueError: If token doesn't exist or data is invalid
            RuntimeError: If update operation fails
        """
        pass

    @abstractmethod
    async def mark_refresh_token_used(self, token: str) -> bool:
        """
        Mark a refresh token as used.

        Args:
            token: The refresh token value

        Returns:
            True if token was marked as used, False if not found

        Raises:
            RuntimeError: If operation fails
        """
        pass
