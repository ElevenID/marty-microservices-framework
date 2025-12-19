"""Driving adapters (Primary/Input adapters) for Store Service."""

from examples.petstore_domain.services.store_service.infrastructure.adapters.input.api import (
    create_store_router,
)

__all__ = ["create_store_router"]
