"""Store Service - A bounded context for store and order management.

This service demonstrates Hexagonal Architecture (Ports and Adapters) following
the strict patterns defined in mmf/services/identity as the reference implementation.

Structure:
    domain/         Pure business logic (entities, value objects, exceptions)
    application/    Use cases and port definitions (interfaces)
    infrastructure/ Adapters implementing ports (API, repositories)
    di_config.py    Dependency injection wiring

Dependency Rule:
    Infrastructure -> Application -> Domain

Note:
    This is the Store's bounded context. It has its own concept of a "CatalogItem"
    which represents a pet for sale. This is NOT the same as the Pet entity from
    pet_service - each bounded context owns its own domain model.

Running:
    # Hexagonal Architecture version (in-memory, for demos)
    uvicorn examples.petstore_domain.services.store_service.main_hexagonal:app

    # Original version (with SQLModel, Dishka, Taskiq)
    uvicorn examples.petstore_domain.services.store_service.main:app
"""

from examples.petstore_domain.services.store_service.di_config import (
    StoreServiceDIContainer,
)

__all__ = ["StoreServiceDIContainer"]
