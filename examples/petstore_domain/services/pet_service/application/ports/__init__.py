"""Application layer ports (interfaces) for Pet Service."""

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)

__all__ = ["PetRepositoryPort"]
