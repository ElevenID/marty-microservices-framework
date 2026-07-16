"""
Message Broker Implementation

This module implements the Broker pattern to decouple producers from consumers.
The broker is responsible for routing messages to the appropriate destination
using the configured routing rules and backend.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from mmf.core.messaging import (
    ConsumerConfig,
    IMessageBackend,
    IMessageBroker,
    IMessageConsumer,
    IMessageProducer,
    IMessageRouter,
    Message,
    ProducerConfig,
)


class MessageBroker(IMessageBroker):
    """
    Message Broker implementation.

    Acts as an intermediary between producers and consumers, handling
    routing and connection management.
    """

    def __init__(self, backend: IMessageBackend, router: IMessageRouter):
        self.backend = backend
        self.router = router
        self.logger = logging.getLogger(__name__)
        self._producers: dict[str, IMessageProducer] = {}
        self._consumers: dict[str, IMessageConsumer] = {}

    async def publish(self, message: Message) -> bool:
        """
        Publish a message through the broker.

        The broker uses the router to determine the destination exchange
        and routing key, then uses an appropriate producer to send the message.
        """
        # Route the message
        exchange, routing_key = await self.router.route(message)

        # Update message routing info if needed
        # Note: We don't modify the original message to avoid side effects

        # Get or create producer for the exchange
        producer = await self._get_producer(exchange)

        # Publish
        try:
            return await producer.publish(message)
        except Exception as e:
            self.logger.error(f"Failed to publish message to {exchange}: {e}")
            return False

    async def subscribe(self, queue: str, handler: Callable[[Message], Any]) -> None:
        """Subscribe to a queue."""
        if queue in self._consumers:
            self.logger.warning(f"Already subscribed to queue: {queue}")
            return

        config = ConsumerConfig(name=f"broker_consumer_{queue}", queue=queue)
        consumer = await self.backend.create_consumer(config)
        await consumer.set_handler(handler)
        await consumer.start()

        self._consumers[queue] = consumer
        self.logger.info(f"Subscribed to queue: {queue}")

    async def unsubscribe(self, queue: str) -> None:
        """Unsubscribe from a queue."""
        if queue not in self._consumers:
            self.logger.warning(f"Not subscribed to queue: {queue}")
            return

        consumer = self._consumers.pop(queue)
        await consumer.stop()
        self.logger.info(f"Unsubscribed from queue: {queue}")

    async def _get_producer(self, exchange: str) -> IMessageProducer:
        """Get or create a producer for the specified exchange."""
        if exchange not in self._producers:
            config = ProducerConfig(name=f"broker_producer_{exchange}", exchange=exchange)
            producer = await self.backend.create_producer(config)
            await producer.start()
            self._producers[exchange] = producer

        return self._producers[exchange]

    async def shutdown(self) -> None:
        """Shutdown the broker and all managed components."""
        for consumer in self._consumers.values():
            await consumer.stop()
        self._consumers.clear()

        for producer in self._producers.values():
            await producer.stop()
        self._producers.clear()
