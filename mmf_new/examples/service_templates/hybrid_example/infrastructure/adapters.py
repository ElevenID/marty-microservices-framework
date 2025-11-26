from typing import Optional, Dict
from mmf_new.examples.service_templates.hybrid_example.domain.models import Order
from mmf_new.examples.service_templates.hybrid_example.domain.ports import OrderRepository, InventoryServicePort
from mmf_new.framework.integration.adapters.rest_adapter import RESTAPIAdapter
from mmf_new.framework.integration.domain.models import IntegrationRequest

class InMemoryOrderRepository(OrderRepository):
    def __init__(self):
        self._orders: Dict[str, Order] = {}

    async def save(self, order: Order) -> Order:
        self._orders[order.order_id] = order
        return order

    async def get_by_id(self, order_id: str) -> Optional[Order]:
        return self._orders.get(order_id)

    async def get_by_ids(self, order_ids: list[str]) -> list[Order]:
        """Get multiple orders by IDs."""
        return [order for order_id, order in self._orders.items() if order_id in order_ids]

class ExternalInventoryAdapter(InventoryServicePort):
    def __init__(self, adapter: RESTAPIAdapter):
        self.adapter = adapter

    async def check_availability(self, product_id: str, quantity: int) -> bool:
        """Call external inventory system to check availability."""
        request = IntegrationRequest(
            system_id=self.adapter.config.system_id,
            operation="GET",
            data={
                "path": f"/inventory/{product_id}",
                "quantity": str(quantity)
            }
        )
        
        response = await self.adapter.execute_request(request)
        
        if not response.success:
            return False
            
        data = response.data
        if isinstance(data, dict):
            return bool(data.get("available", False))
        return False