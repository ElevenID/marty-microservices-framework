"""Domain exceptions for Pet Service.

These exceptions represent domain-specific error conditions.
They have no external dependencies.
"""


class PetDomainError(Exception):
    """Base exception for all Pet domain errors."""

    pass


class PetNotFoundError(PetDomainError):
    """Raised when a pet cannot be found."""

    def __init__(self, pet_id: str) -> None:
        self.pet_id = pet_id
        super().__init__(f"Pet with id '{pet_id}' not found")


class InvalidPetDataError(PetDomainError):
    """Raised when pet data validation fails."""

    pass


class DuplicatePetError(PetDomainError):
    """Raised when attempting to create a pet that already exists."""

    def __init__(self, pet_id: str) -> None:
        self.pet_id = pet_id
        super().__init__(f"Pet with id '{pet_id}' already exists")
