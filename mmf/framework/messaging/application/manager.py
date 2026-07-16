from __future__ import annotations

import logging
from typing import Any

from mmf.core.messaging import (
    ConsumerConfig,
    IDLQManager,
    IMessageBackend,
    IMessageBroker,
    IMessageConsumer,
    IMessageProducer,
    IMessageRouter,
    IMessagingManager,
    MessagingConfig,
    MessagingError,
    ProducerConfig,
)
from mmf.framework.messaging.application.broker import MessageBroker
from mmf.framework.messaging.application.dlq import DLQManager
from mmf.framework.messaging.application.middleware import MiddlewareChain
from mmf.framework.messaging.application.router import MessageRouter


class MessagingManager(IMessagingManager):
    """Messaging manager implementation."""

    def __init__(
        self,
        config: MessagingConfig,
        backend: IMessageBackend,
        router: IMessageRouter,
        dlq_manager: IDLQManager,
    ):
        self.config = config
        self.backend = backend
        self.router = router
        self.dlq_manager = dlq_manager
        self.logger = logging.getLogger(__name__)
        self.middleware_chain = MiddlewareChain()
        self.broker = MessageBroker(backend, router)
        self.producers: dict[str, IMessageProducer] = {}
        self.consumers: dict[str, IMessageConsumer] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the messaging system."""
        if self._initialized:
            return

        # Connect backend
        await self.backend.connect()

        self._initialized = True
        self.logger.info("Messaging system initialized")

    async def shutdown(self) -> None:
        """Shutdown the messaging system."""
        # Stop all consumers
        for consumer in self.consumers.values():
            await consumer.stop()

        # Stop all producers
        for producer in self.producers.values():
            await producer.stop()

        # Disconnect backend
        if self.backend:
            await self.backend.disconnect()

        self._initialized = False
        self.logger.info("Messaging system shutdown")

    async def create_producer(self, config: ProducerConfig) -> IMessageProducer:
        """Create a message producer."""
        if not self._initialized:
            raise MessagingError("Messaging system not initialized")

        if not self.backend:
            raise MessagingError("Backend not initialized")
        producer = await self.backend.create_producer(config)
        await producer.start()
        # Store generic producer, assuming it has a name or we use config.name
        self.producers[config.name] = producer
        return producer

    async def create_consumer(self, config: ConsumerConfig) -> IMessageConsumer:
        """Create a message consumer."""
        if not self._initialized:
            raise MessagingError("Messaging system not initialized")

        if not self.backend:
            raise MessagingError("Backend not initialized")
        consumer = await self.backend.create_consumer(config)
        self.consumers[config.name] = consumer
        return consumer

    async def get_backend(self) -> IMessageBackend:
        """Get the message backend."""
        if not self.backend:
            raise MessagingError("Backend not initialized")
        return self.backend

    async def get_broker(self) -> IMessageBroker:
        """Get the message broker."""
        return self.broker

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on messaging system."""
        health = {
            "initialized": self._initialized,
            "backend_connected": False,
            "producers": len(self.producers),
            "consumers": len(self.consumers),
        }

        if self.backend:
            health["backend_connected"] = await self.backend.health_check()

        return health
