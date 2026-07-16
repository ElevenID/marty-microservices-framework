"""Driving adapters (Primary/Input adapters) for Pet Service.

These adapters handle incoming requests and translate them into
application use case calls.
"""

from examples.petstore_domain.services.pet_service.infrastructure.adapters.input.api import (
    create_pet_router,
)

__all__ = ["create_pet_router"]
