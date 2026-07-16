"""Get Pet Use Case.

This use case handles retrieving a single pet by ID.
"""

from dataclasses import dataclass
from typing import Optional

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)
from examples.petstore_domain.services.pet_service.domain.exceptions import (
    PetNotFoundError,
)
from examples.petstore_domain.services.pet_service.domain.value_objects import PetId


@dataclass
class GetPetQuery:
    """Query object for retrieving a pet."""

    pet_id: str


@dataclass
class GetPetResult:
    """Result of retrieving a pet."""

    pet_id: str
    name: str
    species: str
    age: int
    owner_id: Optional[str]


class GetPetUseCase:
    """Use case for retrieving a pet by ID.

    This use case:
    1. Validates the pet ID
    2. Looks up the pet in the repository
    3. Returns the pet's details or raises an error
    """

    def __init__(self, pet_repository: PetRepositoryPort) -> None:
        """Initialize the use case with required dependencies.

        Args:
            pet_repository: Port for pet persistence operations
        """
        self._pet_repository = pet_repository

    def execute(self, query: GetPetQuery) -> GetPetResult:
        """Execute the get pet use case.

        Args:
            query: The query containing the pet ID

        Returns:
            Result containing the pet's information

        Raises:
            PetNotFoundError: If no pet exists with the given ID
            ValueError: If the pet ID is invalid
        """
        # Create value object (validates format)
        pet_id = PetId(value=query.pet_id)

        # Look up in repository
        pet = self._pet_repository.find_by_id(pet_id)

        if pet is None:
            raise PetNotFoundError(query.pet_id)

        # Return the result
        return GetPetResult(
            pet_id=str(pet.id),
            name=pet.name,
            species=pet.species.value,
            age=pet.age,
            owner_id=pet.owner_id,
        )
