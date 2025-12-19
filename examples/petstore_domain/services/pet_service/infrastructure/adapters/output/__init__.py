"""Driven adapters (Secondary/Output adapters) for Pet Service.

These adapters implement the output ports defined in the application layer,
handling persistence, external services, etc.
"""

from examples.petstore_domain.services.pet_service.infrastructure.adapters.output.in_memory_repository import (
    InMemoryPetRepository,
)

__all__ = ["InMemoryPetRepository"]
