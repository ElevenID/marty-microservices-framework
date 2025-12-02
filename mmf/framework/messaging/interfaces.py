"""
Messaging Interfaces

This module defines the interfaces (ports) for the messaging system.
It serves as the contract for the messaging framework components.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any, Protocol, runtime_checkable

from mmf.framework.messaging.domain.models import (
    ConsumerConfig,
    ExchangeConfig,
    Message,
    MiddlewareStage,
    ProducerConfig,
    QueueConfig,
    RoutingRule,
)


@runtime_checkable
class IMessageSerializer(Protocol):
    """Protocol for message serialization."""

    def serialize(self, data: Any) -> bytes:
        """Serialize data to bytes."""
        ...

    def deserialize(self, data: bytes) -> Any:
        """Deserialize bytes to data."""
        ...

    def get_content_type(self) -> str:
        """Get content type for serialized data."""
        ...


class IMessageQueue(ABC):
    """Interface for message queues."""

    @abstractmethod
    async def declare(self, config: QueueConfig) -> bool:
        """Declare/create the queue."""

    @abstractmethod
    async def delete(self, if_unused: bool = False, if_empty: bool = False) -> bool:
        """Delete the queue."""

    @abstractmethod
    async def purge(self) -> int:
        """Purge all messages from queue."""

    @abstractmethod
    async def bind(self, exchange: str, routing_key: str = "") -> bool:
        """Bind queue to exchange."""

    @abstractmethod
    async def unbind(self, exchange: str, routing_key: str = "") -> bool:
        """Unbind queue from exchange."""

    @abstractmethod
    async def get_message_count(self) -> int:
        """Get number of messages in queue."""

    @abstractmethod
    async def get_consumer_count(self) -> int:
        """Get number of consumers."""


class IMessageExchange(ABC):
    """Interface for message exchanges."""

    @abstractmethod
    async def declare(self, config: ExchangeConfig) -> bool:
        """Declare/create the exchange."""

    @abstractmethod
    async def delete(self, if_unused: bool = False) -> bool:
        """Delete the exchange."""

    @abstractmethod
    async def bind(
        self, destination: str, routing_key: str = "", arguments: dict[str, Any] | None = None
    ) -> bool:
        """Bind exchange to another exchange or queue."""

    @abstractmethod
    async def unbind(self, destination: str, routing_key: str = "") -> bool:
        """Unbind from destination."""


class IMessageProducer(ABC):
    """Interface for message producers."""

    @abstractmethod
    async def start(self) -> None:
        """Start the producer."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop the producer."""

    @abstractmethod
    async def publish(self, message: Message) -> bool:
        """Publish a single message."""

    @abstractmethod
    async def publish_batch(self, messages: list[Message]) -> list[bool]:
        """Publish multiple messages."""


class IMessageConsumer(ABC):
    """Interface for message consumers."""

    @abstractmethod
    async def start(self) -> None:
        """Start consuming messages."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop consuming messages."""

    @abstractmethod
    async def acknowledge(self, message: Message) -> None:
        """Acknowledge message processing."""

    @abstractmethod
    async def reject(self, message: Message, requeue: bool = False) -> None:
        """Reject message."""

    @abstractmethod
    async def set_handler(self, handler: Callable[[Message], Any]) -> None:
        """Set message handler."""


class IMessageBackend(ABC):
    """Interface for message backends."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to the backend."""

    @abstractmethod
    async def disconnect(self) -> None:
        """Disconnect from the backend."""

    @abstractmethod
    async def is_connected(self) -> bool:
        """Check if connected."""

    @abstractmethod
    async def health_check(self) -> bool:
        """Perform health check."""

    @abstractmethod
    async def create_queue(self, config: QueueConfig) -> IMessageQueue:
        """Create a message queue."""

    @abstractmethod
    async def create_exchange(self, config: ExchangeConfig) -> IMessageExchange:
        """Create a message exchange."""

    @abstractmethod
    async def create_producer(self, config: ProducerConfig) -> IMessageProducer:
        """Create a message producer."""

    @abstractmethod
    async def create_consumer(self, config: ConsumerConfig) -> IMessageConsumer:
        """Create a message consumer."""


class IMessageMiddleware(ABC):
    """Interface for message middleware."""

    @abstractmethod
    async def process(self, message: Message, context: dict[str, Any]) -> Message:
        """Process message through middleware."""

    @abstractmethod
    def get_stage(self) -> MiddlewareStage:
        """Get middleware execution stage."""

    @abstractmethod
    def get_priority(self) -> int:
        """Get middleware priority (lower = earlier execution)."""


class IMessageRouter(ABC):
    """Interface for message routing."""

    @abstractmethod
    async def route(self, message: Message) -> tuple[str, str]:
        """Route message and return (exchange, routing_key)."""

    @abstractmethod
    async def add_rule(self, rule: RoutingRule) -> None:
        """Add routing rule."""

    @abstractmethod
    async def remove_rule(self, pattern: str) -> None:
        """Remove routing rule."""

    @abstractmethod
    async def get_rules(self) -> list[RoutingRule]:
        """Get all routing rules."""


class IDLQManager(ABC):
    """Interface for Dead Letter Queue management."""

    @abstractmethod
    async def send_to_dlq(self, message: Message, reason: str) -> bool:
        """Send message to DLQ."""

    @abstractmethod
    async def process_dlq(self) -> None:
        """Process messages in DLQ."""

    @abstractmethod
    async def get_dlq_messages(self, limit: int = 100) -> list[Message]:
        """Get messages from DLQ."""

    @abstractmethod
    async def requeue_from_dlq(self, message_id: str) -> bool:
        """Requeue message from DLQ."""


class IMessagingManager(ABC):
    """Interface for messaging manager."""

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the messaging system."""

    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the messaging system."""

    @abstractmethod
    async def create_producer(self, config: ProducerConfig) -> IMessageProducer:
        """Create a message producer."""

    @abstractmethod
    async def create_consumer(self, config: ConsumerConfig) -> IMessageConsumer:
        """Create a message consumer."""

    @abstractmethod
    async def get_backend(self) -> IMessageBackend:
        """Get the message backend."""

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Perform health check on messaging system."""


class IMessageBroker(ABC):
    """Interface for message broker."""

    @abstractmethod
    async def publish(self, message: Message) -> bool:
        """Publish a message through the broker."""

    @abstractmethod
    async def subscribe(self, queue: str, handler: Callable[[Message], Any]) -> None:
        """Subscribe to a queue."""

    @abstractmethod
    async def unsubscribe(self, queue: str) -> None:
        """Unsubscribe from a queue."""
