"""
Messaging Domain Models

This module defines the core data structures, enums, and exceptions for the messaging system.
It is part of the Domain layer and has NO dependencies on external libraries or other layers.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

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


class DLQPolicy(Enum):
    """Dead Letter Queue policies."""

    DROP = "drop"
    RETRY = "retry"
    FORWARD = "forward"
    STORE = "store"


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


@dataclass
class RetryConfig:
    """Retry configuration for failed messages."""

    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    max_attempts: int = 3
    initial_delay: float = 1.0  # seconds
    max_delay: float = 300.0  # seconds
    backoff_multiplier: float = 2.0
    jitter: bool = True


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
