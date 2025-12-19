"""Pet Service Application Layer.

This module contains use cases and port definitions for the Pet bounded context.
It depends only on the Domain layer and defines interfaces (Ports) that the
Infrastructure layer must implement.

Components:
- ports: Interface definitions (ABC) for infrastructure adapters
- use_cases: Application services orchestrating domain logic
"""

from examples.petstore_domain.services.pet_service.application.ports.pet_repository import (
    PetRepositoryPort,
)
from examples.petstore_domain.services.pet_service.application.use_cases.create_pet import (
    CreatePetUseCase,
)
from examples.petstore_domain.services.pet_service.application.use_cases.delete_pet import (
    DeletePetUseCase,
)
from examples.petstore_domain.services.pet_service.application.use_cases.get_pet import (
    GetPetUseCase,
)
from examples.petstore_domain.services.pet_service.application.use_cases.list_pets import (
    ListPetsUseCase,
)

__all__ = [
    "PetRepositoryPort",
    "CreatePetUseCase",
    "GetPetUseCase",
    "ListPetsUseCase",
    "DeletePetUseCase",
]
