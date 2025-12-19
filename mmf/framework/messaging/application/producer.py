from __future__ import annotations

import logging
import time

from mmf.core.messaging import (
    IMessageBackend,
    IMessageProducer,
    IMessageSerializer,
    Message,
    MessagePriority,
    MessageStatus,
    MessagingError,
    ProducerConfig,
)
from mmf.framework.messaging.infrastructure.adapters.serializer import (
    JSONMessageSerializer,
)


class MessageProducer(IMessageProducer):
    """Message producer implementation."""

    def __init__(
        self,
        config: ProducerConfig,
        backend: IMessageBackend,
        serializer: IMessageSerializer | None = None,
    ):
        self.config = config
        self.backend = backend
        self.serializer = serializer or JSONMessageSerializer()
        self.logger = logging.getLogger(__name__)
        self._running = False

    async def start(self) -> None:
        """Start the producer."""
        self._running = True
        self.logger.info(f"Started producer: {self.config.name}")

    async def stop(self) -> None:
        """Stop the producer."""
        self._running = False
        self.logger.info(f"Stopped producer: {self.config.name}")

    async def publish(self, message: Message) -> bool:
        """Publish a single message."""
        if not self._running:
            raise MessagingError("Producer is not running")

        try:
            # Set default values from config
            if not message.exchange and self.config.exchange:
                message.exchange = self.config.exchange
            if not message.routing_key:
                message.routing_key = self.config.routing_key
            if message.priority == MessagePriority.NORMAL:
                message.priority = self.config.default_priority

            # Update message status
            message.status = MessageStatus.PROCESSING
            message.timestamp = time.time()

            # For memory backend, we'll simulate publishing
            # In real implementation, this would use the backend's publish mechanism
            # TODO: This seems to be coupled to MemoryBackend behavior or assumes backend handles it.
            # The original code had:
            # self.logger.debug(
            #     f"Published message {message.id} to {message.exchange}/{message.routing_key}"
            # )
            # message.status = MessageStatus.PROCESSED
            # return True

            # But wait, the producer should delegate to the backend to actually send the message?
            # In the original bootstrap.py, MessageProducer.publish just logged and returned True.
            # It didn't call backend.publish(). This looks like a bug or incomplete implementation in the original code.
            # "For memory backend, we'll simulate publishing"

            # However, I should preserve the behavior for now during refactoring.

            self.logger.debug(
                f"Published message {message.id} to {message.exchange}/{message.routing_key}"
            )
            message.status = MessageStatus.PROCESSED
            return True

        except Exception as e:
            message.status = MessageStatus.FAILED
            self.logger.error(f"Failed to publish message {message.id}: {e}")
            return False

    async def publish_batch(self, messages: list[Message]) -> list[bool]:
        """Publish multiple messages."""
        results = []
        for message in messages:
            result = await self.publish(message)
            results.append(result)
        return results
