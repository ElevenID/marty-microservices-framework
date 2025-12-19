"""Domain value objects for Pet Service.

Value objects are immutable and defined by their attributes rather than identity.
They have no external dependencies - only standard library types.
"""

import uuid
from dataclasses import dataclass
from enum import Enum
from typing import Self


class Species(str, Enum):
    """Valid pet species in the system."""

    DOG = "dog"
    CAT = "cat"
    BIRD = "bird"
    FISH = "fish"
    REPTILE = "reptile"
    OTHER = "other"

    @classmethod
    def from_string(cls, value: str) -> Self:
        """Create Species from string, defaulting to OTHER if unknown."""
        try:
            return cls(value.lower())
        except ValueError:
            return cls.OTHER


@dataclass(frozen=True)
class PetId:
    """Unique identifier for a Pet.

    This is a value object wrapping the raw ID to provide type safety
    and domain-specific validation.
    """

    value: str

    def __post_init__(self) -> None:
        """Validate the ID format."""
        if not self.value:
            msg = "PetId cannot be empty"
            raise ValueError(msg)

    @classmethod
    def generate(cls) -> Self:
        """Generate a new unique PetId."""
        return cls(value=str(uuid.uuid4()))

    def __str__(self) -> str:
        return self.value
