"""Application layer ports (interfaces) for Store Service."""

from examples.petstore_domain.services.store_service.application.ports.catalog_repository import (
    CatalogRepositoryPort,
)
from examples.petstore_domain.services.store_service.application.ports.order_repository import (
    OrderRepositoryPort,
)

__all__ = ["CatalogRepositoryPort", "OrderRepositoryPort"]
