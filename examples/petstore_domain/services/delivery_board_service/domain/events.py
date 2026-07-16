"""Domain events for Delivery Board Service."""

from dataclasses import dataclass
from typing import Any, List, Optional

from mmf.framework.events.enhanced_event_bus import BaseEvent, EventMetadata


class DeliveryScheduledEvent(BaseEvent):
    """Event published when a delivery is scheduled."""

    def __init__(
        self,
        delivery_id: str,
        order_id: str,
        truck_id: str,
        items: List[dict[str, Any]],
        destination: str,
        metadata: Optional[EventMetadata] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the event."""
        data = {
            "delivery_id": delivery_id,
            "order_id": order_id,
            "truck_id": truck_id,
            "items": items,
            "destination": destination,
        }
        super().__init__(
            event_type="delivery_service.delivery_scheduled",
            data=data,
            metadata=metadata,
            **kwargs,
        )


class DeliveryCancelledEvent(BaseEvent):
    """Event published when a delivery is cancelled."""

    def __init__(
        self,
        delivery_id: str,
        order_id: str,
        reason: str = "",
        metadata: Optional[EventMetadata] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the event."""
        data = {
            "delivery_id": delivery_id,
            "order_id": order_id,
            "reason": reason,
        }
        super().__init__(
            event_type="delivery_service.delivery_cancelled",
            data=data,
            metadata=metadata,
            **kwargs,
        )
