"""In-Memory Pet Repository Adapter.

This is a driven (output) adapter that implements the PetRepositoryPort
interface using an in-memory dictionary. Suitable for testing and demos.
"""

from typing import Optional

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)
from examples.petstore_domain.services.pet_service.domain.entities import Pet
from examples.petstore_domain.services.pet_service.domain.exceptions import (
    DuplicatePetError,
)
from examples.petstore_domain.services.pet_service.domain.value_objects import PetId


class InMemoryPetRepository(PetRepositoryPort):
    """In-memory implementation of the pet repository.

    This adapter stores pets in a dictionary, making it ideal for:
    - Unit testing (fast, no external dependencies)
    - Demo applications
    - Development without database setup

    Note: Data is lost when the application restarts.
    """

    def __init__(self) -> None:
        """Initialize the in-memory storage."""
        self._storage: dict[str, Pet] = {}

    def save(self, pet: Pet) -> None:
        """Persist a pet entity to memory.

        Args:
            pet: The pet entity to save

        Raises:
            DuplicatePetError: If a pet with the same ID already exists
        """
        pet_id_str = str(pet.id)

        if pet_id_str in self._storage:
            raise DuplicatePetError(pet_id_str)

        self._storage[pet_id_str] = pet

    def find_by_id(self, pet_id: PetId) -> Optional[Pet]:
        """Find a pet by its unique identifier.

        Args:
            pet_id: The pet's unique identifier

        Returns:
            The pet if found, None otherwise
        """
        return self._storage.get(str(pet_id))

    def find_all(
        self, *, limit: int | None = None, offset: int = 0
    ) -> tuple[list[Pet], int]:
        """Retrieve all pets from memory with optional pagination.

        Args:
            limit: Maximum number of pets to return (None for all)
            offset: Number of pets to skip

        Returns:
            Tuple of (list of pet entities, total count)
        """
        all_pets = list(self._storage.values())
        total_count = len(all_pets)

        # Apply pagination
        if offset:
            all_pets = all_pets[offset:]
        if limit is not None:
            all_pets = all_pets[:limit]

        return all_pets, total_count

    def delete(self, pet_id: PetId) -> bool:
        """Delete a pet from memory.

        Args:
            pet_id: The pet's unique identifier

        Returns:
            True if the pet was deleted, False if not found
        """
        pet_id_str = str(pet_id)

        if pet_id_str not in self._storage:
            return False

        del self._storage[pet_id_str]
        return True

    def exists(self, pet_id: PetId) -> bool:
        """Check if a pet exists in memory.

        Args:
            pet_id: The pet's unique identifier

        Returns:
            True if the pet exists, False otherwise
        """
        return str(pet_id) in self._storage

    def clear(self) -> None:
        """Clear all pets from memory.

        Useful for testing scenarios.
        """
        self._storage.clear()

    def count(self) -> int:
        """Get the total number of pets in memory.

        Returns:
            Number of stored pets
        """
        return len(self._storage)
