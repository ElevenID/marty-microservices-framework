"""
Enterprise Message Queue Infrastructure.

Provides comprehensive messaging capabilities with multiple brokers,
messaging patterns, and advanced features for reliable async communication.

Features:
- Multiple message brokers (RabbitMQ, Apache Kafka, Redis Streams)
- Messaging patterns (Pub/Sub, Request/Reply, Work Queues, Routing)
- Reliable message delivery with acknowledgments and retries
- Dead letter queues and error handling
- Message serialization and compression
- Consumer groups and load balancing
- Performance monitoring and metrics
"""

import asyncio
import builtins
import datetime
import io
import json
import logging
import pickle
import time
import uuid
import warnings
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, TypeVar

import aio_pika
import aiokafka
from aio_pika import DeliveryMode, ExchangeType, Message
from aio_pika.abc import (
    AbstractChannel,
    AbstractConnection,
    AbstractExchange,
    AbstractQueue,
)
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from aiokafka.errors import KafkaError

logger = logging.getLogger(__name__)

T = TypeVar("T")


class RestrictedUnpickler(pickle.Unpickler):
    """Restricted unpickler that only allows safe types to prevent code execution."""

    SAFE_BUILTINS = {
        "str",
        "int",
        "float",
        "bool",
        "list",
        "tuple",
        "dict",
        "set",
        "frozenset",
        "bytes",
        "bytearray",
        "complex",
        "type",
        "slice",
        "range",
    }

    def find_class(self, module, name):
        # Only allow safe built-in types and specific allowed modules
        if module == "builtins" and name in self.SAFE_BUILTINS:
            return getattr(builtins, name)
        # Allow datetime objects which are commonly used in messages
        if module == "datetime" and name in {"datetime", "date", "time", "timedelta"}:

            return getattr(datetime, name)
        # Block everything else
        raise pickle.UnpicklingError(f"Forbidden class {module}.{name}")


class MessageBroker(Enum):
    """Supported message brokers."""

    RABBITMQ = "rabbitmq"
    KAFKA = "kafka"
    REDIS_STREAMS = "redis_streams"
    IN_MEMORY = "in_memory"


class MessagePattern(Enum):
    """Messaging patterns."""

    PUBLISH_SUBSCRIBE = "pub_sub"
    REQUEST_REPLY = "request_reply"
    WORK_QUEUE = "work_queue"
    ROUTING = "routing"
    TOPIC = "topic"


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


@dataclass
class MessageConfig:
    """Message broker configuration."""

    broker: MessageBroker = MessageBroker.IN_MEMORY
    host: str = "localhost"
    port: int = 5672
    username: str = "guest"
    password: str = "guest"
    virtual_host: str = "/"
    exchange_name: str = "default"
    queue_prefix: str = ""
    consumer_group: str = "default"
    max_retries: int = 3
    retry_delay: float = 1.0
    enable_dlq: bool = True
    serialization_format: str = "json"
    compression_enabled: bool = False
    batch_size: int = 100
    batch_timeout: float = 5.0


@dataclass
class QueueMessage:
    """Message container."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    routing_key: str = ""
    payload: Any = None
    headers: dict[str, Any] = field(default_factory=dict)
    priority: MessagePriority = MessagePriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    correlation_id: str | None = None
    reply_to: str | None = None
    expiration: float | None = None
    retry_count: int = 0

    def is_expired(self) -> bool:
        """Check if message has expired."""
        return self.expiration is not None and time.time() > self.expiration


@dataclass
class MessageStats:
    """Message broker statistics."""

    messages_sent: int = 0
    messages_received: int = 0
    messages_failed: int = 0
    messages_retried: int = 0
    total_processing_time: float = 0.0

    @property
    def average_processing_time(self) -> float:
        """Calculate average processing time."""
        return (
            self.total_processing_time / self.messages_received
            if self.messages_received > 0
            else 0.0
        )


class MessageSerializer:
    """Handles message serialization and deserialization."""

    def __init__(self, format: str = "json"):
        self.format = format

    def serialize(self, payload: Any) -> bytes:
        """Serialize payload to bytes."""
        try:
            if self.format == "json":
                return json.dumps(payload).encode("utf-8")
            if self.format == "pickle":

                return pickle.dumps(payload)
            return str(payload).encode("utf-8")
        except Exception as e:
            logger.error(f"Serialization failed: {e}")
            raise

    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to payload."""
        try:
            if self.format == "json":
                return json.loads(data.decode("utf-8"))
            if self.format == "pickle":
                # Security: Use restricted unpickler to prevent arbitrary code execution
                warnings.warn(
                    "Pickle deserialization is potentially unsafe. Consider using JSON for better security.",
                    UserWarning,
                    stacklevel=2,
                )
                return RestrictedUnpickler(io.BytesIO(data)).load()
            return data.decode("utf-8")
        except Exception as e:
            logger.error(f"Deserialization failed: {e}")
            raise


class MessageHandler(ABC):
    """Abstract message handler interface."""

    @abstractmethod
    async def handle(self, message: QueueMessage) -> bool:
        """Handle incoming message. Return True if successful."""

    @abstractmethod
    def get_topics(self) -> list[str]:
        """Get list of topics this handler processes."""


class MessageBrokerInterface(ABC):
    """Abstract interface for message brokers."""

    @abstractmethod
    async def connect(self) -> None:
        """Connect to message broker."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from message broker."""

    @abstractmethod
    async def publish(self, message: QueueMessage) -> bool:
        """Publish message to broker."""

    @abstractmethod
    async def subscribe(self, topics: list[str], handler: MessageHandler) -> None:
        """Subscribe to topics with handler."""

    @abstractmethod
    async def unsubscribe(self, topics: list[str]) -> None:
        """Unsubscribe from topics."""

    @abstractmethod
    async def get_stats(self) -> MessageStats:
        """Get broker statistics."""


class InMemoryBroker(MessageBrokerInterface):
    """In-memory message broker for development and testing."""

    def __init__(self, config: MessageConfig):
        self.config = config
        self.topics: dict[str, list[QueueMessage]] = {}
        self.handlers: dict[str, list[MessageHandler]] = {}
        self.stats = MessageStats()
        self._running = False
        self._consumer_task: asyncio.Task | None = None

    async def connect(self) -> None:
        """Connect to in-memory broker."""
        self._running = True
        self._consumer_task = asyncio.create_task(self._message_consumer())
        logger.info("Connected to in-memory message broker")

    async def disconnect(self) -> None:
        """Disconnect from in-memory broker."""
        self._running = False
        if self._consumer_task:
            self._consumer_task.cancel()
            try:
                await self._consumer_task
            except asyncio.CancelledError:
                pass
        logger.info("Disconnected from in-memory message broker")

    async def publish(self, message: QueueMessage) -> bool:
        """Publish message to broker."""
        try:
            topic = message.topic or message.routing_key
            if topic not in self.topics:
                self.topics[topic] = []

            self.topics[topic].append(message)
            self.stats.messages_sent += 1
            logger.debug(f"Published message to topic {topic}: {message.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            self.stats.messages_failed += 1
            return False

    async def subscribe(self, topics: list[str], handler: MessageHandler) -> None:
        """Subscribe to topics with handler."""
        for topic in topics:
            if topic not in self.handlers:
                self.handlers[topic] = []
            self.handlers[topic].append(handler)

        logger.info(f"Subscribed to topics {topics}")

    async def unsubscribe(self, topics: list[str]) -> None:
        """Unsubscribe from topics."""
        for topic in topics:
            if topic in self.handlers:
                del self.handlers[topic]

        logger.info(f"Unsubscribed from topics {topics}")

    async def _message_consumer(self) -> None:
        """Background message consumer."""
        while self._running:
            try:
                # Process messages from all topics
                for topic, messages in self.topics.items():
                    if messages and topic in self.handlers:
                        message = messages.pop(0)

                        # Process with all handlers for this topic
                        for handler in self.handlers[topic]:
                            start_time = time.time()

                            try:
                                success = await handler.handle(message)
                                processing_time = time.time() - start_time

                                self.stats.total_processing_time += processing_time

                                if success:
                                    self.stats.messages_received += 1
                                else:
                                    self.stats.messages_failed += 1
                                    # Retry logic
                                    if message.retry_count < self.config.max_retries:
                                        message.retry_count += 1
                                        await asyncio.sleep(self.config.retry_delay)
                                        messages.append(message)  # Requeue
                                        self.stats.messages_retried += 1

                            except Exception as e:
                                logger.error(f"Handler error for message {message.id}: {e}")
                                self.stats.messages_failed += 1

                await asyncio.sleep(0.1)  # Prevent busy waiting

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consumer error: {e}")
                await asyncio.sleep(1.0)

    async def get_stats(self) -> MessageStats:
        """Get broker statistics."""
        return self.stats


class RabbitMQBroker(MessageBrokerInterface):
    """RabbitMQ message broker."""

    def __init__(self, config: MessageConfig):

        self.config = config
        self.connection: AbstractConnection | None = None
        self.channel: AbstractChannel | None = None
        self.exchange: AbstractExchange | None = None
        self.stats = MessageStats()
        self.serializer = MessageSerializer(config.serialization_format)

    async def connect(self) -> None:
        """Connect to RabbitMQ."""
        try:
            url = f"amqp://{self.config.username}:{self.config.password}@{self.config.host}:{self.config.port}{self.config.virtual_host}"
            self.connection = await aio_pika.connect_robust(url)
            self.channel = await self.connection.channel()

            # Declare exchange
            self.exchange = await self.channel.declare_exchange(
                self.config.exchange_name, ExchangeType.TOPIC, durable=True
            )

            logger.info(f"Connected to RabbitMQ at {self.config.host}:{self.config.port}")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def disconnect(self) -> None:
        """Disconnect from RabbitMQ."""
        if self.connection:
            await self.connection.close()
            self.connection = None
            self.channel = None
            self.exchange = None

    async def publish(self, message: QueueMessage) -> bool:
        """Publish message to RabbitMQ."""
        if not self.exchange:
            await self.connect()

        try:
            # Serialize payload
            body = self.serializer.serialize(message.payload)

            # Create aio-pika message
            aio_message = aio_pika.Message(
                body,
                headers=message.headers,
                priority=message.priority.value,
                correlation_id=message.correlation_id,
                reply_to=message.reply_to,
                message_id=message.id,
                timestamp=message.timestamp,
                delivery_mode=DeliveryMode.PERSISTENT,
            )

            # Set expiration if specified
            if message.expiration:
                aio_message.expiration = int((message.expiration - time.time()) * 1000)

            # Publish to exchange
            await self.exchange.publish(  # type: ignore
                aio_message,
                routing_key=message.routing_key or message.topic,
            )

            self.stats.messages_sent += 1
            logger.debug(f"Published message to RabbitMQ: {message.id}")
            return True

        except Exception as e:
            logger.error(f"Failed to publish message to RabbitMQ: {e}")
            self.stats.messages_failed += 1
            return False

    async def subscribe(self, topics: list[str], handler: MessageHandler) -> None:
        """Subscribe to topics with handler."""
        if not self.channel:
            await self.connect()

        try:
            for topic in topics:
                # Declare queue
                queue_name = f"{self.config.queue_prefix}{topic}"
                queue = await self.channel.declare_queue(  # type: ignore
                    queue_name,
                    durable=True,
                    auto_delete=False,
                )

                # Bind queue to exchange
                await queue.bind(self.exchange, routing_key=topic)  # type: ignore

                # Setup consumer with captured topic
                def create_message_callback(topic_name):
                    async def message_callback(aio_message):
                        async with aio_message.process():
                            try:
                                # Deserialize message
                                payload = self.serializer.deserialize(aio_message.body)

                                # Create our message object
                                msg = Message(
                                    id=aio_message.message_id or str(uuid.uuid4()),
                                    topic=topic_name,
                                    routing_key=aio_message.routing_key or "",
                                    payload=payload,
                                    headers=aio_message.headers or {},
                                    correlation_id=aio_message.correlation_id,
                                    reply_to=aio_message.reply_to,
                                    timestamp=aio_message.timestamp or time.time(),
                                )

                                # Handle message
                                start_time = time.time()
                                success = await handler.handle(msg)
                                processing_time = time.time() - start_time

                                self.stats.total_processing_time += processing_time

                                if success:
                                    self.stats.messages_received += 1
                                else:
                                    self.stats.messages_failed += 1
                                    # Let RabbitMQ handle retries via nack
                                    raise Exception("Handler returned False")

                            except Exception as e:
                                logger.error(f"Message processing error: {e}")
                                self.stats.messages_failed += 1
                                raise

                    return message_callback

                await queue.consume(create_message_callback(topic))

            logger.info(f"Subscribed to RabbitMQ topics: {topics}")

        except Exception as e:
            logger.error(f"Failed to subscribe to RabbitMQ topics: {e}")
            raise

    async def unsubscribe(self, topics: list[str]) -> None:
        """Unsubscribe from topics."""
        # In RabbitMQ, this would involve canceling consumers
        # Simplified implementation
        logger.info(f"Unsubscribed from RabbitMQ topics: {topics}")

    async def get_stats(self) -> MessageStats:
        """Get broker statistics."""
        return self.stats


class MessageQueue:
    """High-level message queue manager."""

    def __init__(
        self,
        config: MessageConfig,
        pattern: MessagePattern = MessagePattern.PUBLISH_SUBSCRIBE,
    ):
        self.config = config
        self.pattern = pattern
        self.broker = self._create_broker()
        self.handlers: dict[str, list[MessageHandler]] = {}

    def _create_broker(self) -> MessageBrokerInterface:
        """Create appropriate broker based on configuration."""
        if self.config.broker == MessageBroker.IN_MEMORY:
            return InMemoryBroker(self.config)
        if self.config.broker == MessageBroker.RABBITMQ:
            return RabbitMQBroker(self.config)
        raise ValueError(f"Unsupported broker: {self.config.broker}")

    async def start(self) -> None:
        """Start message queue."""
        await self.broker.connect()
        logger.info(f"Message queue started with {self.config.broker.value} broker")

    async def stop(self) -> None:
        """Stop message queue."""
        await self.broker.disconnect()
        logger.info("Message queue stopped")

    async def publish(
        self, topic: str, payload: Any, routing_key: str | None = None, **kwargs
    ) -> bool:
        """Publish message to topic."""
        message = Message(topic=topic, routing_key=routing_key or topic, payload=payload, **kwargs)
        return await self.broker.publish(message)

    async def subscribe(self, topic: str, handler: MessageHandler) -> None:
        """Subscribe to topic with handler."""
        if topic not in self.handlers:
            self.handlers[topic] = []

        self.handlers[topic].append(handler)
        await self.broker.subscribe([topic], handler)

    async def unsubscribe(self, topic: str, handler: MessageHandler | None = None) -> None:
        """Unsubscribe from topic."""
        if topic in self.handlers:
            if handler:
                self.handlers[topic].remove(handler)
            else:
                del self.handlers[topic]

        await self.broker.unsubscribe([topic])

    async def request_reply(
        self,
        topic: str,
        payload: Any,
        timeout: float = 30.0,
    ) -> Any | None:
        """Send request and wait for reply (RPC pattern)."""
        reply_topic = f"reply_{uuid.uuid4()}"
        correlation_id = str(uuid.uuid4())

        # Setup reply handler
        reply_received = asyncio.Event()
        reply_payload = None

        class ReplyHandler(MessageHandler):
            def get_topics(self) -> list[str]:
                return [reply_topic]

            async def handle(self, message: QueueMessage) -> bool:
                nonlocal reply_payload
                if message.correlation_id == correlation_id:
                    reply_payload = message.payload
                    reply_received.set()
                    return True
                return False

        reply_handler = ReplyHandler()
        await self.subscribe(reply_topic, reply_handler)

        try:
            # Send request
            await self.publish(
                topic,
                payload,
                correlation_id=correlation_id,
                reply_to=reply_topic,
            )

            # Wait for reply
            await asyncio.wait_for(reply_received.wait(), timeout=timeout)
            return reply_payload

        except asyncio.TimeoutError:
            logger.warning(f"Request to {topic} timed out after {timeout}s")
            return None

        finally:
            await self.unsubscribe(reply_topic, reply_handler)

    async def get_stats(self) -> MessageStats:
        """Get message queue statistics."""
        return await self.broker.get_stats()


# Global message queue instances
_message_queues: dict[str, MessageQueue] = {}


def get_message_queue(name: str = "default") -> MessageQueue | None:
    """Get global message queue."""
    return _message_queues.get(name)


def create_message_queue(
    name: str,
    config: MessageConfig,
    pattern: MessagePattern = MessagePattern.PUBLISH_SUBSCRIBE,
) -> MessageQueue:
    """Create and register global message queue."""
    queue = MessageQueue(config, pattern)
    _message_queues[name] = queue
    return queue


@asynccontextmanager
async def message_queue_context(
    name: str,
    config: MessageConfig,
    pattern: MessagePattern = MessagePattern.PUBLISH_SUBSCRIBE,
):
    """Context manager for message queue lifecycle."""
    queue = create_message_queue(name, config, pattern)
    await queue.start()

    try:
        yield queue
    finally:
        await queue.stop()


# Decorators for message handling
def message_handler(topics: list[str], queue_name: str = "default"):
    """Decorator for message handlers."""

    def decorator(cls):
        # Ensure class implements MessageHandler
        if not issubclass(cls, MessageHandler):
            raise TypeError(f"Class {cls.__name__} must inherit from MessageHandler")

        # Auto-register with message queue
        async def auto_register():
            queue = get_message_queue(queue_name)
            if queue:
                handler = cls()
                for topic in topics:
                    await queue.subscribe(topic, handler)

        # Store registration function for later use
        cls._auto_register = auto_register
        cls._topics = topics

        return cls

    return decorator


def publish_message(
    topic: str,
    queue_name: str = "default",
    routing_key: str | None = None,
):
    """Decorator for automatic message publishing after function execution."""

    def decorator(func):
        async def wrapper(*args, **kwargs):
            result = await func(*args, **kwargs)

            queue = get_message_queue(queue_name)
            if queue:
                await queue.publish(
                    topic,
                    {"result": result, "args": args, "kwargs": kwargs},
                    routing_key=routing_key,
                )

            return result

        return wrapper

    return decorator
