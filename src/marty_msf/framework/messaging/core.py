"""
Core Message Queue Abstractions

Provides fundamental message and queue abstractions that form the foundation
of the messaging framework.
"""

import builtins
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .backends import BackendConfig, BackendType
from .manager import MessagingConfig, MessagingManager

logger = logging.getLogger(__name__)


class MessagePriority(Enum):
    """Message priority levels."""

    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 15


class MessageStatus(Enum):
    """Message processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    RETRYING = "retrying"


class ExchangeType(Enum):
    """Exchange types for message routing."""

    DIRECT = "direct"
    TOPIC = "topic"
    FANOUT = "fanout"
    HEADERS = "headers"


@dataclass
class MessageHeaders:
    """Message headers container."""

    # Standard headers
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: str | None = None
    timestamp: float = field(default_factory=time.time)
    content_type: str = "application/json"
    content_encoding: str = "utf-8"
    priority: MessagePriority = MessagePriority.NORMAL
    expiration: float | None = None
    reply_to: str | None = None

    # Routing headers
    routing_key: str | None = None
    exchange: str | None = None

    # Processing headers
    retry_count: int = 0
    max_retries: int = 3
    delay_seconds: float = 0.0

    # Custom headers
    custom: builtins.dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if message has expired."""
        if self.expiration is None:
            return False
        return time.time() > (self.timestamp + self.expiration)

    def should_retry(self) -> bool:
        """Check if message should be retried."""
        return self.retry_count < self.max_retries

    def increment_retry(self):
        """Increment retry counter."""
        self.retry_count += 1

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert headers to dictionary."""
        return {
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "timestamp": self.timestamp,
            "content_type": self.content_type,
            "content_encoding": self.content_encoding,
            "priority": self.priority.value,
            "expiration": self.expiration,
            "reply_to": self.reply_to,
            "routing_key": self.routing_key,
            "exchange": self.exchange,
            "retry_count": self.retry_count,
            "max_retries": self.max_retries,
            "delay_seconds": self.delay_seconds,
            "custom": self.custom,
        }

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "MessageHeaders":
        """Create headers from dictionary."""
        headers = cls()
        headers.message_id = data.get("message_id", headers.message_id)
        headers.correlation_id = data.get("correlation_id")
        headers.timestamp = data.get("timestamp", headers.timestamp)
        headers.content_type = data.get("content_type", headers.content_type)
        headers.content_encoding = data.get("content_encoding", headers.content_encoding)
        headers.priority = MessagePriority(data.get("priority", headers.priority.value))
        headers.expiration = data.get("expiration")
        headers.reply_to = data.get("reply_to")
        headers.routing_key = data.get("routing_key")
        headers.exchange = data.get("exchange")
        headers.retry_count = data.get("retry_count", headers.retry_count)
        headers.max_retries = data.get("max_retries", headers.max_retries)
        headers.delay_seconds = data.get("delay_seconds", headers.delay_seconds)
        headers.custom = data.get("custom", {})
        return headers


@dataclass
class Message:
    """Core message abstraction."""

    body: Any
    headers: MessageHeaders = field(default_factory=MessageHeaders)
    status: MessageStatus = MessageStatus.PENDING

    def __post_init__(self):
        """Initialize message after creation."""
        if not self.headers.message_id:
            self.headers.message_id = str(uuid.uuid4())

    @property
    def id(self) -> str:
        """Get message ID."""
        return self.headers.message_id

    @property
    def correlation_id(self) -> str | None:
        """Get correlation ID."""
        return self.headers.correlation_id

    @property
    def routing_key(self) -> str | None:
        """Get routing key."""
        return self.headers.routing_key

    @property
    def priority(self) -> MessagePriority:
        """Get message priority."""
        return self.headers.priority

    def is_expired(self) -> bool:
        """Check if message has expired."""
        return self.headers.is_expired()

    def should_retry(self) -> bool:
        """Check if message should be retried."""
        return self.headers.should_retry()

    def mark_processing(self):
        """Mark message as being processed."""
        self.status = MessageStatus.PROCESSING

    def mark_completed(self):
        """Mark message as completed."""
        self.status = MessageStatus.COMPLETED

    def mark_failed(self):
        """Mark message as failed."""
        self.status = MessageStatus.FAILED
        self.headers.increment_retry()

    def mark_dead_letter(self):
        """Mark message as dead letter."""
        self.status = MessageStatus.DEAD_LETTER

    def to_dict(self) -> builtins.dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "body": self.body,
            "headers": self.headers.to_dict(),
            "status": self.status.value,
        }

    @classmethod
    def from_dict(cls, data: builtins.dict[str, Any]) -> "Message":
        """Create message from dictionary."""
        return cls(
            body=data["body"],
            headers=MessageHeaders.from_dict(data["headers"]),
            status=MessageStatus(data["status"]),
        )


@dataclass
class QueueConfig:
    """Configuration for message queues."""

    name: str
    durable: bool = True
    auto_delete: bool = False
    exclusive: bool = False
    max_length: int | None = None
    max_priority: int = 15
    message_ttl: int | None = None
    dead_letter_exchange: str | None = None
    dead_letter_routing_key: str | None = None
    arguments: builtins.dict[str, Any] = field(default_factory=dict)


@dataclass
class ExchangeConfig:
    """Configuration for message exchanges."""

    name: str
    exchange_type: ExchangeType = ExchangeType.DIRECT
    durable: bool = True
    auto_delete: bool = False
    internal: bool = False
    arguments: builtins.dict[str, Any] = field(default_factory=dict)


class MessageQueue(ABC):
    """Abstract base class for message queues."""

    def __init__(self, config: QueueConfig):
        self.config = config
        self.name = config.name

        # Metrics
        self._message_count = 0
        self._consumer_count = 0
        self._published_count = 0
        self._consumed_count = 0
        self._failed_count = 0

    @abstractmethod
    async def publish(self, message: Message) -> bool:
        """Publish a message to the queue."""

    @abstractmethod
    async def consume(self, timeout: float | None = None) -> Message | None:
        """Consume a message from the queue."""

    @abstractmethod
    async def ack(self, message: Message) -> bool:
        """Acknowledge message processing."""

    @abstractmethod
    async def nack(self, message: Message, requeue: bool = True) -> bool:
        """Negative acknowledge message."""

    @abstractmethod
    async def purge(self) -> int:
        """Purge all messages from queue."""

    @abstractmethod
    async def delete(self) -> bool:
        """Delete the queue."""

    @abstractmethod
    async def get_message_count(self) -> int:
        """Get number of messages in queue."""

    @abstractmethod
    async def get_consumer_count(self) -> int:
        """Get number of active consumers."""

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get queue statistics."""
        return {
            "name": self.name,
            "config": {
                "durable": self.config.durable,
                "auto_delete": self.config.auto_delete,
                "max_length": self.config.max_length,
                "max_priority": self.config.max_priority,
            },
            "metrics": {
                "message_count": self._message_count,
                "consumer_count": self._consumer_count,
                "published_count": self._published_count,
                "consumed_count": self._consumed_count,
                "failed_count": self._failed_count,
            },
        }


class MessageExchange(ABC):
    """Abstract base class for message exchanges."""

    def __init__(self, config: ExchangeConfig):
        self.config = config
        self.name = config.name
        self.exchange_type = config.exchange_type

        # Bound queues
        self._bindings: builtins.dict[str, builtins.list[str]] = {}  # routing_key -> queue_names

        # Metrics
        self._published_count = 0
        self._routed_count = 0
        self._unrouted_count = 0

    @abstractmethod
    async def publish(self, message: Message, routing_key: str = "") -> bool:
        """Publish message to exchange."""

    @abstractmethod
    async def bind_queue(self, queue_name: str, routing_key: str = "") -> bool:
        """Bind queue to exchange."""

    @abstractmethod
    async def unbind_queue(self, queue_name: str, routing_key: str = "") -> bool:
        """Unbind queue from exchange."""

    @abstractmethod
    async def delete(self) -> bool:
        """Delete the exchange."""

    def get_bindings(self) -> builtins.dict[str, builtins.list[str]]:
        """Get exchange bindings."""
        return self._bindings.copy()

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get exchange statistics."""
        return {
            "name": self.name,
            "type": self.exchange_type.value,
            "config": {
                "durable": self.config.durable,
                "auto_delete": self.config.auto_delete,
                "internal": self.config.internal,
            },
            "bindings": self._bindings,
            "metrics": {
                "published_count": self._published_count,
                "routed_count": self._routed_count,
                "unrouted_count": self._unrouted_count,
            },
        }


class QueueManager(ABC):
    """Abstract base class for queue managers."""

    def __init__(self):
        self._queues: builtins.dict[str, MessageQueue] = {}
        self._exchanges: builtins.dict[str, MessageExchange] = {}

    @abstractmethod
    async def create_queue(self, config: QueueConfig) -> MessageQueue:
        """Create a new queue."""

    @abstractmethod
    async def create_exchange(self, config: ExchangeConfig) -> MessageExchange:
        """Create a new exchange."""

    @abstractmethod
    async def delete_queue(self, name: str) -> bool:
        """Delete a queue."""

    @abstractmethod
    async def delete_exchange(self, name: str) -> bool:
        """Delete an exchange."""

    async def get_queue(self, name: str) -> MessageQueue | None:
        """Get queue by name."""
        return self._queues.get(name)

    async def get_exchange(self, name: str) -> MessageExchange | None:
        """Get exchange by name."""
        return self._exchanges.get(name)

    async def list_queues(self) -> builtins.list[str]:
        """List all queue names."""
        return list(self._queues.keys())

    async def list_exchanges(self) -> builtins.list[str]:
        """List all exchange names."""
        return list(self._exchanges.keys())

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to message broker."""

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from message broker."""

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected to message broker."""

    def get_stats(self) -> builtins.dict[str, Any]:
        """Get manager statistics."""
        queue_stats = {}
        exchange_stats = {}

        for name, queue in self._queues.items():
            queue_stats[name] = queue.get_stats()

        for name, exchange in self._exchanges.items():
            exchange_stats[name] = exchange.get_stats()

        return {
            "queues": queue_stats,
            "exchanges": exchange_stats,
            "total_queues": len(self._queues),
            "total_exchanges": len(self._exchanges),
        }


class MessageBus:
    """
    Simple MessageBus interface that wraps MessagingManager.

    This provides a simpler interface for basic messaging operations
    while maintaining compatibility with existing test code.
    """

    def __init__(self, service_name: str, config: dict[str, Any] | None = None):
        """Initialize MessageBus with service name and configuration."""
        # Import here to avoid circular imports

        if config is None:
            config = {}

        # Create a backend config from the provided config
        backend_config = BackendConfig(
            backend_type=BackendType.KAFKA,  # Default to Kafka
            **config,
        )

        messaging_config = MessagingConfig(backend_config=backend_config)
        self._manager = MessagingManager(messaging_config)
        self._service_name = service_name

    async def start(self) -> None:
        """Start the messaging system."""
        await self._manager.initialize()

    async def stop(self) -> None:
        """Stop the messaging system."""
        await self._manager.shutdown()

    async def publish(self, topic: str, message: Any, **kwargs) -> None:
        """Publish a message to a topic."""
        await self._manager.publish(topic, message, **kwargs)

    async def subscribe(self, topic: str, handler, **kwargs) -> None:
        """Subscribe to a topic with a handler."""
        # This is a simplified interface - in practice you'd need to create
        # proper consumer configurations
        raise NotImplementedError("Subscribe functionality needs to be implemented")
