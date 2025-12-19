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

from mmf.core.messaging import BackendConfig, BackendType, MessagingConfig
from mmf.core.registry import get_service, register_singleton
from mmf.framework.messaging.application.broker import MessageBroker
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
    router = MessageRouter(config.routing)
    dlq_manager = DLQManager(config.dlq, backend)

    return MessagingManager(config, backend, router, dlq_manager)


def get_messaging_manager() -> MessagingManager:
    """Get the global messaging manager from the registry."""
    try:
        return get_service(MessagingManager)
    except KeyError:
        manager = create_messaging_manager()
        register_singleton(MessagingManager, manager)
        return manager


async def setup_messaging_system(config: MessagingConfig | None = None) -> MessagingManager:
    """Set up and initialize the complete messaging system."""
    manager = create_messaging_manager(config)
    await manager.initialize()
    register_singleton(MessagingManager, manager)
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
    "get_messaging_manager",
    "setup_messaging_system",
    "MessageQueue",
    "EventStreamManager",
    "DLQHandler",
    "MessageBus",
    "MessageBroker",
]
