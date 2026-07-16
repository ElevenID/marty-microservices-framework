"""
OAuth2 Client Store Port Interface.

This module defines the port interface for OAuth2 client persistence
and management operations.
"""

from abc import ABC, abstractmethod
from typing import Optional

from mmf.services.identity.domain.models.oauth2 import (
    OAuth2Client,
    OAuth2ClientRegistration,
)


class OAuth2ClientStore(ABC):
    """
    OAuth2 Client Store port interface.

    Defines the contract for OAuth2 client persistence operations
    including registration, retrieval, and management.
    """

    @abstractmethod
    async def save(self, client: OAuth2Client) -> None:
        """
        Save an OAuth2 client.

        Args:
            client: The OAuth2 client to save

        Raises:
            ValueError: If client data is invalid
            RuntimeError: If save operation fails
        """
        pass

    @abstractmethod
    async def get_by_id(self, client_id: str) -> OAuth2Client | None:
        """
        Retrieve a client by ID.

        Args:
            client_id: The client ID

        Returns:
            OAuth2Client if found, None otherwise
        """
        pass

    @abstractmethod
    async def get_by_name(self, client_name: str) -> list[OAuth2Client]:
        """
        Retrieve clients by name (may return multiple results).

        Args:
            client_name: The client name to search for

        Returns:
            List of matching OAuth2Client instances
        """
        pass

    @abstractmethod
    async def update(self, client: OAuth2Client) -> None:
        """
        Update an existing OAuth2 client.

        Args:
            client: The updated OAuth2 client

        Raises:
            ValueError: If client doesn't exist or data is invalid
            RuntimeError: If update operation fails
        """
        pass

    @abstractmethod
    async def delete(self, client_id: str) -> bool:
        """
        Delete a client by ID.

        Args:
            client_id: The client ID to delete

        Returns:
            True if client was deleted, False if not found

        Raises:
            RuntimeError: If delete operation fails
        """
        pass

    @abstractmethod
    async def list_clients(
        self, limit: int = 100, offset: int = 0, active_only: bool = True
    ) -> list[OAuth2Client]:
        """
        List OAuth2 clients with pagination.

        Args:
            limit: Maximum number of clients to return
            offset: Number of clients to skip
            active_only: Whether to include only active clients

        Returns:
            List of OAuth2Client instances
        """
        pass

    @abstractmethod
    async def exists(self, client_id: str) -> bool:
        """
        Check if a client exists.

        Args:
            client_id: The client ID to check

        Returns:
            True if client exists, False otherwise
        """
        pass

    @abstractmethod
    async def register_client(self, registration: OAuth2ClientRegistration) -> OAuth2Client:
        """
        Register a new OAuth2 client.

        Args:
            registration: The client registration request

        Returns:
            The newly created OAuth2Client

        Raises:
            ValueError: If registration data is invalid
            RuntimeError: If registration fails
        """
        pass

    @abstractmethod
    async def deactivate_client(self, client_id: str) -> bool:
        """
        Deactivate a client (soft delete).

        Args:
            client_id: The client ID to deactivate

        Returns:
            True if client was deactivated, False if not found

        Raises:
            RuntimeError: If deactivation fails
        """
        pass

    @abstractmethod
    async def activate_client(self, client_id: str) -> bool:
        """
        Activate a previously deactivated client.

        Args:
            client_id: The client ID to activate

        Returns:
            True if client was activated, False if not found

        Raises:
            RuntimeError: If activation fails
        """
        pass

    @abstractmethod
    async def regenerate_secret(self, client_id: str) -> OAuth2Client | None:
        """
        Regenerate the client secret for a confidential client.

        Args:
            client_id: The client ID

        Returns:
            Updated OAuth2Client with new secret, None if not found

        Raises:
            ValueError: If client is public (no secret)
            RuntimeError: If regeneration fails
        """
        pass
