"""Create Order Use Case.

This use case handles the creation of new orders in the system.
"""

from dataclasses import dataclass
from typing import Optional

from examples.petstore_domain.services.store_service.application.ports.catalog_repository import (
    CatalogRepositoryPort,
)
from examples.petstore_domain.services.store_service.application.ports.order_repository import (
    OrderRepositoryPort,
)
from examples.petstore_domain.services.store_service.domain.entities import Order
from examples.petstore_domain.services.store_service.domain.events import (
    OrderPlacedEvent,
)
from examples.petstore_domain.services.store_service.domain.exceptions import (
    CatalogItemNotFoundError,
    InsufficientStockError,
)
from examples.petstore_domain.services.store_service.domain.value_objects import (
    OrderId,
    OrderStatus,
)
from mmf.framework.events.enhanced_event_bus import EnhancedEventBus


@dataclass
class CreateOrderCommand:
    """Command object for creating an order."""

    pet_id: str
    quantity: int
    customer_name: str
    delivery_address: Optional[str] = None
    delivery_requested: bool = True


@dataclass
class CreateOrderResult:
    """Result of creating an order."""

    order_id: str
    pet_id: str
    quantity: int
    customer_name: str
    status: str
    total_price: float
    delivery_requested: bool


class CreateOrderUseCase:
    """Use case for creating a new order.

    This use case:
    1. Validates the catalog item exists and has stock
    2. Creates a new Order domain entity
    3. Reduces catalog stock
    4. Persists the order
    5. Publishes an OrderPlacedEvent
    6. Returns the created order's details
    """

    def __init__(
        self,
        catalog_repository: CatalogRepositoryPort,
        order_repository: OrderRepositoryPort,
        event_bus: EnhancedEventBus,
    ) -> None:
        """Initialize the use case with required dependencies.

        Args:
            catalog_repository: Port for catalog persistence operations
            order_repository: Port for order persistence operations
            event_bus: Event bus for publishing domain events
        """
        self._catalog_repository = catalog_repository
        self._order_repository = order_repository
        self._event_bus = event_bus

    async def execute(self, command: CreateOrderCommand) -> CreateOrderResult:
        """Execute the create order use case.

        Args:
            command: The create order command with order details

        Returns:
            Result containing the created order's information

        Raises:
            CatalogItemNotFoundError: If the pet_id is not in catalog
            InsufficientStockError: If there's not enough stock
        """
        # Find the catalog item
        catalog_item = self._catalog_repository.find_by_pet_id(command.pet_id)
        if catalog_item is None:
            raise CatalogItemNotFoundError(command.pet_id)

        # Check stock
        if catalog_item.quantity < command.quantity:
            raise InsufficientStockError(
                command.pet_id, command.quantity, catalog_item.quantity
            )

        # Calculate total price
        total_price = catalog_item.price * command.quantity

        # Generate order ID
        order_id = OrderId.generate()

        # Create the order
        order = Order(
            id=order_id,
            pet_id=command.pet_id,
            quantity=command.quantity,
            customer_name=command.customer_name,
            status=OrderStatus.PENDING,
            total_price=total_price,
            delivery_requested=command.delivery_requested,
            delivery_address=command.delivery_address,
        )

        # Reduce stock
        catalog_item.reduce_stock(command.quantity)
        self._catalog_repository.update(catalog_item)

        # Save order
        self._order_repository.save(order)

        # Publish OrderPlacedEvent
        event = OrderPlacedEvent(
            order_id=str(order.id),
            customer_id=order.customer_name,  # Using name as ID for simplicity
            items=[
                {
                    "pet_id": order.pet_id,
                    "quantity": order.quantity,
                    "description": f"{catalog_item.name} ({catalog_item.species})",
                }
            ],
            total_amount=order.total_price.to_float(),
            currency=order.total_price.currency,
            delivery_requested=order.delivery_requested,
            delivery_address=order.delivery_address,
        )
        await self._event_bus.publish(event)

        return CreateOrderResult(
            order_id=str(order.id),
            pet_id=order.pet_id,
            quantity=order.quantity,
            customer_name=order.customer_name,
            status=order.status.value,
            total_price=order.total_price.to_float(),
            delivery_requested=order.delivery_requested,
        )
