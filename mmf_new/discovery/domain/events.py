"""
Service Discovery Events

Events related to service registration, deregistration, and health changes.
"""

import builtins
import time
import uuid
from typing import Any

from mmf_new.discovery.domain.models import ServiceInstance


class ServiceEvent:
    """Service registry event."""

    def __init__(
        self,
        event_type: str,
        service_name: str,
        instance_id: str,
        instance: ServiceInstance | None = None,
        timestamp: float | None = None,
    ):
        self.event_type = event_type  # register, deregister, health_change, etc.
        self.service_name = service_name
        self.instance_id = instance_id
        self.instance = instance
        self.timestamp = timestamp or time.time()
        self.event_id = str(uuid.uuid4())

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "service_name": self.service_name,
            "instance_id": self.instance_id,
            "instance": self.instance.to_dict() if self.instance else None,
            "timestamp": self.timestamp,
        }
