"""Pet Service Domain Layer.

This module contains the core business logic for the Pet bounded context.
It has ZERO external dependencies - only standard library types are allowed.

Components:
- entities: Core domain entities (Pet)
- value_objects: Immutable value types (PetId, Species)
- exceptions: Domain-specific exceptions
"""

from examples.petstore_domain.services.pet_service.domain.entities import Pet
from examples.petstore_domain.services.pet_service.domain.value_objects import (
    PetId,
    Species,
)

__all__ = ["Pet", "PetId", "Species"]
