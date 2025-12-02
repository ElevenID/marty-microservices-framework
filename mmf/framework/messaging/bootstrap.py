"""
Messaging Bootstrap - Dependency Injection and Component Wiring

This module handles the orchestration and dependency injection for the messaging system.
It wires together all the messaging components and provides the concrete implementations
that depend on the API layer.

Following the Level Contract principle:
- This module depends on the API layer (messaging.api)
- This module provides concrete implementations
- This module handles dependency injection and component assembly
"""

from mmf.framework.messaging.application.compatibility import (
    DLQHandler,
    EventStreamManager,
    MessageBus,
    MessageQueue,
)
from mmf.framework.messaging.application.consumer import MessageConsumer
from mmf.framework.messaging.application.dlq import DLQManager
from mmf.framework.messaging.application.manager import MessagingManager
from mmf.framework.messaging.application.middleware import MiddlewareChain
from mmf.framework.messaging.application.producer import MessageProducer
from mmf.framework.messaging.application.router import MessageRouter
from mmf.framework.messaging.domain.models import (
    BackendConfig,
    BackendType,
    MessagingConfig,
)
from mmf.framework.messaging.infrastructure.adapters.memory import (
    MemoryMessageBackend,
    MemoryMessageExchange,
    MemoryMessageQueue,
)
from mmf.framework.messaging.infrastructure.adapters.serializer import (
    JSONMessageSerializer,
)
from mmf.framework.messaging.infrastructure.factories import BackendFactory


def create_messaging_manager(config: MessagingConfig | None = None) -> MessagingManager:
    """Create a fully configured messaging manager."""
    if config is None:
        # Create default memory backend config
        backend_config = BackendConfig(type=BackendType.MEMORY, connection_url="memory://localhost")
        config = MessagingConfig(backend=backend_config)

    backend = BackendFactory.create_backend(config.backend)
    return MessagingManager(config, backend)


async def setup_messaging_system(config: MessagingConfig | None = None) -> MessagingManager:
    """Set up and initialize the complete messaging system."""
    manager = create_messaging_manager(config)
    await manager.initialize()
    return manager


__all__ = [
    "JSONMessageSerializer",
    "MemoryMessageQueue",
    "MemoryMessageExchange",
    "MemoryMessageBackend",
    "MessageProducer",
    "MessageConsumer",
    "MessageRouter",
    "DLQManager",
    "MiddlewareChain",
    "MessagingManager",
    "create_messaging_manager",
    "setup_messaging_system",
    "MessageQueue",
    "EventStreamManager",
    "DLQHandler",
    "MessageBus",
]
