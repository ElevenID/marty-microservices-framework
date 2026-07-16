"""Create Pet Use Case.

This use case handles the creation of new pets in the system.
"""

from dataclasses import dataclass
from typing import Optional

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)
from examples.petstore_domain.services.pet_service.domain.entities import Pet
from examples.petstore_domain.services.pet_service.domain.events import PetCreatedEvent
from examples.petstore_domain.services.pet_service.domain.value_objects import (
    PetId,
    Species,
)
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus


@dataclass
class CreatePetCommand:
    """Command object for creating a pet."""

    name: str
    species: str
    age: int
    owner_id: Optional[str] = None


@dataclass
class CreatePetResult:
    """Result of creating a pet."""

    pet_id: str
    name: str
    species: str
    age: int
    owner_id: Optional[str]


class CreatePetUseCase:
    """Use case for creating a new pet.

    This use case:
    1. Validates the input command
    2. Creates a new Pet domain entity
    3. Persists it via the repository port
    4. Returns the created pet's details
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

    async def execute(self, command: CreatePetCommand) -> CreatePetResult:
        """Execute the create pet use case.

        Args:
            command: The create pet command with pet details

        Returns:
            Result containing the created pet's information

        Raises:
            ValueError: If the command data is invalid
        """
        # Generate a new unique ID
        pet_id = PetId.generate()

        # Convert species string to domain value object
        species = Species.from_string(command.species)

        # Create the domain entity (validation happens in __post_init__)
        pet = Pet(
            id=pet_id,
            name=command.name,
            species=species,
            age=command.age,
            owner_id=command.owner_id,
        )

        # Persist via the repository port
        self._pet_repository.save(pet)

        # Publish domain event
        event = PetCreatedEvent(
            pet_id=str(pet.id),
            name=pet.name,
            species=pet.species.value,
            age=pet.age,
            owner_id=pet.owner_id,
        )
        await self._event_bus.publish(event)

        # Return the result
        return CreatePetResult(
            pet_id=str(pet.id),
            name=pet.name,
            species=pet.species.value,
            age=pet.age,
            owner_id=pet.owner_id,
        )
