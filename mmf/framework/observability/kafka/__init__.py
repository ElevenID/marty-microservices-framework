"""
Kafka infrastructure for Marty Microservices Framework

Kafka functionality is provided by the enhanced event bus.
Import from mmf.framework.events for Kafka-based event streaming.
"""

from mmf.framework.events.enhanced_event_bus import EnhancedEventBus as EventBus
from mmf.framework.events.enhanced_event_bus import KafkaConfig

__all__ = [
    "EventBus",  # EnhancedEventBus with Kafka support
    "KafkaConfig",
]
