"""Delete Pet Use Case.

This use case handles removing a pet from the system.
"""

from dataclasses import dataclass

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)
from examples.petstore_domain.services.pet_service.domain.exceptions import (
    PetNotFoundError,
)
from examples.petstore_domain.services.pet_service.domain.value_objects import PetId


@dataclass
class DeletePetCommand:
    """Command object for deleting a pet."""

    pet_id: str


@dataclass
class DeletePetResult:
    """Result of deleting a pet."""

    success: bool
    pet_id: str


class DeletePetUseCase:
    """Use case for deleting a pet.

    This use case:
    1. Validates the pet ID exists
    2. Deletes the pet from the repository
    3. Returns success status
    """

    def __init__(self, pet_repository: PetRepositoryPort) -> None:
        """Initialize the use case with required dependencies.

        Args:
            pet_repository: Port for pet persistence operations
        """
        self._pet_repository = pet_repository

    def execute(self, command: DeletePetCommand) -> DeletePetResult:
        """Execute the delete pet use case.

        Args:
            command: The delete pet command with pet ID

        Returns:
            Result indicating success

        Raises:
            PetNotFoundError: If no pet exists with the given ID
            ValueError: If the pet ID is invalid
        """
        # Create value object (validates format)
        pet_id = PetId(value=command.pet_id)

        # Check existence and delete
        deleted = self._pet_repository.delete(pet_id)

        if not deleted:
            raise PetNotFoundError(command.pet_id)

        return DeletePetResult(
            success=True,
            pet_id=command.pet_id,
        )
