from mmf.examples.service_templates.fastapi_example.domain.models import Order
from mmf.examples.service_templates.fastapi_example.domain.ports import (
    InventoryServicePort,
    OrderRepository,
)


class OrderService:
    def __init__(self, repo: OrderRepository, inventory: InventoryServicePort):
        self.repo = repo
        self.inventory = inventory

    async def create_order(self, order: Order) -> Order:
        """Create a new order if inventory allows."""
        # Check inventory for all items
        for item in order.items:
            available = await self.inventory.check_availability(item.product_id, item.quantity)
            if not available:
                raise ValueError(f"Product {item.product_id} is not available")

        # Calculate total
        order.calculate_total()

        # Save order
        return await self.repo.save(order)

    async def get_order(self, order_id: str) -> Order | None:
        """Get order by ID."""
        return await self.repo.get_by_id(order_id)
