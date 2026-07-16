"""Pet Service - A bounded context for pet management.

This service demonstrates Hexagonal Architecture (Ports and Adapters) following
the strict patterns defined in mmf/services/identity as the reference implementation.

Structure:
    domain/         Pure business logic (entities, value objects, exceptions)
    application/    Use cases and port definitions (interfaces)
    infrastructure/ Adapters implementing ports (API, repositories)
    di_config.py    Dependency injection wiring

Dependency Rule:
    Infrastructure -> Application -> Domain

Example:
    ```python
    from examples.petstore_domain.services.pet_service.di_config import PetServiceDIContainer
    from examples.petstore_domain.services.pet_service.infrastructure.adapters.input.api import (
        create_pet_router,
    )
    from fastapi import FastAPI

    # Initialize DI container
    container = PetServiceDIContainer()
    container.initialize()

    # Create FastAPI app with injected use cases
    app = FastAPI(title="Pet Service")
    router = create_pet_router(
        create_pet_use_case=container.create_pet_use_case,
        get_pet_use_case=container.get_pet_use_case,
        list_pets_use_case=container.list_pets_use_case,
        delete_pet_use_case=container.delete_pet_use_case,
    )
    app.include_router(router)
    ```
"""

from examples.petstore_domain.services.pet_service.di_config import (
    PetServiceDIContainer,
)

__all__ = ["PetServiceDIContainer"]
