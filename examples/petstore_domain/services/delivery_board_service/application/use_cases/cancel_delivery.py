"""Cancel Delivery Use Case.

This use case handles the cancellation of an existing delivery.
"""

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
from examples.petstore_domain.services.delivery_board_service.domain.events import (
    DeliveryCancelledEvent,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    DeliveryId,
    DeliveryStatus,
)
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus


@dataclass
class CancelDeliveryCommand:
    """Command object for cancelling a delivery."""

    delivery_id: str
    reason: str = ""


@dataclass
class CancelDeliveryResult:
    """Result of cancelling a delivery."""

    delivery_id: str
    order_id: str
    status: str
    cancelled: bool
    error_message: str | None = None


class CancelDeliveryUseCase:
    """Use case for cancelling an existing delivery.

    This use case:
    1. Finds the delivery by ID
    2. Validates it can be cancelled
    3. Updates the delivery status
    4. Frees up truck capacity
    5. Publishes cancellation event
    """

    def __init__(
        self,
        delivery_repository: DeliveryRepositoryPort,
        truck_repository: TruckRepositoryPort,
        event_bus: EnhancedEventBus,
    ) -> None:
        """Initialize the use case.

        Args:
            delivery_repository: Repository for accessing deliveries
            truck_repository: Repository for accessing trucks
            event_bus: Event bus for publishing domain events
        """
        self._delivery_repository = delivery_repository
        self._truck_repository = truck_repository
        self._event_bus = event_bus

    async def execute(self, command: CancelDeliveryCommand) -> CancelDeliveryResult:
        """Execute the use case.

        Args:
            command: Command containing delivery ID and cancellation reason

        Returns:
            Result containing the cancelled delivery details or error
        """
        # Find delivery
        delivery_id = DeliveryId(command.delivery_id)
        delivery = self._delivery_repository.find_by_id(delivery_id)

        if delivery is None:
            return CancelDeliveryResult(
                delivery_id=command.delivery_id,
                order_id="",
                status="",
                cancelled=False,
                error_message=f"Delivery {command.delivery_id} not found",
            )

        # Check if delivery can be cancelled
        if not delivery.status.can_transition_to(DeliveryStatus.CANCELLED):
            return CancelDeliveryResult(
                delivery_id=command.delivery_id,
                order_id=delivery.order_id,
                status=delivery.status.value,
                cancelled=False,
                error_message=f"Cannot cancel delivery in status {delivery.status.value}",
            )

        # Cancel the delivery
        delivery.cancel()
        self._delivery_repository.update(delivery)

        # Free up truck capacity
        truck = self._truck_repository.find_by_id(delivery.truck_id)
        if truck is not None:
            truck.complete_delivery()
            self._truck_repository.update(truck)

        # Publish domain event
        await self._event_bus.publish(
            DeliveryCancelledEvent(
                delivery_id=str(delivery.id),
                order_id=delivery.order_id,
                reason=command.reason,
            )
        )

        return CancelDeliveryResult(
            delivery_id=str(delivery.id),
            order_id=delivery.order_id,
            status=delivery.status.value,
            cancelled=True,
        )
