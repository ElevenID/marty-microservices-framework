"""Domain events for Pet Service."""

from dataclasses import dataclass
from typing import Any, Optional

from mmf.framework.events.enhanced_event_bus import BaseEvent, EventMetadata


class PetCreatedEvent(BaseEvent):
    """Event published when a new pet is created."""

    def __init__(
        self,
        pet_id: str,
        name: str,
        species: str,
        age: int,
        owner_id: Optional[str] = None,
        metadata: Optional[EventMetadata] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the event."""
        data = {
            "pet_id": pet_id,
            "name": name,
            "species": species,
            "age": age,
            "owner_id": owner_id,
        }
        super().__init__(
            event_type="pet_service.pet_created",
            data=data,
            metadata=metadata,
            **kwargs,
        )


class PetUpdatedEvent(BaseEvent):
    """Event published when a pet is updated."""

    def __init__(
        self,
        pet_id: str,
        name: str,
        species: str,
        age: int,
        owner_id: Optional[str] = None,
        metadata: Optional[EventMetadata] = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the event."""
        data = {
            "pet_id": pet_id,
            "name": name,
            "species": species,
            "age": age,
            "owner_id": owner_id,
        }
        super().__init__(
            event_type="pet_service.pet_updated",
            data=data,
            metadata=metadata,
            **kwargs,
        )
