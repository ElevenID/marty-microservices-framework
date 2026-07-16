"""Store Service Application Layer.

This module contains use cases and port definitions for the Store bounded context.
It depends only on the Domain layer and defines interfaces (Ports) that the
Infrastructure layer must implement.

Components:
- ports: Interface definitions (ABC) for infrastructure adapters
- use_cases: Application services orchestrating domain logic
"""

from examples.petstore_domain.services.store_service.application.ports.catalog_repository import (
    CatalogRepositoryPort,
)
from examples.petstore_domain.services.store_service.application.ports.order_repository import (
    OrderRepositoryPort,
)
from examples.petstore_domain.services.store_service.application.use_cases.create_order import (
    CreateOrderUseCase,
)
from examples.petstore_domain.services.store_service.application.use_cases.get_catalog import (
    GetCatalogUseCase,
)
from examples.petstore_domain.services.store_service.application.use_cases.get_order import (
    GetOrderUseCase,
)

__all__ = [
    "CatalogRepositoryPort",
    "OrderRepositoryPort",
    "CreateOrderUseCase",
    "GetCatalogUseCase",
    "GetOrderUseCase",
]
