"""List Pets Use Case.

This use case handles retrieving all pets in the system.
"""

from dataclasses import dataclass
from typing import Optional

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)


@dataclass
class PaginationQuery:
    """Query parameters for pagination."""

    limit: int = 20
    offset: int = 0


@dataclass
class PetSummary:
    """Summary information for a pet in the list."""

    pet_id: str
    name: str
    species: str
    age: int
    owner_id: Optional[str]


@dataclass
class ListPetsResult:
    """Result of listing pets."""

    pets: list[PetSummary]
    total_count: int
    limit: int
    offset: int
    has_more: bool


class ListPetsUseCase:
    """Use case for listing all pets.

    This use case:
    1. Retrieves all pets from the repository
    2. Maps them to summary objects
    3. Returns the list with count and pagination info
    """

    def __init__(self, pet_repository: PetRepositoryPort) -> None:
        """Initialize the use case with required dependencies.

        Args:
            pet_repository: Port for pet persistence operations
        """
        self._pet_repository = pet_repository

    def execute(self, pagination: Optional[PaginationQuery] = None) -> ListPetsResult:
        """Execute the list pets use case.

        Args:
            pagination: Optional pagination parameters

        Returns:
            Result containing list of pet summaries, total count, and pagination info
        """
        if pagination is None:
            pagination = PaginationQuery()

        # Retrieve pets from repository with pagination
        pets, total_count = self._pet_repository.find_all(
            limit=pagination.limit, offset=pagination.offset
        )

        # Map to summaries
        summaries = [
            PetSummary(
                pet_id=str(pet.id),
                name=pet.name,
                species=pet.species.value,
                age=pet.age,
                owner_id=pet.owner_id,
            )
            for pet in pets
        ]

        has_more = (pagination.offset + len(summaries)) < total_count

        return ListPetsResult(
            pets=summaries,
            total_count=total_count,
            limit=pagination.limit,
            offset=pagination.offset,
            has_more=has_more,
        )
