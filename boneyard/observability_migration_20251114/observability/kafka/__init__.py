"""
Kafka infrastructure for Marty Microservices Framework

Note: Kafka functionality has been integrated into the enhanced event bus.
Please use marty_msf.framework.events.enhanced_event_bus instead.
"""

# Re-export from enhanced event bus for backward compatibility
from marty_msf.framework.events.enhanced_event_bus import EnhancedEventBus as EventBus
from marty_msf.framework.events.enhanced_event_bus import (
    KafkaConfig,
)
from marty_msf.framework.events.enhanced_event_bus import (
    enhanced_event_bus_context as event_bus_context,
)

# Deprecated exports - use enhanced event bus directly
__all__ = [
    "EventBus",  # Now points to EnhancedEventBus
    "KafkaConfig",
    "event_bus_context",
]
