"""Pet Repository Port (Interface).

This is an output port defining how the application layer expects to
interact with pet persistence. Infrastructure adapters must implement
this interface.
"""

from abc import ABC, abstractmethod
from typing import Optional

from examples.petstore_domain.services.pet_service.domain.entities import Pet
from examples.petstore_domain.services.pet_service.domain.value_objects import PetId


class PetRepositoryPort(ABC):
    """Abstract interface for pet persistence operations.

    This port defines the contract that any pet repository implementation
    must fulfill. The application layer depends only on this abstraction,
    not on concrete implementations.

    Implementations might include:
    - InMemoryPetRepository (for testing/demos)
    - SQLAlchemyPetRepository (for production)
    - RedisPetRepository (for caching layer)
    """

    @abstractmethod
    def save(self, pet: Pet) -> None:
        """Persist a pet entity.

        Args:
            pet: The pet entity to save

        Raises:
            DuplicatePetError: If a pet with the same ID already exists
        """
        pass

    @abstractmethod
    def find_by_id(self, pet_id: PetId) -> Optional[Pet]:
        """Find a pet by its unique identifier.

        Args:
            pet_id: The pet's unique identifier

        Returns:
            The pet if found, None otherwise
        """
        pass

    @abstractmethod
    def find_all(
        self, *, limit: int | None = None, offset: int = 0
    ) -> tuple[list[Pet], int]:
        """Retrieve all pets with optional pagination.

        Args:
            limit: Maximum number of pets to return (None for all)
            offset: Number of pets to skip

        Returns:
            Tuple of (list of pet entities, total count)
        """
        pass

    @abstractmethod
    def delete(self, pet_id: PetId) -> bool:
        """Delete a pet by its unique identifier.

        Args:
            pet_id: The pet's unique identifier

        Returns:
            True if the pet was deleted, False if not found
        """
        pass

    @abstractmethod
    def exists(self, pet_id: PetId) -> bool:
        """Check if a pet exists.

        Args:
            pet_id: The pet's unique identifier

        Returns:
            True if the pet exists, False otherwise
        """
        pass
