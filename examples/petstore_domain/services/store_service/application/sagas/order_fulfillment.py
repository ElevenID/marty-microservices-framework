"""Order Fulfillment Saga.

This saga manages the distributed transaction of fulfilling an order,
which involves scheduling delivery and updating order status.
"""

import logging
from typing import Any

from examples.petstore_domain.services.store_service.application.ports.catalog_repository import (
    CatalogRepositoryPort,
)
from examples.petstore_domain.services.store_service.application.ports.delivery_service import (
    DeliveryRequest,
    DeliveryServicePort,
)
from examples.petstore_domain.services.store_service.application.ports.order_repository import (
    OrderRepositoryPort,
)
from examples.petstore_domain.services.store_service.domain.value_objects import (
    OrderStatus,
)
from mmf.framework.patterns.saga.orchestrator import SagaOrchestrator
from mmf.framework.patterns.saga.types import SagaStep

logger = logging.getLogger(__name__)


class OrderFulfillmentSaga:
    """Saga for order fulfillment."""

    def __init__(
        self,
        orchestrator: SagaOrchestrator,
        delivery_service: DeliveryServicePort,
        order_repository: OrderRepositoryPort,
        catalog_repository: CatalogRepositoryPort,
    ) -> None:
        """Initialize the saga."""
        self.orchestrator = orchestrator
        self.delivery_service = delivery_service
        self.order_repository = order_repository
        self.catalog_repository = catalog_repository

        # Register handlers
        self.orchestrator.register_step_handler("schedule_delivery", self._schedule_delivery)
        self.orchestrator.register_compensation_handler("schedule_delivery", self._cancel_delivery)

        self.orchestrator.register_step_handler("confirm_order", self._confirm_order)
        self.orchestrator.register_compensation_handler("confirm_order", self._fail_order)

    async def start(self, order_id: str, delivery_request: dict[str, Any]) -> str:
        """Start the order fulfillment saga."""
        steps = [
            SagaStep(
                step_id="step_1",
                step_name="schedule_delivery",
                service_name="delivery-board-service",
                action="schedule_delivery",
                compensation_action="cancel_delivery",
            ),
            SagaStep(
                step_id="step_2",
                step_name="confirm_order",
                service_name="store-service",
                action="confirm_order",
                compensation_action="fail_order",
            ),
        ]

        context = {
            "order_id": order_id,
            "delivery_request": delivery_request,
        }

        return await self.orchestrator.start_saga("order_fulfillment", steps, context)

    async def _schedule_delivery(self, context: dict[str, Any]) -> None:
        """Step: Schedule delivery."""
        req_data = context["delivery_request"]
        request = DeliveryRequest(
            order_id=req_data["order_id"],
            address=req_data["address"],
            items=req_data["items"],
            priority=req_data["priority"],
        )

        delivery_id = await self.delivery_service.create_delivery(request)
        if not delivery_id:
            raise Exception("Failed to schedule delivery")

        context["delivery_id"] = delivery_id
        logger.info(f"Scheduled delivery {delivery_id} for order {context['order_id']}")

    async def _cancel_delivery(self, context: dict[str, Any]) -> None:
        """Compensation: Cancel delivery."""
        # In a real app, we would call delivery_service.cancel_delivery(context["delivery_id"])
        logger.info(f"Compensating: Cancelling delivery for order {context['order_id']}")

    async def _confirm_order(self, context: dict[str, Any]) -> None:
        """Step: Confirm order."""
        order_id = context["order_id"]
        order = self.order_repository.find_by_id(order_id)
        if order:
            order.status = OrderStatus.CONFIRMED
            self.order_repository.save(order)
            logger.info(f"Confirmed order {order_id}")

    async def _fail_order(self, context: dict[str, Any]) -> None:
        """Compensation: Fail order and release stock."""
        order_id = context["order_id"]
        order = self.order_repository.find_by_id(order_id)
        if order:
            order.status = OrderStatus.CANCELLED
            self.order_repository.save(order)

            # Release stock
            catalog_item = self.catalog_repository.find_by_pet_id(order.pet_id)
            if catalog_item:
                catalog_item.quantity += order.quantity
                self.catalog_repository.save(catalog_item)

            logger.info(f"Compensating: Failed order {order_id} and released stock")
