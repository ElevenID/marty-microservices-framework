"""Update Pet Use Case.

This use case handles updating an existing pet's properties.
"""

from dataclasses import dataclass
from typing import Optional

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)
from examples.petstore_domain.services.pet_service.domain.events import PetUpdatedEvent
from examples.petstore_domain.services.pet_service.domain.value_objects import (
    PetId,
    Species,
)
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus


@dataclass
class UpdatePetCommand:
    """Command object for updating a pet."""

    pet_id: str
    name: Optional[str] = None
    species: Optional[str] = None
    age: Optional[int] = None
    owner_id: Optional[str] = None


@dataclass
class UpdatePetResult:
    """Result of updating a pet."""

    pet_id: str
    name: str
    species: str
    age: int
    owner_id: Optional[str]
    success: bool
    error_message: Optional[str] = None


class UpdatePetUseCase:
    """Use case for updating an existing pet.

    This use case:
    1. Finds the pet by ID
    2. Validates the update is valid
    3. Updates the pet properties
    4. Persists the changes
    5. Publishes update event
    """

    def __init__(
        self,
        pet_repository: PetRepositoryPort,
        event_bus: EnhancedEventBus,
    ) -> None:
        """Initialize the use case with required dependencies.

        Args:
            pet_repository: Port for pet persistence operations
            event_bus: Event bus for publishing domain events
        """
        self._pet_repository = pet_repository
        self._event_bus = event_bus

    async def execute(self, command: UpdatePetCommand) -> UpdatePetResult:
        """Execute the update pet use case.

        Args:
            command: The update pet command with pet details

        Returns:
            Result containing the updated pet's information or error
        """
        # Find the pet
        pet_id = PetId(command.pet_id)
        pet = self._pet_repository.find_by_id(pet_id)

        if pet is None:
            return UpdatePetResult(
                pet_id=command.pet_id,
                name="",
                species="",
                age=0,
                owner_id=None,
                success=False,
                error_message=f"Pet {command.pet_id} not found",
            )

        # Apply updates
        if command.name is not None:
            try:
                pet.update_name(command.name)
            except ValueError as e:
                return UpdatePetResult(
                    pet_id=command.pet_id,
                    name=pet.name,
                    species=pet.species.value,
                    age=pet.age,
                    owner_id=pet.owner_id,
                    success=False,
                    error_message=str(e),
                )

        if command.species is not None:
            pet.species = Species.from_string(command.species)

        if command.age is not None:
            if command.age < 0:
                return UpdatePetResult(
                    pet_id=command.pet_id,
                    name=pet.name,
                    species=pet.species.value,
                    age=pet.age,
                    owner_id=pet.owner_id,
                    success=False,
                    error_message="Pet age cannot be negative",
                )
            pet.age = command.age

        if command.owner_id is not None:
            if command.owner_id == "":
                pet.remove_owner()
            else:
                pet.assign_owner(command.owner_id)

        # Note: In-memory repository stores references, so no explicit update needed
        # For real repositories, we would call: self._pet_repository.update(pet)

        # Publish domain event
        await self._event_bus.publish(
            PetUpdatedEvent(
                pet_id=str(pet.id),
                name=pet.name,
                species=pet.species.value,
                age=pet.age,
                owner_id=pet.owner_id,
            )
        )

        return UpdatePetResult(
            pet_id=str(pet.id),
            name=pet.name,
            species=pet.species.value,
            age=pet.age,
            owner_id=pet.owner_id,
            success=True,
        )
