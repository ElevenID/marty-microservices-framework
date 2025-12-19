"""Create Delivery Use Case.

This use case handles the creation of new deliveries with truck assignment.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from examples.petstore_domain.services.delivery_board_service.application.ports.delivery_repository import (
    DeliveryRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.application.ports.truck_repository import (
    TruckRepositoryPort,
)
from examples.petstore_domain.services.delivery_board_service.domain.entities import (
    Delivery,
    DeliveryItem,
    Truck,
)
from examples.petstore_domain.services.delivery_board_service.domain.events import (
    DeliveryScheduledEvent,
)
from examples.petstore_domain.services.delivery_board_service.domain.exceptions import (
    NoAvailableTruckError,
)
from examples.petstore_domain.services.delivery_board_service.domain.value_objects import (
    DeliveryId,
    DeliveryStatus,
    TruckId,
)
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus

if TYPE_CHECKING:
    from examples.petstore_domain.services.delivery_board_service.infrastructure.metrics import (
        DeliveryMetrics,
    )


@dataclass
class DeliveryItemCommand:
    """Item in a delivery request."""

    description: str
    quantity: int = 1


@dataclass
class CreateDeliveryCommand:
    """Command object for creating a delivery."""

    order_id: str
    address: str
    items: list[DeliveryItemCommand]
    priority: str = "standard"


@dataclass
class CreateDeliveryResult:
    """Result of creating a delivery."""

    delivery_id: str
    order_id: str
    truck_id: str
    status: str
    eta_minutes: int
    priority: str


class CreateDeliveryUseCase:
    """Use case for creating a new delivery.

    This use case:
    1. Finds an available truck (or auto-scales one)
    2. Assigns the delivery to the truck
    3. Creates the delivery entity
    4. Persists everything
    """

    def __init__(
        self,
        delivery_repository: DeliveryRepositoryPort,
        truck_repository: TruckRepositoryPort,
        event_bus: EnhancedEventBus,
        metrics: "DeliveryMetrics | None" = None,
    ) -> None:
        """Initialize the use case with required dependencies."""
        self._delivery_repository = delivery_repository
        self._truck_repository = truck_repository
        self._event_bus = event_bus
        self._metrics = metrics

    def _find_or_create_truck(self) -> Truck:
        """Find an available truck or auto-scale a new one."""
        available_trucks = self._truck_repository.find_available()

        if available_trucks:
            # Return the truck with lowest current load
            return min(available_trucks, key=lambda t: t.current_load)

        # Auto-scale: create a new truck
        all_trucks = self._truck_repository.find_all()
        truck_id = TruckId.generate()
        truck = Truck(
            id=truck_id,
            name=f"Surge Truck {len(all_trucks) + 1}",
            capacity=5,
            current_load=0,
            auto_scaled=True,
        )
        self._truck_repository.save(truck)
        return truck

    async def execute(self, command: CreateDeliveryCommand) -> CreateDeliveryResult:
        """Execute the create delivery use case.

        Args:
            command: The create delivery command with delivery details

        Returns:
            Result containing the created delivery's information

        Raises:
            NoAvailableTruckError: If no truck can be assigned
        """
        # Find or create a truck
        truck = self._find_or_create_truck()

        # Assign delivery to truck
        truck.assign_delivery()
        self._truck_repository.update(truck)

        # Calculate ETA based on truck load
        eta_minutes = 30 + truck.current_load * 5

        # Create delivery items
        items = [
            DeliveryItem(description=item.description, quantity=item.quantity)
            for item in command.items
        ]

        # Generate delivery ID
        delivery_id = DeliveryId.generate()

        # Create the delivery
        delivery = Delivery(
            id=delivery_id,
            order_id=command.order_id,
            address=command.address,
            items=items,
            status=DeliveryStatus.QUEUED,
            truck_id=truck.id,
            eta_minutes=eta_minutes,
            priority=command.priority,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )

        # Save delivery
        self._delivery_repository.save(delivery)

        # Record metrics
        if self._metrics:
            self._metrics.record_delivery_created(priority=command.priority)
            self._metrics.record_truck_assignment(truck_id=str(truck.id))

        # Publish DeliveryScheduledEvent
        event = DeliveryScheduledEvent(
            delivery_id=str(delivery.id),
            order_id=delivery.order_id,
            truck_id=str(delivery.truck_id),
            items=[
                {"description": item.description, "quantity": item.quantity}
                for item in delivery.items
            ],
            destination=delivery.address,
        )
        await self._event_bus.publish(event)

        return CreateDeliveryResult(
            delivery_id=str(delivery.id),
            order_id=delivery.order_id,
            truck_id=str(delivery.truck_id),
            status=delivery.status.value,
            eta_minutes=delivery.eta_minutes,
            priority=delivery.priority,
        )
