"""Use case for completing a delivery."""

import logging
from dataclasses import dataclass

from examples.petstore_domain.services.delivery_board_service.application.ports.delivery_repository import (
    DeliveryRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.application.ports.truck_repository import (
    TruckRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Delivery,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    DeliveryId,
    DeliveryStatus,
)


@dataclass(frozen=True)
class CompleteDeliveryResult:
    """Result of completing a delivery."""

    delivery: Delivery | None
    success: bool
    error_message: str | None = None


class CompleteDeliveryUseCase:
    """Use case for completing a delivery."""

    def __init__(
        self,
        delivery_repository: DeliveryRepositoryPort,
        truck_repository: TruckRepositoryPort,
    ) -> None:
        """Initialize the use case.

        Args:
            delivery_repository: Repository for accessing deliveries
            truck_repository: Repository for accessing trucks
        """
        self._delivery_repository = delivery_repository
        self._truck_repository = truck_repository

    async def execute(self, delivery_id: str) -> CompleteDeliveryResult:
        """Execute the use case.

        Args:
            delivery_id: ID of the delivery to complete

        Returns:
            Result containing the updated delivery or error details
        """
        try:
            # Convert string ID to value object
            id_vo = DeliveryId(delivery_id)

            # Find delivery
            delivery = self._delivery_repository.find_by_id(id_vo)
            if not delivery:
                return CompleteDeliveryResult(
                    delivery=None,
                    success=False,
                    error_message=f"Delivery {delivery_id} not found",
                )

            # Update delivery status - fast forward if needed for demo
            if delivery.status == DeliveryStatus.QUEUED:
                # Skip ASSIGNED as it's already assigned to a truck in CreateDeliveryUseCase
                # But domain logic requires transitions
                delivery.status = DeliveryStatus.ASSIGNED
                delivery.start_transit()
                delivery.complete()
            elif delivery.status == DeliveryStatus.ASSIGNED:
                delivery.start_transit()
                delivery.complete()
            elif delivery.status == DeliveryStatus.IN_TRANSIT:
                delivery.complete()
            else:
                # Try to complete directly (will raise if invalid)
                delivery.complete()

            # Find associated truck and update its load
            truck = self._truck_repository.find_by_id(delivery.truck_id)
            if truck:
                truck.complete_delivery()
                self._truck_repository.save(truck)

            # Save updated delivery
            self._delivery_repository.save(delivery)

            return CompleteDeliveryResult(
                delivery=delivery,
                success=True,
            )

        except ValueError as e:
            return CompleteDeliveryResult(
                delivery=None,
                success=False,
                error_message=str(e),
            )
        except Exception as e:
            return CompleteDeliveryResult(
                delivery=None,
                success=False,
                error_message=f"Unexpected error: {e}",
            )
