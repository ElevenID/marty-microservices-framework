"""
Messaging API - Core Interfaces and Contracts

This module defines the foundational interfaces and data contracts for the messaging system.
It serves as the lowest level in our messaging architecture, containing only abstract
contracts that other messaging components depend on.

Following the Level Contract principle:
- This module imports only from standard library
- All other messaging modules depend on this API layer
- No circular dependencies are possible by design
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Protocol, runtime_checkable

# --- Core Enums ---


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
    PROCESSED = "processed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    RETRY = "retry"


class BackendType(Enum):
    """Message backend types."""

    RABBITMQ = "rabbitmq"
    REDIS = "redis"
    KAFKA = "kafka"
    MEMORY = "memory"
    SQS = "sqs"
    PUBSUB = "pubsub"


class MessagePattern(Enum):
    """Message pattern types."""

    REQUEST_REPLY = "request_reply"
    PUBLISH_SUBSCRIBE = "publish_subscribe"
    WORK_QUEUE = "work_queue"
    ROUTING = "routing"
    RPC = "rpc"


class ConsumerMode(Enum):
    """Consumer processing modes."""

    PULL = "pull"
    PUSH = "push"
    STREAMING = "streaming"


class MiddlewareType(Enum):
    """Middleware types for different stages."""

    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    LOGGING = "logging"
    METRICS = "metrics"
    TRACING = "tracing"
    VALIDATION = "validation"
    TRANSFORMATION = "transformation"
    RETRY = "retry"
    CIRCUIT_BREAKER = "circuit_breaker"
    RATE_LIMITING = "rate_limiting"


class MiddlewareStage(Enum):
    """Middleware execution stages."""

    PRE_PUBLISH = "pre_publish"
    POST_PUBLISH = "post_publish"
    PRE_CONSUME = "pre_consume"
    POST_CONSUME = "post_consume"
    ERROR_HANDLING = "error_handling"


# --- Core Data Models ---


@dataclass
class MessageHeaders:
    """Message headers container."""

    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        """Get header value."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set header value."""
        self.data[key] = value

    def remove(self, key: str) -> None:
        """Remove header."""
        self.data.pop(key, None)


@dataclass
class Message:
    """Core message abstraction."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    body: Any = None
    headers: MessageHeaders = field(default_factory=MessageHeaders)
    priority: MessagePriority = MessagePriority.NORMAL
    status: MessageStatus = MessageStatus.PENDING
    routing_key: str = ""
    exchange: str = ""
    timestamp: float = field(default_factory=time.time)
    expiration: float | None = None
    retry_count: int = 0
    max_retries: int = 3
    correlation_id: str | None = None
    reply_to: str | None = None
    content_type: str = "application/json"
    content_encoding: str = "utf-8"
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_expired(self) -> bool:
        """Check if message has expired."""
        if self.expiration is None:
            return False
        return time.time() > self.expiration

    def can_retry(self) -> bool:
        """Check if message can be retried."""
        return self.retry_count < self.max_retries


@dataclass
class QueueConfig:
    """Queue configuration."""

    name: str
    durable: bool = True
    exclusive: bool = False
    auto_delete: bool = False
    arguments: dict[str, Any] = field(default_factory=dict)
    max_length: int | None = None
    max_length_bytes: int | None = None
    ttl: int | None = None  # seconds
    dlq_enabled: bool = True
    dlq_name: str | None = None


@dataclass
class ExchangeConfig:
    """Exchange configuration."""

    name: str
    type: str = "direct"  # direct, topic, fanout, headers
    durable: bool = True
    auto_delete: bool = False
    arguments: dict[str, Any] = field(default_factory=dict)


@dataclass
class BackendConfig:
    """Message backend configuration."""

    type: BackendType
    connection_url: str
    connection_params: dict[str, Any] = field(default_factory=dict)
    pool_size: int = 10
    max_connections: int = 100
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    health_check_interval: int = 30


@dataclass
class ProducerConfig:
    """Configuration for message producers."""

    name: str
    exchange: str | None = None
    routing_key: str = ""
    default_priority: MessagePriority = MessagePriority.NORMAL
    default_ttl: int | None = None
    confirm_delivery: bool = True
    max_retries: int = 3
    retry_delay: float = 1.0
    batch_size: int = 1
    batch_timeout: float = 5.0
    compression: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ConsumerConfig:
    """Configuration for message consumers."""

    name: str
    queue: str
    mode: ConsumerMode = ConsumerMode.PULL
    auto_ack: bool = False
    prefetch_count: int = 10
    max_workers: int = 5
    timeout: int = 30
    retry_attempts: int = 3
    retry_delay: float = 1.0
    dlq_enabled: bool = True
    batch_processing: bool = False
    batch_size: int = 10
    batch_timeout: float = 5.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingRule:
    """Message routing rule."""

    pattern: str
    exchange: str
    routing_key: str
    priority: int = 0
    condition: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RoutingConfig:
    """Routing configuration."""

    rules: list[RoutingRule] = field(default_factory=list)
    default_exchange: str | None = None
    default_routing_key: str = ""
    enable_fallback: bool = True
    fallback_exchange: str | None = None


class DLQPolicy(Enum):
    """Dead Letter Queue policies."""

    DROP = "drop"
    RETRY = "retry"
    FORWARD = "forward"
    STORE = "store"


@dataclass
class DLQMessage:
    """Dead Letter Queue message wrapper."""

    message: Message
    failure_count: int = 0
    retry_attempts: int = 0
    failure_reasons: list[str] = field(default_factory=list)
    exceptions: list[Exception] = field(default_factory=list)

    def add_failure(self, reason: str, exception: Exception | None = None) -> None:
        """Add a failure record to this DLQ message."""
        self.failure_count += 1
        self.failure_reasons.append(reason)
        if exception:
            self.exceptions.append(exception)


@dataclass
class DLQConfig:
    """Dead Letter Queue configuration."""

    enabled: bool = True
    queue_name: str | None = None
    exchange_name: str | None = None
    routing_key: str = "dlq"
    max_retries: int = 3
    retry_delay: float = 60.0  # seconds
    ttl: int | None = None  # seconds
    max_length: int | None = None
    retry_config: RetryConfig | None = None


@dataclass
class MessagingConfig:
    """Overall messaging configuration."""

    backend: BackendConfig
    default_exchange: ExchangeConfig | None = None
    default_queue: QueueConfig | None = None
    dlq: DLQConfig = field(default_factory=DLQConfig)
    routing: RoutingConfig = field(default_factory=RoutingConfig)
    enable_monitoring: bool = True
    enable_tracing: bool = True
    enable_metrics: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)


# --- Core Interfaces ---


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


# --- Exception Classes ---


class MessagingError(Exception):
    """Base messaging exception."""

    pass


class MessagingConnectionError(MessagingError):
    """Connection-related errors."""


class SerializationError(MessagingError):
    """Serialization-related errors."""

    pass


class RoutingError(MessagingError):
    """Routing-related errors."""

    pass


class ConsumerError(MessagingError):
    """Consumer-related errors."""

    pass


class ProducerError(MessagingError):
    """Producer-related errors."""

    pass


class DLQError(MessagingError):
    """DLQ-related errors."""

    pass


class MiddlewareError(MessagingError):
    """Middleware-related errors."""


# --- Additional Enums for Compatibility ---


class RoutingType(Enum):
    """Message routing types."""

    DIRECT = "direct"
    TOPIC = "topic"
    FANOUT = "fanout"
    HEADERS = "headers"


class MatchType(Enum):
    """Routing pattern match types."""

    EXACT = "exact"
    PREFIX = "prefix"
    SUFFIX = "suffix"
    REGEX = "regex"
    WILDCARD = "wildcard"


class RetryStrategy(Enum):
    """Retry strategies for failed messages."""

    FIXED_DELAY = "fixed_delay"
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"


@dataclass
class RetryConfig:
    """Retry configuration for failed messages."""

    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 300.0  # seconds
    backoff_multiplier: float = 2.0
    jitter: bool = True

    pass
