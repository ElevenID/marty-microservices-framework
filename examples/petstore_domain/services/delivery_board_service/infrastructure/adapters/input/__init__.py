"""Driving adapters (Primary/Input adapters) for Delivery Board Service."""

from examples.petstore_domain.services.delivery_board_service.infrastructure.adapters.input.api import (
    create_delivery_router,
)

__all__ = ["create_delivery_router"]
