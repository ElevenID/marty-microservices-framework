"""
OAuth2 Authorization Store Port Interface.

This module defines the port interface for OAuth2 authorization
persistence and management operations.
"""

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Optional

from mmf.services.identity.domain.models.oauth2 import OAuth2Authorization


class OAuth2AuthorizationStore(ABC):
    """
    OAuth2 Authorization Store port interface.

    Defines the contract for OAuth2 authorization persistence operations
    including storage, retrieval, and lifecycle management.
    """

    @abstractmethod
    async def save(self, authorization: OAuth2Authorization) -> None:
        """
        Save an OAuth2 authorization.

        Args:
            authorization: The authorization to save

        Raises:
            ValueError: If authorization data is invalid
            RuntimeError: If save operation fails
        """
        pass

    @abstractmethod
    async def get_by_code(self, code: str) -> OAuth2Authorization | None:
        """
        Retrieve an authorization by code.

        Args:
            code: The authorization code

        Returns:
            OAuth2Authorization if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_id(self, authorization_id: str) -> OAuth2Authorization | None:
        """
        Retrieve an authorization by ID.

        Args:
            authorization_id: The authorization ID

        Returns:
            OAuth2Authorization if found, None otherwise
        """
        pass

    @abstractmethod
    async def update(self, authorization: OAuth2Authorization) -> None:
        """
        Update an authorization.

        Args:
            authorization: The updated authorization

        Raises:
            ValueError: If authorization doesn't exist or data is invalid
            RuntimeError: If update operation fails
        """
        pass

    @abstractmethod
    async def mark_used(self, code: str) -> bool:
        """
        Mark an authorization as used.

        Args:
            code: The authorization code

        Returns:
            True if authorization was marked as used, False if not found

        Raises:
            RuntimeError: If operation fails
        """
        pass

    @abstractmethod
    async def delete(self, authorization_id: str) -> bool:
        """
        Delete an authorization.

        Args:
            authorization_id: The authorization ID

        Returns:
            True if authorization was deleted, False if not found

        Raises:
            RuntimeError: If delete operation fails
        """
        pass

    @abstractmethod
    async def get_authorizations_for_user(
        self, user_id: str, client_id: str | None = None, active_only: bool = True
    ) -> list[OAuth2Authorization]:
        """
        Get authorizations for a user.

        Args:
            user_id: The user ID
            client_id: Optional client ID to filter authorizations
            active_only: Whether to include only active (unused, unexpired) authorizations

        Returns:
            List of OAuth2Authorization instances
        """
        pass

    @abstractmethod
    async def get_authorizations_for_client(
        self, client_id: str, active_only: bool = True
    ) -> list[OAuth2Authorization]:
        """
        Get authorizations for a client.

        Args:
            client_id: The client ID
            active_only: Whether to include only active authorizations

        Returns:
            List of OAuth2Authorization instances
        """
        pass

    @abstractmethod
    async def cleanup_expired_authorizations(self, before: datetime | None = None) -> int:
        """
        Clean up expired authorizations.

        Args:
            before: Clean up authorizations expired before this time (defaults to now)

        Returns:
            Number of authorizations cleaned up

        Raises:
            RuntimeError: If cleanup fails
        """
        pass

    @abstractmethod
    async def revoke_authorizations_for_user(
        self, user_id: str, client_id: str | None = None
    ) -> int:
        """
        Revoke (delete) all authorizations for a user.

        Args:
            user_id: The user ID
            client_id: Optional client ID to filter authorizations

        Returns:
            Number of authorizations revoked

        Raises:
            RuntimeError: If revocation fails
        """
        pass

    @abstractmethod
    async def revoke_authorizations_for_client(self, client_id: str) -> int:
        """
        Revoke (delete) all authorizations for a client.

        Args:
            client_id: The client ID

        Returns:
            Number of authorizations revoked

        Raises:
            RuntimeError: If revocation fails
        """
        pass
