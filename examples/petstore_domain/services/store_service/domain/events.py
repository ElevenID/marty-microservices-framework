"""Domain events for Store Service."""

from dataclasses import dataclass
from typing import Any, List, Optional

from mmf.framework.events.enhanced_event_bus import BaseEvent, EventMetadata


class OrderPlacedEvent(BaseEvent):
    """Event published when a new order is placed."""

    def __init__(
        self,
        order_id: str,
        customer_id: str,
        items: List[dict[str, Any]],
        total_amount: float,
        currency: str,
        metadata: Optional[EventMetadata] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the event."""
        data = {
            "order_id": order_id,
            "customer_id": customer_id,
            "items": items,
            "total_amount": total_amount,
            "currency": currency,
        }
        super().__init__(
            event_type="store_service.order_placed",
            data=data,
            metadata=metadata,
            **kwargs,
        )
