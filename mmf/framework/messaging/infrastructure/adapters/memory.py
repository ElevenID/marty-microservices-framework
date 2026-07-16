from __future__ import annotations

import asyncio
import logging
from typing import Any

from mmf.core.messaging import (
    BackendConfig,
    ConsumerConfig,
    IMessageBackend,
    IMessageConsumer,
    IMessageExchange,
    IMessageProducer,
    IMessageQueue,
    Message,
    MessageStatus,
    MessagingError,
    ProducerConfig,
)
from mmf.framework.messaging.application.consumer import MessageConsumer
from mmf.framework.messaging.application.producer import MessageProducer


class MemoryMessageQueue(IMessageQueue):
    """In-memory message queue implementation."""

    def __init__(self, name: str):
        self.name = name
        self.messages: asyncio.Queue[Message] = asyncio.Queue()
        self.bindings: dict[str, list[str]] = {}  # exchange -> routing_keys
        self._declared = False

    async def declare(self, config: Any) -> bool:
        """Declare the queue."""
        self._declared = True
        return True

    async def delete(self, if_unused: bool = False, if_empty: bool = False) -> bool:
        """Delete the queue."""
        if if_empty and not self.messages.empty():
            return False
        # Drain queue
        while not self.messages.empty():
            try:
                self.messages.get_nowait()
            except asyncio.QueueEmpty:
                break
        self.bindings.clear()
        self._declared = False
        return True

    async def purge(self) -> int:
        """Purge all messages from queue."""
        count = self.messages.qsize()
        while not self.messages.empty():
            try:
                self.messages.get_nowait()
            except asyncio.QueueEmpty:
                break
        return count

    async def bind(self, exchange: str, routing_key: str = "") -> bool:
        """Bind queue to exchange."""
        if exchange not in self.bindings:
            self.bindings[exchange] = []
        if routing_key not in self.bindings[exchange]:
            self.bindings[exchange].append(routing_key)
        return True

    async def unbind(self, exchange: str, routing_key: str = "") -> bool:
        """Unbind queue from exchange."""
        if exchange in self.bindings and routing_key in self.bindings[exchange]:
            self.bindings[exchange].remove(routing_key)
            if not self.bindings[exchange]:
                del self.bindings[exchange]
        return True

    async def get_message_count(self) -> int:
        """Get number of messages in queue."""
        return self.messages.qsize()

    async def get_consumer_count(self) -> int:
        """Get number of consumers."""
        return 0  # Memory queue doesn't track consumers


class MemoryMessageExchange(IMessageExchange):
    """In-memory message exchange implementation."""

    def __init__(self, name: str):
        self.name = name
        self.bindings: dict[str, list[str]] = {}  # destination -> routing_keys
        self._declared = False

    async def declare(self, config: Any) -> bool:
        """Declare the exchange."""
        self._declared = True
        return True

    async def delete(self, if_unused: bool = False) -> bool:
        """Delete the exchange."""
        self.bindings.clear()
        self._declared = False
        return True

    async def bind(
        self, destination: str, routing_key: str = "", arguments: dict[str, Any] | None = None
    ) -> bool:
        """Bind exchange to destination."""
        if destination not in self.bindings:
            self.bindings[destination] = []
        if routing_key not in self.bindings[destination]:
            self.bindings[destination].append(routing_key)
        return True

    async def unbind(self, destination: str, routing_key: str = "") -> bool:
        """Unbind from destination."""
        if destination in self.bindings and routing_key in self.bindings[destination]:
            self.bindings[destination].remove(routing_key)
            if not self.bindings[destination]:
                del self.bindings[destination]
        return True


class MemoryMessageProducer(MessageProducer):
    """In-memory message producer implementation."""

    def __init__(self, config: ProducerConfig, backend: MemoryMessageBackend):
        super().__init__(config, backend)
        self.backend = backend

    async def publish(self, message: Message) -> bool:
        """Publish a single message."""
        if not self._running:
            raise MessagingError("Producer is not running")

        # Set default values from config
        if not message.exchange and self.config.exchange:
            message.exchange = self.config.exchange
        if not message.routing_key:
            message.routing_key = self.config.routing_key

        exchange_name = message.exchange
        routing_key = message.routing_key

        if not exchange_name:
            self.logger.warning(f"Message {message.id} has no exchange")
            return False

        # Find queues bound to this exchange/routing_key
        delivered = False
        for queue in self.backend.queues.values():
            if exchange_name in queue.bindings:
                if routing_key in queue.bindings[exchange_name]:
                    await queue.messages.put(message)
                    delivered = True

        if delivered:
            message.status = MessageStatus.PROCESSED
            self.logger.debug(f"Published message {message.id} to {exchange_name}/{routing_key}")
            return True
        else:
            self.logger.warning(f"Message {message.id} was not routed to any queue")
            return False


class MemoryMessageConsumer(MessageConsumer):
    """In-memory message consumer implementation."""

    def __init__(self, config: ConsumerConfig, backend: MemoryMessageBackend):
        super().__init__(config, backend)
        self.backend = backend
        # We don't need self._consume_task here because parent class manages self._task

    async def _consume_loop(self) -> None:
        """Consumption loop."""
        queue_name = self.config.queue

        # Wait for queue to exist
        while queue_name not in self.backend.queues and self._running:
            await asyncio.sleep(0.1)

        if not self._running:
            return

        queue = self.backend.queues[queue_name]
        while self._running:
            try:
                message = await queue.messages.get()
                if self._handler:
                    try:
                        await self._handler(message)
                        await self.acknowledge(message)
                    except Exception as e:
                        self.logger.error(f"Error handling message: {e}")
                        await self.reject(message)
                else:
                    # No handler, just acknowledge to remove from queue or requeue?
                    # For now, just log warning and drop
                    self.logger.warning("No handler set for consumer")
                    await self.acknowledge(message)
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in consume loop: {e}")
                await asyncio.sleep(1)


class MemoryMessageBackend(IMessageBackend):
    """In-memory message backend implementation."""

    def __init__(self, config: BackendConfig):
        self.config = config
        self.queues: dict[str, MemoryMessageQueue] = {}
        self.exchanges: dict[str, MemoryMessageExchange] = {}
        self._connected = False
        self.logger = logging.getLogger(__name__)

    async def connect(self) -> bool:
        """Connect to the backend."""
        self._connected = True
        self.logger.info("Connected to memory backend")
        return True

    async def disconnect(self) -> None:
        """Disconnect from the backend."""
        self._connected = False
        self.queues.clear()
        self.exchanges.clear()
        self.logger.info("Disconnected from memory backend")

    async def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected

    async def health_check(self) -> bool:
        """Perform health check."""
        return self._connected

    async def create_queue(self, config: Any) -> IMessageQueue:
        """Create a message queue."""
        queue = MemoryMessageQueue(config.name)
        await queue.declare(config)
        self.queues[config.name] = queue
        return queue

    async def create_exchange(self, config: Any) -> IMessageExchange:
        """Create a message exchange."""
        exchange = MemoryMessageExchange(config.name)
        await exchange.declare(config)
        self.exchanges[config.name] = exchange
        return exchange

    async def create_producer(self, config: ProducerConfig) -> IMessageProducer:
        """Create a message producer."""
        return MemoryMessageProducer(config, self)

    async def create_consumer(self, config: ConsumerConfig) -> IMessageConsumer:
        """Create a message consumer."""
        return MemoryMessageConsumer(config, self)
