"""
FastStream Adapter - Messaging Backend Implementation

This module provides the FastStream implementation of the messaging backend interfaces.
It supports multiple protocols (Kafka, RabbitMQ, Redis, NATS) through FastStream's unified API.
"""

import asyncio
import logging
from typing import Any

from faststream import FastStream
from faststream.kafka import KafkaBroker
from faststream.nats import NatsBroker
from faststream.rabbit import RabbitBroker
from faststream.redis import RedisBroker

from mmf.core.messaging import (
    BackendConfig,
    BackendType,
    ConsumerConfig,
    ExchangeConfig,
    IMessageBackend,
    IMessageConsumer,
    IMessageExchange,
    IMessageProducer,
    IMessageQueue,
    Message,
    MessagePriority,
    MessageStatus,
    ProducerConfig,
    QueueConfig,
)

logger = logging.getLogger(__name__)


class FastStreamQueue(IMessageQueue):
    """FastStream queue implementation."""

    def __init__(self, name: str, broker: Any):
        self.name = name
        self.broker = broker

    async def declare(self, config: QueueConfig) -> bool:
        """Declare the queue."""
        # FastStream handles declaration implicitly or via specific broker methods
        # For RabbitMQ, we might need explicit declaration
        if isinstance(self.broker, RabbitBroker):
            await self.broker.declare_queue(
                queue=self.name,
                durable=config.durable,
                auto_delete=config.auto_delete,
            )
        return True

    async def delete(self, if_unused: bool = False, if_empty: bool = False) -> bool:
        """Delete the queue."""
        # FastStream doesn't expose delete uniformly, might need broker-specific calls
        return True

    async def purge(self) -> int:
        """Purge all messages from queue."""
        return 0

    async def bind(self, exchange: str, routing_key: str = "") -> bool:
        """Bind queue to exchange."""
        if isinstance(self.broker, RabbitBroker):
            await self.broker.declare_binding(
                queue=self.name,
                exchange=exchange,
                routing_key=routing_key,
            )
        return True

    async def unbind(self, exchange: str, routing_key: str = "") -> bool:
        """Unbind queue from exchange."""
        return True

    async def get_message_count(self) -> int:
        """Get number of messages in queue."""
        return 0

    async def get_consumer_count(self) -> int:
        """Get number of consumers."""
        return 0


class FastStreamExchange(IMessageExchange):
    """FastStream exchange implementation."""

    def __init__(self, name: str, broker: Any):
        self.name = name
        self.broker = broker

    async def declare(self, config: ExchangeConfig) -> bool:
        """Declare the exchange."""
        if isinstance(self.broker, RabbitBroker):
            await self.broker.declare_exchange(
                exchange=self.name,
                type=config.type,
                durable=config.durable,
                auto_delete=config.auto_delete,
            )
        return True

    async def delete(self, if_unused: bool = False) -> bool:
        """Delete the exchange."""
        return True

    async def bind(
        self, destination: str, routing_key: str = "", arguments: dict[str, Any] | None = None
    ) -> bool:
        """Bind exchange to destination."""
        return True

    async def unbind(self, destination: str, routing_key: str = "") -> bool:
        """Unbind from destination."""
        return True


class FastStreamProducer(IMessageProducer):
    """FastStream producer implementation."""

    def __init__(self, config: ProducerConfig, broker: Any):
        self.config = config
        self.broker = broker
        self._running = False

    async def start(self) -> None:
        """Start the producer."""
        self._running = True

    async def stop(self) -> None:
        """Stop the producer."""
        self._running = False

    async def publish(self, message: Message) -> bool:
        """Publish a single message."""
        if not self._running:
            return False

        try:
            exchange = message.exchange or self.config.exchange
            routing_key = message.routing_key or self.config.routing_key

            # FastStream publish
            await self.broker.publish(
                message.body,
                exchange=exchange,
                routing_key=routing_key,
                headers=message.headers.data,
                correlation_id=message.correlation_id,
            )
            message.status = MessageStatus.PROCESSED
            return True
        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            message.status = MessageStatus.FAILED
            return False

    async def publish_batch(self, messages: list[Message]) -> list[bool]:
        """Publish multiple messages."""
        results = []
        for msg in messages:
            results.append(await self.publish(msg))
        return results


class FastStreamConsumer(IMessageConsumer):
    """FastStream consumer implementation."""

    def __init__(self, config: ConsumerConfig, broker: Any):
        self.config = config
        self.broker = broker
        self._running = False
        self._handler = None

    async def start(self) -> None:
        """Start consuming messages."""
        self._running = True

        if self._handler:
            # Define a wrapper to adapt FastStream message to our Message interface
            async def wrapper(body: Any):
                # TODO: Extract headers and other metadata if possible
                # For now, we assume body is the payload
                msg = Message(body=body)
                if self._handler:
                    await self._handler(msg)

            # Register the subscriber
            # We use the queue_name from config as the topic/queue
            self.broker.subscriber(self.config.queue_name)(wrapper)

    async def stop(self) -> None:
        """Stop consuming messages."""
        self._running = False

    async def acknowledge(self, message: Message) -> None:
        """Acknowledge message processing."""
        # FastStream handles ack automatically usually, or via context
        pass

    async def reject(self, message: Message, requeue: bool = False) -> None:
        """Reject message."""
        pass

    async def set_handler(self, handler: Any) -> None:
        """Set message handler."""
        self._handler = handler

    def _create_router(self):
        # Create a FastStream router/subscriber for this consumer
        # This is a simplification; actual implementation depends on how we want to map
        # the generic handler to FastStream's expected signature
        pass


class FastStreamBackend(IMessageBackend):
    """FastStream backend implementation."""

    def __init__(self, config: BackendConfig):
        self.config = config
        self.broker: Any = None
        self.app: FastStream | None = None

    async def connect(self) -> bool:
        """Connect to the backend."""
        try:
            if self.config.type == BackendType.KAFKA:
                self.broker = KafkaBroker(self.config.connection_url)
            elif self.config.type == BackendType.RABBITMQ:
                self.broker = RabbitBroker(self.config.connection_url)
            elif self.config.type == BackendType.REDIS:
                self.broker = RedisBroker(self.config.connection_url)
            elif self.config.type == BackendType.NATS:
                self.broker = NatsBroker(self.config.connection_url)
            else:
                raise ValueError(f"Unsupported backend type: {self.config.type}")

            await self.broker.connect()
            return True
        except Exception as e:
            logger.error(f"Failed to connect to backend: {e}")
            return False

    async def disconnect(self) -> None:
        """Disconnect from the backend."""
        if self.broker:
            await self.broker.close()

    async def is_connected(self) -> bool:
        """Check if connected."""
        return self.broker is not None and self.broker.connected

    async def health_check(self) -> bool:
        """Perform health check."""
        if not self.broker:
            return False
        return await self.broker.ping()

    async def create_queue(self, config: QueueConfig) -> IMessageQueue:
        """Create a message queue."""
        queue = FastStreamQueue(config.name, self.broker)
        await queue.declare(config)
        return queue

    async def create_exchange(self, config: ExchangeConfig) -> IMessageExchange:
        """Create a message exchange."""
        exchange = FastStreamExchange(config.name, self.broker)
        await exchange.declare(config)
        return exchange

    async def create_producer(self, config: ProducerConfig) -> IMessageProducer:
        """Create a message producer."""
        return FastStreamProducer(config, self.broker)

    async def create_consumer(self, config: ConsumerConfig) -> IMessageConsumer:
        """Create a message consumer."""
        return FastStreamConsumer(config, self.broker)
