"""Repository interfaces for the domain layer."""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar
from uuid import UUID

T = TypeVar("T")


class Repository(ABC, Generic[T]):
    """Base repository interface for data access operations.

    This interface defines the contract for all repository implementations
    in the hexagonal architecture. It's a port in the hexagonal architecture
    that will be implemented by adapters in the infrastructure layer.
    """

    @abstractmethod
    async def save(self, entity: T) -> T:
        """Save an entity to the repository.

        Args:
            entity: The entity to save

        Returns:
            The saved entity with any updated fields (e.g., generated ID)
        """
        ...

    @abstractmethod
    async def find_by_id(self, entity_id: UUID | str | int) -> T | None:
        """Find entity by its unique identifier.

        Args:
            entity_id: The unique identifier

        Returns:
            The entity if found, None otherwise
        """
        ...

    @abstractmethod
    async def find_all(self, skip: int = 0, limit: int = 100) -> list[T]:
        """Find all entities with pagination.

        Args:
            skip: Number of entities to skip
            limit: Maximum number of entities to return

        Returns:
            List of entities
        """
        ...

    @abstractmethod
    async def update(self, entity_id: UUID | str | int, updates: dict[str, Any]) -> T | None:
        """Update an entity.

        Args:
            entity_id: The unique identifier
            updates: Dictionary of fields to update

        Returns:
            The updated entity if found, None otherwise
        """
        ...

    @abstractmethod
    async def delete(self, entity_id: UUID | str | int) -> bool:
        """Delete an entity.

        Args:
            entity_id: The unique identifier

        Returns:
            True if deleted, False if not found
        """
        ...

    @abstractmethod
    async def exists(self, entity_id: UUID | str | int) -> bool:
        """Check if entity exists.

        Args:
            entity_id: The unique identifier

        Returns:
            True if exists, False otherwise
        """
        ...

    @abstractmethod
    async def count(self) -> int:
        """Count total entities.

        Returns:
            Total number of entities
        """
        ...


class DomainRepository(Repository[T]):
    """Domain-specific repository interface with additional methods."""

    @abstractmethod
    async def create(self, data: dict[str, Any]) -> T:
        """Create a new entity.

        Args:
            data: The creation data

        Returns:
            The created entity
        """
        ...

    @abstractmethod
    async def find_by_criteria(self, criteria: dict[str, Any]) -> list[T]:
        """Find entities by criteria.

        Args:
            criteria: Search criteria

        Returns:
            List of matching entities
        """
        ...

    @abstractmethod
    async def find_one_by_criteria(self, criteria: dict[str, Any]) -> T | None:
        """Find single entity by criteria.

        Args:
            criteria: Search criteria

        Returns:
            The matching entity if found, None otherwise
        """
        ...

    @abstractmethod
    async def find_with_pagination(
        self,
        criteria: dict[str, Any] | None = None,
        skip: int = 0,
        limit: int = 100,
        order_by: str | None = None,
        order_desc: bool = False,
    ) -> list[T]:
        """Find entities with advanced pagination and sorting.

        Args:
            criteria: Optional search criteria
            skip: Number of entities to skip
            limit: Maximum number of entities to return
            order_by: Field to order by
            order_desc: Whether to order in descending order

        Returns:
            List of matching entities
        """
        ...

    @abstractmethod
    async def count_by_criteria(self, criteria: dict[str, Any] | None = None) -> int:
        """Count entities matching criteria.

        Args:
            criteria: Optional search criteria

        Returns:
            Count of matching entities
        """
        ...

    @abstractmethod
    async def bulk_create(self, entities_data: list[dict[str, Any]]) -> list[T]:
        """Create multiple entities in bulk.

        Args:
            entities_data: List of entity creation data

        Returns:
            List of created entities
        """
        ...

    @abstractmethod
    async def bulk_update(self, updates: list[tuple[UUID | str | int, dict[str, Any]]]) -> list[T]:
        """Update multiple entities in bulk.

        Args:
            updates: List of (entity_id, updates) tuples

        Returns:
            List of updated entities
        """
        ...

    @abstractmethod
    async def bulk_delete(self, entity_ids: list[UUID | str | int]) -> int:
        """Delete multiple entities in bulk.

        Args:
            entity_ids: List of entity IDs to delete

        Returns:
            Number of entities deleted
        """
        ...


# Repository Error Classes
class RepositoryError(Exception):
    """Base repository error."""


class EntityNotFoundError(RepositoryError):
    """Entity not found error."""


class EntityConflictError(RepositoryError):
    """Entity conflict error (e.g., duplicate key)."""


class RepositoryValidationError(RepositoryError):
    """Repository validation error."""


class RepositoryConnectionError(RepositoryError):
    """Repository connection error."""


class RepositoryTransactionError(RepositoryError):
    """Repository transaction error."""
