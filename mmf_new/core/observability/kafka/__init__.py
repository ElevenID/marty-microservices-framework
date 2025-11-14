"""
Kafka infrastructure for Marty Microservices Framework

Note: Kafka functionality has been integrated into the enhanced event bus.
This module is a placeholder until the event bus is migrated to mmf_new.

TODO: Restore these imports once mmf_new.core.events is migrated
"""

# TODO: Re-enable once event bus is migrated
# from mmf_new.core.events.enhanced_event_bus import EnhancedEventBus as EventBus
# from mmf_new.core.events.enhanced_event_bus import (
#     KafkaConfig,
# )
# from mmf_new.core.events.enhanced_event_bus import (
#     enhanced_event_bus_context as event_bus_context,
# )

# Deprecated exports - use enhanced event bus directly
__all__ = [
    # "EventBus",  # Now points to EnhancedEventBus
    # "KafkaConfig",
    # "event_bus_context",
]
