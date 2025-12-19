"""Driven adapters (Secondary/Output adapters) for Store Service."""

from examples.petstore_domain.services.store_service.infrastructure.adapters.output.in_memory_catalog_repository import (
    InMemoryCatalogRepository,
)
from examples.petstore_domain.services.store_service.infrastructure.adapters.output.in_memory_order_repository import (
    InMemoryOrderRepository,
)

__all__ = ["InMemoryCatalogRepository", "InMemoryOrderRepository"]
