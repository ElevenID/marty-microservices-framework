"""Application layer ports (interfaces) for Delivery Board Service."""

from examples.petstore_domain.services.delivery_board_service.application.ports.delivery_repository import (
    DeliveryRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.application.ports.truck_repository import (
    TruckRepositoryPort,
)

__all__ = ["DeliveryRepositoryPort", "TruckRepositoryPort"]
