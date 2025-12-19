"""Delivery Board Service - A bounded context for delivery management.

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
    This is the Delivery bounded context. It has its own concepts of Delivery
    and Truck which are NOT shared with other services - each bounded context
    owns its own domain model.

Running:
    # Hexagonal Architecture version (in-memory, for demos)
    uvicorn examples.petstore_domain.services.delivery_board_service.main_hexagonal:app

    # Original version
    uvicorn examples.petstore_domain.services.delivery_board_service.main:app
"""

from examples.petstore_domain.services.delivery_board_service.di_config import (
    DeliveryBoardDIContainer,
)

__all__ = ["DeliveryBoardDIContainer"]
