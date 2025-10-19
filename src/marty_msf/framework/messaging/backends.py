"""
Message Queue Backend Implementations

Provides backend implementations for various message queue systems including
RabbitMQ, Redis, AWS SQS, and in-memory queues.
"""

import builtins
import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aio_pika
import redis.asyncio as redis

from .core import ExchangeConfig, Message, MessageExchange, MessageQueue, QueueConfig

logger = logging.getLogger(__name__)


class BackendType(Enum):
    """Message queue backend types."""

    MEMORY = "memory"
    RABBITMQ = "rabbitmq"
    REDIS = "redis"
    AWS_SQS = "aws_sqs"
    KAFKA = "kafka"


@dataclass
class BackendConfig:
    """Base configuration for message queue backends."""

    backend_type: BackendType
    name: str = "default"

    # Connection settings
    host: str = "localhost"
    port: int = 5672
    username: str | None = None
    password: str | None = None
    virtual_host: str = "/"

    # Connection pool
    max_connections: int = 10
    connection_timeout: float = 30.0
    heartbeat: int = 600

    # Reliability
    enable_ssl: bool = False
    ssl_cert_path: str | None = None
    ssl_key_path: str | None = None

    # Performance
    max_frame_size: int = 131072
    channel_max: int = 2047

    # Additional backend-specific settings
    options: builtins.dict[str, Any] = None

    def __post_init__(self):
        if self.options is None:
            self.options = {}


class MessageBackend(ABC):
    """Abstract message queue backend."""

    def __init__(self, config: BackendConfig):
        self.config = config
        self._connected = False
        self._connection = None

    @abstractmethod
    async def connect(self):
        """Connect to message queue backend."""

    @abstractmethod
    async def disconnect(self):
        """Disconnect from message queue backend."""

    @abstractmethod
    async def create_queue(self, config: QueueConfig) -> MessageQueue:
        """Create a message queue."""

    @abstractmethod
    async def create_exchange(self, config: ExchangeConfig) -> MessageExchange:
        """Create a message exchange."""

    @abstractmethod
    async def publish(self, message: Message) -> bool:
        """Publish a message."""

    @abstractmethod
    async def consume(self, queue: str, timeout: float | None = None) -> Message | None:
        """Consume a message from queue."""

    @abstractmethod
    async def ack(self, message: Message) -> bool:
        """Acknowledge message processing."""

    @abstractmethod
    async def nack(self, message: Message, requeue: bool = True) -> bool:
        """Negative acknowledge message."""

    @abstractmethod
    async def send_to_dlq(self, message: Message) -> bool:
        """Send message to dead letter queue."""

    @property
    def is_connected(self) -> bool:
        """Check if backend is connected."""
        return self._connected


class InMemoryBackend(MessageBackend):
    """In-memory message queue backend for testing and development."""

    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._queues: builtins.dict[str, builtins.list[Message]] = {}
        self._exchanges: builtins.dict[str, builtins.dict[str, Any]] = {}
        self._dlq: builtins.list[Message] = []
        self._queue_configs: builtins.dict[str, QueueConfig] = {}
        self._exchange_configs: builtins.dict[str, ExchangeConfig] = {}

    async def connect(self):
        """Connect to in-memory backend."""
        self._connected = True
        logger.info("Connected to in-memory message backend")

    async def disconnect(self):
        """Disconnect from in-memory backend."""
        self._connected = False
        self._queues.clear()
        self._exchanges.clear()
        self._dlq.clear()
        logger.info("Disconnected from in-memory message backend")

    async def create_queue(self, config: QueueConfig) -> MessageQueue:
        """Create an in-memory queue."""
        if config.name not in self._queues:
            self._queues[config.name] = []
            self._queue_configs[config.name] = config
            logger.info(f"Created in-memory queue: {config.name}")

        return InMemoryQueue(config, self)

    async def create_exchange(self, config: ExchangeConfig) -> MessageExchange:
        """Create an in-memory exchange."""
        if config.name not in self._exchanges:
            self._exchanges[config.name] = {
                "type": config.exchange_type,
                "bindings": {},
            }
            self._exchange_configs[config.name] = config
            logger.info(f"Created in-memory exchange: {config.name}")

        return InMemoryExchange(config, self)

    async def publish(self, message: Message) -> bool:
        """Publish message to queue or exchange."""
        try:
            exchange_name = message.headers.exchange
            routing_key = message.headers.routing_key

            if exchange_name and exchange_name in self._exchanges:
                # Route through exchange
                await self._route_through_exchange(message, exchange_name, routing_key)
            elif routing_key in self._queues:
                # Direct queue publish
                self._queues[routing_key].append(message)
                message.mark_published()
            else:
                logger.warning(f"No queue or exchange found for routing key: {routing_key}")
                return False

            return True

        except Exception as e:
            logger.error(f"Failed to publish message: {e}")
            return False

    async def _route_through_exchange(self, message: Message, exchange_name: str, routing_key: str):
        """Route message through exchange."""
        exchange = self._exchanges[exchange_name]
        exchange_type = exchange["type"]

        if exchange_type == "direct":
            # Direct routing
            if routing_key in exchange["bindings"]:
                for queue_name in exchange["bindings"][routing_key]:
                    if queue_name in self._queues:
                        self._queues[queue_name].append(message)

        elif exchange_type == "fanout":
            # Broadcast to all bound queues
            for binding_queues in exchange["bindings"].values():
                for queue_name in binding_queues:
                    if queue_name in self._queues:
                        self._queues[queue_name].append(message)

        elif exchange_type == "topic":
            # Topic pattern matching (simplified)
            for binding_key, queue_names in exchange["bindings"].items():
                if self._matches_topic_pattern(routing_key, binding_key):
                    for queue_name in queue_names:
                        if queue_name in self._queues:
                            self._queues[queue_name].append(message)

        message.mark_published()

    def _matches_topic_pattern(self, routing_key: str, pattern: str) -> bool:
        """Simple topic pattern matching."""
        if pattern == "*":
            return True
        if pattern == routing_key:
            return True
        # Add more sophisticated pattern matching as needed
        return False

    async def consume(self, queue: str, timeout: float | None = None) -> Message | None:
        """Consume message from queue."""
        if queue not in self._queues:
            return None

        queue_list = self._queues[queue]

        if not queue_list:
            return None

        # Get highest priority message
        message = max(queue_list, key=lambda m: m.headers.priority.value)
        queue_list.remove(message)

        message.mark_delivered()
        return message

    async def ack(self, message: Message) -> bool:
        """Acknowledge message."""
        message.mark_completed()
        return True

    async def nack(self, message: Message, requeue: bool = True) -> bool:
        """Negative acknowledge message."""
        if requeue and message.headers.routing_key in self._queues:
            # Requeue message
            self._queues[message.headers.routing_key].append(message)
            message.status = message.status.PENDING
        else:
            message.mark_failed()

        return True

    async def send_to_dlq(self, message: Message) -> bool:
        """Send message to dead letter queue."""
        self._dlq.append(message)
        message.mark_failed()
        logger.info(f"Message {message.id} sent to DLQ")
        return True

    def bind_queue(self, exchange_name: str, queue_name: str, routing_key: str):
        """Bind queue to exchange."""
        if exchange_name in self._exchanges:
            bindings = self._exchanges[exchange_name]["bindings"]
            if routing_key not in bindings:
                bindings[routing_key] = []
            if queue_name not in bindings[routing_key]:
                bindings[routing_key].append(queue_name)


class InMemoryQueue(MessageQueue):
    """In-memory queue implementation."""

    def __init__(self, config: QueueConfig, backend: InMemoryBackend):
        super().__init__(config)
        self.backend = backend

    async def publish(self, message: Message) -> bool:
        """Publish message to queue."""
        message.headers.routing_key = self.config.name
        return await self.backend.publish(message)

    async def consume(self, timeout: float | None = None) -> Message | None:
        """Consume message from queue."""
        return await self.backend.consume(self.config.name, timeout)

    async def purge(self) -> int:
        """Purge all messages from queue."""
        if self.config.name in self.backend._queues:
            count = len(self.backend._queues[self.config.name])
            self.backend._queues[self.config.name].clear()
            return count
        return 0

    async def get_message_count(self) -> int:
        """Get number of messages in queue."""
        if self.config.name in self.backend._queues:
            return len(self.backend._queues[self.config.name])
        return 0


class InMemoryExchange(MessageExchange):
    """In-memory exchange implementation."""

    def __init__(self, config: ExchangeConfig, backend: InMemoryBackend):
        super().__init__(config)
        self.backend = backend

    async def publish(self, message: Message) -> bool:
        """Publish message to exchange."""
        message.headers.exchange = self.config.name
        return await self.backend.publish(message)

    async def bind_queue(self, queue_name: str, routing_key: str):
        """Bind queue to exchange."""
        self.backend.bind_queue(self.config.name, queue_name, routing_key)


# RabbitMQ Backend (requires aio-pika)
class RabbitMQBackend(MessageBackend):
    """RabbitMQ message queue backend."""

    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._connection = None
        self._channel = None
        self._queues: builtins.dict[str, Any] = {}
        self._exchanges: builtins.dict[str, Any] = {}

    async def connect(self):
        """Connect to RabbitMQ."""
        try:

            connection_url = self._build_connection_url()
            self._connection = await aio_pika.connect_robust(
                connection_url,
                timeout=self.config.connection_timeout,
                heartbeat=self.config.heartbeat,
            )

            self._channel = await self._connection.channel()
            await self._channel.set_qos(prefetch_count=100)

            self._connected = True
            logger.info(f"Connected to RabbitMQ at {self.config.host}:{self.config.port}")

        except ImportError:
            raise RuntimeError("aio-pika package required for RabbitMQ backend")
        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {e}")
            raise

    async def disconnect(self):
        """Disconnect from RabbitMQ."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            self._channel = None
            self._connected = False
            logger.info("Disconnected from RabbitMQ")

    def _build_connection_url(self) -> str:
        """Build RabbitMQ connection URL."""
        auth = ""
        if self.config.username and self.config.password:
            auth = f"{self.config.username}:{self.config.password}@"

        return f"amqp://{auth}{self.config.host}:{self.config.port}/{self.config.virtual_host}"

    async def create_queue(self, config: QueueConfig) -> MessageQueue:
        """Create RabbitMQ queue."""

        queue = await self._channel.declare_queue(
            config.name,
            durable=config.durable,
            auto_delete=config.auto_delete,
            arguments=config.arguments or {},
        )

        self._queues[config.name] = queue
        logger.info(f"Created RabbitMQ queue: {config.name}")

        return RabbitMQQueue(config, self, queue)

    async def create_exchange(self, config: ExchangeConfig) -> MessageExchange:
        """Create RabbitMQ exchange."""

        exchange_type = getattr(aio_pika.ExchangeType, config.exchange_type.upper())

        exchange = await self._channel.declare_exchange(
            config.name,
            exchange_type,
            durable=config.durable,
            auto_delete=config.auto_delete,
        )

        self._exchanges[config.name] = exchange
        logger.info(f"Created RabbitMQ exchange: {config.name}")

        return RabbitMQExchange(config, self, exchange)

    async def publish(self, message: Message) -> bool:
        """Publish message to RabbitMQ."""
        try:

            # Create AMQP message
            amqp_message = aio_pika.Message(
                body=message.body
                if isinstance(message.body, bytes)
                else str(message.body).encode(),
                headers=message.headers.custom,
                priority=message.headers.priority.value,
                correlation_id=message.headers.correlation_id,
                reply_to=message.headers.reply_to,
                expiration=int(message.headers.expiration * 1000)
                if message.headers.expiration
                else None,
                message_id=message.id,
            )

            exchange_name = message.headers.exchange or ""
            routing_key = message.headers.routing_key

            # Get exchange
            if exchange_name and exchange_name in self._exchanges:
                exchange = self._exchanges[exchange_name]
            else:
                exchange = self._channel.default_exchange

            # Publish message
            await exchange.publish(amqp_message, routing_key=routing_key)
            message.mark_published()

            return True

        except Exception as e:
            logger.error(f"Failed to publish message to RabbitMQ: {e}")
            return False

    async def consume(self, queue: str, timeout: float | None = None) -> Message | None:
        """Consume message from RabbitMQ queue."""
        if queue not in self._queues:
            return None

        try:
            amqp_queue = self._queues[queue]
            amqp_message = await amqp_queue.get(timeout=timeout)

            if amqp_message:
                # Convert to framework message
                message = Message(
                    id=amqp_message.message_id or str(uuid.uuid4()),
                    body=amqp_message.body,
                )

                # Set headers
                message.headers.correlation_id = amqp_message.correlation_id
                message.headers.reply_to = amqp_message.reply_to
                message.headers.priority = amqp_message.priority or 0
                message.headers.custom.update(amqp_message.headers or {})

                # Store AMQP message for ack/nack
                message._amqp_message = amqp_message
                message.mark_delivered()

                return message

        except Exception as e:
            logger.error(f"Failed to consume from RabbitMQ queue {queue}: {e}")

        return None

    async def ack(self, message: Message) -> bool:
        """Acknowledge RabbitMQ message."""
        try:
            if hasattr(message, "_amqp_message"):
                await message._amqp_message.ack()
                message.mark_completed()
                return True
        except Exception as e:
            logger.error(f"Failed to ack RabbitMQ message: {e}")

        return False

    async def nack(self, message: Message, requeue: bool = True) -> bool:
        """Negative acknowledge RabbitMQ message."""
        try:
            if hasattr(message, "_amqp_message"):
                await message._amqp_message.nack(requeue=requeue)
                if not requeue:
                    message.mark_failed()
                return True
        except Exception as e:
            logger.error(f"Failed to nack RabbitMQ message: {e}")

        return False

    async def send_to_dlq(self, message: Message) -> bool:
        """Send message to RabbitMQ dead letter queue."""
        # Implementation depends on DLQ configuration
        # This is a simplified version
        try:
            dlq_name = f"{message.headers.routing_key}.dlq"

            if dlq_name not in self._queues:
                # Create DLQ if it doesn't exist
                config = QueueConfig(name=dlq_name, durable=True)
                await self.create_queue(config)

            # Republish to DLQ
            message.headers.routing_key = dlq_name
            message.headers.custom["original_queue"] = message.headers.routing_key
            message.headers.custom["dlq_timestamp"] = time.time()

            return await self.publish(message)

        except Exception as e:
            logger.error(f"Failed to send message to DLQ: {e}")
            return False


class RabbitMQQueue(MessageQueue):
    """RabbitMQ queue implementation."""

    def __init__(self, config: QueueConfig, backend: RabbitMQBackend, amqp_queue):
        super().__init__(config)
        self.backend = backend
        self.amqp_queue = amqp_queue

    async def publish(self, message: Message) -> bool:
        """Publish message to queue."""
        message.headers.routing_key = self.config.name
        return await self.backend.publish(message)

    async def consume(self, timeout: float | None = None) -> Message | None:
        """Consume message from queue."""
        return await self.backend.consume(self.config.name, timeout)

    async def purge(self) -> int:
        """Purge all messages from queue."""
        try:
            return await self.amqp_queue.purge()
        except Exception as e:
            logger.error(f"Failed to purge RabbitMQ queue: {e}")
            return 0

    async def get_message_count(self) -> int:
        """Get number of messages in queue."""
        try:
            declaration = await self.amqp_queue.declare(passive=True)
            return declaration.message_count
        except Exception as e:
            logger.error(f"Failed to get RabbitMQ queue message count: {e}")
            return 0


class RabbitMQExchange(MessageExchange):
    """RabbitMQ exchange implementation."""

    def __init__(self, config: ExchangeConfig, backend: RabbitMQBackend, amqp_exchange):
        super().__init__(config)
        self.backend = backend
        self.amqp_exchange = amqp_exchange

    async def publish(self, message: Message) -> bool:
        """Publish message to exchange."""
        message.headers.exchange = self.config.name
        return await self.backend.publish(message)

    async def bind_queue(self, queue_name: str, routing_key: str):
        """Bind queue to exchange."""
        try:
            if queue_name in self.backend._queues:
                queue = self.backend._queues[queue_name]
                await queue.bind(self.amqp_exchange, routing_key=routing_key)
                logger.info(
                    f"Bound queue {queue_name} to exchange {self.config.name} with routing key {routing_key}"
                )
        except Exception as e:
            logger.error(f"Failed to bind queue to exchange: {e}")


# Redis Backend (requires aioredis)
class RedisBackend(MessageBackend):
    """Redis message queue backend using streams or lists."""

    def __init__(self, config: BackendConfig):
        super().__init__(config)
        self._redis = None
        self._use_streams = config.options.get("use_streams", True)

    async def connect(self):
        """Connect to Redis."""
        try:

            self._redis = redis.from_url(
                f"redis://{self.config.host}:{self.config.port}",
                username=self.config.username,
                password=self.config.password,
                encoding="utf-8",
                decode_responses=False,  # We handle serialization ourselves
            )

            # Test connection
            await self._redis.ping()

            self._connected = True
            logger.info(f"Connected to Redis at {self.config.host}:{self.config.port}")

        except ImportError:
            raise RuntimeError("redis package required for Redis backend")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            raise

    async def disconnect(self):
        """Disconnect from Redis."""
        if self._redis:
            await self._redis.close()
            self._redis = None
            self._connected = False
            logger.info("Disconnected from Redis")

    async def create_queue(self, config: QueueConfig) -> MessageQueue:
        """Create Redis queue."""
        # Redis queues are created implicitly
        logger.info(f"Created Redis queue: {config.name}")
        return RedisQueue(config, self)

    async def create_exchange(self, config: ExchangeConfig) -> MessageExchange:
        """Create Redis exchange (using pub/sub)."""
        logger.info(f"Created Redis exchange: {config.name}")
        return RedisExchange(config, self)

    async def publish(self, message: Message) -> bool:
        """Publish message to Redis."""
        try:
            queue_name = message.headers.routing_key

            # Serialize message
            message_data = {
                "id": message.id,
                "body": message.body,
                "headers": message.headers.__dict__,
                "timestamp": message.timestamp,
                "status": message.status.value,
            }

            serialized = json.dumps(message_data).encode()

            if self._use_streams:
                # Use Redis streams
                await self._redis.xadd(
                    f"queue:{queue_name}", fields={"message": serialized}, id="*"
                )
            else:
                # Use Redis lists
                await self._redis.lpush(f"queue:{queue_name}", serialized)

            message.mark_published()
            return True

        except Exception as e:
            logger.error(f"Failed to publish message to Redis: {e}")
            return False

    async def consume(self, queue: str, timeout: float | None = None) -> Message | None:
        """Consume message from Redis queue."""
        try:
            if self._use_streams:
                # Use Redis streams
                timeout_ms = int(timeout * 1000) if timeout else 1000

                result = await self._redis.xread(
                    streams={f"queue:{queue}": "$"}, count=1, block=timeout_ms
                )

                if result:
                    stream_name, messages = result[0]
                    if messages:
                        message_id, fields = messages[0]
                        message_data = json.loads(fields[b"message"])
                        return self._deserialize_message(message_data)

            else:
                # Use Redis lists
                timeout_int = int(timeout) if timeout else 1

                result = await self._redis.brpop(keys=[f"queue:{queue}"], timeout=timeout_int)

                if result:
                    queue_name, message_data = result
                    message_dict = json.loads(message_data)
                    return self._deserialize_message(message_dict)

        except Exception as e:
            logger.error(f"Failed to consume from Redis queue {queue}: {e}")

        return None

    def _deserialize_message(self, message_data: builtins.dict[str, Any]) -> Message:
        """Deserialize message from Redis."""
        message = Message(id=message_data["id"], body=message_data["body"])

        # Restore headers
        headers_data = message_data["headers"]
        for key, value in headers_data.items():
            if hasattr(message.headers, key):
                setattr(message.headers, key, value)

        message.timestamp = message_data["timestamp"]
        message.mark_delivered()

        return message

    async def ack(self, message: Message) -> bool:
        """Acknowledge Redis message."""
        # Redis doesn't have built-in ack, so we just mark as completed
        message.mark_completed()
        return True

    async def nack(self, message: Message, requeue: bool = True) -> bool:
        """Negative acknowledge Redis message."""
        if requeue:
            # Republish message
            return await self.publish(message)
        message.mark_failed()
        return True

    async def send_to_dlq(self, message: Message) -> bool:
        """Send message to Redis dead letter queue."""
        try:
            dlq_name = f"{message.headers.routing_key}.dlq"

            # Add DLQ metadata
            message.headers.custom["original_queue"] = message.headers.routing_key
            message.headers.custom["dlq_timestamp"] = time.time()
            message.headers.routing_key = dlq_name

            return await self.publish(message)

        except Exception as e:
            logger.error(f"Failed to send message to Redis DLQ: {e}")
            return False


class RedisQueue(MessageQueue):
    """Redis queue implementation."""

    def __init__(self, config: QueueConfig, backend: RedisBackend):
        super().__init__(config)
        self.backend = backend

    async def publish(self, message: Message) -> bool:
        """Publish message to queue."""
        message.headers.routing_key = self.config.name
        return await self.backend.publish(message)

    async def consume(self, timeout: float | None = None) -> Message | None:
        """Consume message from queue."""
        return await self.backend.consume(self.config.name, timeout)

    async def purge(self) -> int:
        """Purge all messages from queue."""
        try:
            count = await self.backend._redis.llen(f"queue:{self.config.name}")
            await self.backend._redis.delete(f"queue:{self.config.name}")
            return count
        except Exception as e:
            logger.error(f"Failed to purge Redis queue: {e}")
            return 0

    async def get_message_count(self) -> int:
        """Get number of messages in queue."""
        try:
            if self.backend._use_streams:
                return await self.backend._redis.xlen(f"queue:{self.config.name}")
            return await self.backend._redis.llen(f"queue:{self.config.name}")
        except Exception as e:
            logger.error(f"Failed to get Redis queue message count: {e}")
            return 0


class RedisExchange(MessageExchange):
    """Redis exchange implementation using pub/sub."""

    def __init__(self, config: ExchangeConfig, backend: RedisBackend):
        super().__init__(config)
        self.backend = backend

    async def publish(self, message: Message) -> bool:
        """Publish message to exchange."""
        try:
            # Use Redis pub/sub for exchange
            channel_name = f"exchange:{self.config.name}:{message.headers.routing_key}"

            message_data = {
                "id": message.id,
                "body": message.body,
                "headers": message.headers.__dict__,
                "timestamp": message.timestamp,
            }

            serialized = json.dumps(message_data)
            await self.backend._redis.publish(channel_name, serialized)

            message.mark_published()
            return True

        except Exception as e:
            logger.error(f"Failed to publish to Redis exchange: {e}")
            return False

    async def bind_queue(self, queue_name: str, routing_key: str):
        """Bind queue to exchange."""
        # In Redis, binding is handled by subscribing to the appropriate channel
        # This would typically be done in the consumer setup
        logger.info(
            f"Bound queue {queue_name} to exchange {self.config.name} with routing key {routing_key}"
        )


# Backend Factory
class BackendFactory:
    """Factory for creating message queue backends."""

    @staticmethod
    def create_backend(config: BackendConfig) -> MessageBackend:
        """Create a message queue backend."""
        backend_map = {
            BackendType.MEMORY: InMemoryBackend,
            BackendType.RABBITMQ: RabbitMQBackend,
            BackendType.REDIS: RedisBackend,
        }

        backend_class = backend_map.get(config.backend_type)

        if not backend_class:
            raise ValueError(f"Unsupported backend type: {config.backend_type}")

        return backend_class(config)
