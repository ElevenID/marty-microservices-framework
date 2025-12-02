"""
Messaging Domain Ports

This module defines the interfaces (ports) for the messaging system.
It is part of the Domain layer and depends only on the Domain Models.

Note: This module re-exports interfaces from mmf.framework.messaging.interfaces
to maintain backward compatibility. New code should import from interfaces directly.
"""

from mmf.framework.messaging.interfaces import (
    IDLQManager,
    IMessageBackend,
    IMessageConsumer,
    IMessageExchange,
    IMessageMiddleware,
    IMessageProducer,
    IMessageQueue,
    IMessageRouter,
    IMessageSerializer,
    IMessagingManager,
)

__all__ = [
    "IDLQManager",
    "IMessageBackend",
    "IMessageConsumer",
    "IMessageExchange",
    "IMessageMiddleware",
    "IMessageProducer",
    "IMessageQueue",
    "IMessageRouter",
    "IMessageSerializer",
    "IMessagingManager",
]
