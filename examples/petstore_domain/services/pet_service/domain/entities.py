"""Domain entities for Pet Service.

Entities are objects with a distinct identity that persists over time.
They have no external dependencies - only standard library types and
domain value objects.
"""

from dataclasses import dataclass, field
from typing import Optional

from examples.petstore_domain.services.pet_service.domain.value_objects import (
    PetId,
    Species,
)


@dataclass
class Pet:
    """Core domain entity representing a pet in the system.

    Attributes:
        id: Unique identifier for the pet
        name: Pet's name
        species: Type of animal
        age: Pet's age in years
        owner_id: Optional reference to the owner (external bounded context)
    """

    id: PetId
    name: str
    species: Species
    age: int
    owner_id: Optional[str] = None

    def __post_init__(self) -> None:
        """Validate entity invariants."""
        if not self.name:
            msg = "Pet name cannot be empty"
            raise ValueError(msg)
        if self.age < 0:
            msg = "Pet age cannot be negative"
            raise ValueError(msg)

    def update_name(self, new_name: str) -> None:
        """Update the pet's name with validation."""
        if not new_name:
            msg = "Pet name cannot be empty"
            raise ValueError(msg)
        self.name = new_name

    def celebrate_birthday(self) -> None:
        """Increment the pet's age by one year."""
        self.age += 1

    def assign_owner(self, owner_id: str) -> None:
        """Assign an owner to this pet."""
        self.owner_id = owner_id

    def remove_owner(self) -> None:
        """Remove the owner from this pet."""
        self.owner_id = None
