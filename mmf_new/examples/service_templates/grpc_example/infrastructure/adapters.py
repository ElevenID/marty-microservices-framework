from mmf_new.examples.service_templates.grpc_example.domain.models import Order
from mmf_new.examples.service_templates.grpc_example.domain.ports import (
    InventoryServicePort,
    OrderRepository,
)
from mmf_new.framework.integration.adapters.rest_adapter import RESTAPIAdapter
from mmf_new.framework.integration.domain.models import IntegrationRequest


class InMemoryOrderRepository(OrderRepository):
    def __init__(self):
        self._orders: dict[str, Order] = {}

    async def save(self, order: Order) -> Order:
        self._orders[order.order_id] = order
        return order

    async def get_by_id(self, order_id: str) -> Order | None:
        return self._orders.get(order_id)


class ExternalInventoryAdapter(InventoryServicePort):
    def __init__(self, adapter: RESTAPIAdapter):
        self.adapter = adapter

    async def check_availability(self, product_id: str, quantity: int) -> bool:
        """Call external inventory system to check availability."""
        request = IntegrationRequest(
            system_id=self.adapter.config.system_id,
            operation="GET",
            data={"path": f"/inventory/{product_id}", "quantity": str(quantity)},
        )

        response = await self.adapter.execute_request(request)

        if not response.success:
            return False

        data = response.data
        if isinstance(data, dict):
            return bool(data.get("available", False))
        return False
