"""
Messaging Bootstrap - Dependency Injection and Component Wiring

This module handles the orchestration and dependency injection for the messaging system.
It wires together all the messaging components and provides the concrete implementations
that depend on the API layer.

Following the Level Contract principle:
- This module depends on the API layer (messaging.api)
- This module provides concrete implementations
- This module handles dependency injection and component assembly
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Callable
from typing import Any

from .api import (
    BackendConfig,
    BackendType,
    ConsumerConfig,
    DLQConfig,
    IDLQManager,
    IMessageBackend,
    IMessageConsumer,
    IMessageExchange,
    IMessageMiddleware,
    IMessageProducer,
    IMessageQueue,
    IMessageRouter,
    IMessageSerializer,
    IMessagingManager,
    Message,
    MessageHeaders,
    MessagePriority,
    MessageStatus,
    MessagingConfig,
    MessagingError,
    MiddlewareStage,
    ProducerConfig,
    QueueConfig,
    RoutingConfig,
    RoutingRule,
)


class JSONMessageSerializer(IMessageSerializer):
    """JSON message serializer implementation."""

    def serialize(self, data: Any) -> bytes:
        """Serialize data to JSON bytes."""
        try:
            return json.dumps(data, default=str).encode("utf-8")
        except (TypeError, ValueError) as e:
            raise MessagingError(f"Failed to serialize data: {e}") from e

    def deserialize(self, data: bytes) -> Any:
        """Deserialize JSON bytes to data."""
        try:
            return json.loads(data.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            raise MessagingError(f"Failed to deserialize data: {e}") from e

    def get_content_type(self) -> str:
        """Get content type for JSON."""
        return "application/json"


class MemoryMessageQueue(IMessageQueue):
    """In-memory message queue implementation."""

    def __init__(self, name: str):
        self.name = name
        self.messages: list[Message] = []
        self.bindings: dict[str, list[str]] = {}  # exchange -> routing_keys
        self._declared = False

    async def declare(self, config: Any) -> bool:
        """Declare the queue."""
        self._declared = True
        return True

    async def delete(self, if_unused: bool = False, if_empty: bool = False) -> bool:
        """Delete the queue."""
        if if_empty and self.messages:
            return False
        self.messages.clear()
        self.bindings.clear()
        self._declared = False
        return True

    async def purge(self) -> int:
        """Purge all messages from queue."""
        count = len(self.messages)
        self.messages.clear()
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
        return len(self.messages)

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


class MessageConsumer(IMessageConsumer):
    """Message consumer implementation."""

    def __init__(
        self,
        config: ConsumerConfig,
        backend: IMessageBackend,
        serializer: IMessageSerializer | None = None,
    ):
        self.config = config
        self.backend = backend
        self.serializer = serializer or JSONMessageSerializer()
        self.logger = logging.getLogger(__name__)
        self._running = False
        self._handler: Callable[[Message], Any] | None = None
        self._task: asyncio.Task | None = None

    async def start(self) -> None:
        """Start consuming messages."""
        if self._running:
            return

        self._running = True
        self.logger.info(f"Started consumer: {self.config.name}")

        # Start background task for consuming
        if self._handler:
            self._task = asyncio.create_task(self._consume_loop())

    async def stop(self) -> None:
        """Stop consuming messages."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self.logger.info(f"Stopped consumer: {self.config.name}")

    async def acknowledge(self, message: Message) -> None:
        """Acknowledge message processing."""
        message.status = MessageStatus.PROCESSED
        self.logger.debug(f"Acknowledged message {message.id}")

    async def reject(self, message: Message, requeue: bool = False) -> None:
        """Reject message."""
        message.status = MessageStatus.FAILED if not requeue else MessageStatus.PENDING
        self.logger.debug(f"Rejected message {message.id}, requeue: {requeue}")

    async def set_handler(self, handler: Callable[[Message], Any]) -> None:
        """Set message handler."""
        self._handler = handler

    async def _consume_loop(self) -> None:
        """Main consume loop."""
        while self._running:
            try:
                # In real implementation, this would fetch messages from backend
                # For now, we'll just simulate with a delay
                await asyncio.sleep(1)
            except Exception as e:
                self.logger.error(f"Error in consume loop: {e}")
                await asyncio.sleep(1)


class MessageRouter(IMessageRouter):
    """Message router implementation."""

    def __init__(self, config: RoutingConfig):
        self.config = config
        self.rules: list[RoutingRule] = config.rules.copy()
        self.logger = logging.getLogger(__name__)

    async def route(self, message: Message) -> tuple[str, str]:
        """Route message and return (exchange, routing_key)."""
        # Check rules in priority order
        sorted_rules = sorted(self.rules, key=lambda r: r.priority, reverse=True)

        for rule in sorted_rules:
            if await self._matches_rule(message, rule):
                return rule.exchange, rule.routing_key

        # Use default routing
        exchange = self.config.default_exchange or message.exchange
        routing_key = self.config.default_routing_key or message.routing_key
        return exchange, routing_key

    async def add_rule(self, rule: RoutingRule) -> None:
        """Add routing rule."""
        self.rules.append(rule)

    async def remove_rule(self, pattern: str) -> None:
        """Remove routing rule."""
        self.rules = [r for r in self.rules if r.pattern != pattern]

    async def get_rules(self) -> list[RoutingRule]:
        """Get all routing rules."""
        return self.rules.copy()

    async def _matches_rule(self, message: Message, rule: RoutingRule) -> bool:
        """Check if message matches routing rule."""
        # Simple pattern matching - in real implementation this would be more sophisticated
        return rule.pattern in message.routing_key or rule.pattern == "*"


class DLQManager(IDLQManager):
    """Dead Letter Queue manager implementation."""

    def __init__(self, config: DLQConfig, backend: IMessageBackend):
        self.config = config
        self.backend = backend
        self.logger = logging.getLogger(__name__)
        self.dlq_messages: dict[str, Message] = {}

    async def send_to_dlq(self, message: Message, reason: str) -> bool:
        """Send message to DLQ."""
        try:
            message.status = MessageStatus.DEAD_LETTER
            message.headers.set("dlq_reason", reason)
            message.headers.set("dlq_timestamp", time.time())

            self.dlq_messages[message.id] = message
            self.logger.warning(f"Sent message {message.id} to DLQ: {reason}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to send message {message.id} to DLQ: {e}")
            return False

    async def process_dlq(self) -> None:
        """Process messages in DLQ."""
        messages_to_retry = []
        current_time = time.time()

        for message in self.dlq_messages.values():
            dlq_timestamp = message.headers.get("dlq_timestamp", 0)
            if current_time - dlq_timestamp >= self.config.retry_delay:
                if message.retry_count < self.config.max_retries:
                    messages_to_retry.append(message)

        for message in messages_to_retry:
            message.retry_count += 1
            message.status = MessageStatus.RETRY
            del self.dlq_messages[message.id]
            self.logger.info(
                f"Retrying message {message.id} from DLQ (attempt {message.retry_count})"
            )

    async def get_dlq_messages(self, limit: int = 100) -> list[Message]:
        """Get messages from DLQ."""
        messages = list(self.dlq_messages.values())
        return messages[:limit]

    async def requeue_from_dlq(self, message_id: str) -> bool:
        """Requeue message from DLQ."""
        if message_id in self.dlq_messages:
            message = self.dlq_messages[message_id]
            message.status = MessageStatus.PENDING
            del self.dlq_messages[message_id]
            self.logger.info(f"Requeued message {message_id} from DLQ")
            return True
        return False


class MiddlewareChain:
    """Middleware chain for processing messages."""

    def __init__(self):
        self.middleware: dict[MiddlewareStage, list[IMessageMiddleware]] = {}
        self.logger = logging.getLogger(__name__)

    def add_middleware(self, middleware: IMessageMiddleware) -> None:
        """Add middleware to the chain."""
        stage = middleware.get_stage()
        if stage not in self.middleware:
            self.middleware[stage] = []

        # Insert in priority order (lower priority = earlier execution)
        self.middleware[stage].append(middleware)
        self.middleware[stage].sort(key=lambda m: m.get_priority())

    async def process(
        self, message: Message, stage: MiddlewareStage, context: dict[str, Any] | None = None
    ) -> Message:
        """Process message through middleware chain for a specific stage."""
        if context is None:
            context = {}

        if stage not in self.middleware:
            return message

        processed_message = message
        for middleware in self.middleware[stage]:
            try:
                processed_message = await middleware.process(processed_message, context)
            except Exception as e:
                self.logger.error(f"Middleware {type(middleware).__name__} failed: {e}")
                # Continue with other middleware or handle based on policy

        return processed_message


class MessagingManager(IMessagingManager):
    """Messaging manager implementation."""

    def __init__(self, config: MessagingConfig):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.backend: IMessageBackend | None = None
        self.router: MessageRouter | None = None
        self.dlq_manager: DLQManager | None = None
        self.middleware_chain = MiddlewareChain()
        self.producers: dict[str, MessageProducer] = {}
        self.consumers: dict[str, MessageConsumer] = {}
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the messaging system."""
        if self._initialized:
            return

        # Create backend
        self.backend = await self._create_backend()
        await self.backend.connect()

        # Create router
        self.router = MessageRouter(self.config.routing)

        # Create DLQ manager
        self.dlq_manager = DLQManager(self.config.dlq, self.backend)

        self._initialized = True
        self.logger.info("Messaging system initialized")

    async def shutdown(self) -> None:
        """Shutdown the messaging system."""
        # Stop all consumers
        for consumer in self.consumers.values():
            await consumer.stop()

        # Stop all producers
        for producer in self.producers.values():
            await producer.stop()

        # Disconnect backend
        if self.backend:
            await self.backend.disconnect()

        self._initialized = False
        self.logger.info("Messaging system shutdown")

    async def create_producer(self, config: ProducerConfig) -> IMessageProducer:
        """Create a message producer."""
        if not self._initialized:
            raise MessagingError("Messaging system not initialized")

        if not self.backend:
            raise MessagingError("Backend not initialized")
        producer = MessageProducer(config, self.backend)
        await producer.start()
        self.producers[config.name] = producer
        return producer

    async def create_consumer(self, config: ConsumerConfig) -> IMessageConsumer:
        """Create a message consumer."""
        if not self._initialized:
            raise MessagingError("Messaging system not initialized")

        if not self.backend:
            raise MessagingError("Backend not initialized")
        consumer = MessageConsumer(config, self.backend)
        self.consumers[config.name] = consumer
        return consumer

    async def get_backend(self) -> IMessageBackend:
        """Get the message backend."""
        if not self.backend:
            raise MessagingError("Backend not initialized")
        return self.backend

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on messaging system."""
        health = {
            "initialized": self._initialized,
            "backend_connected": False,
            "producers": len(self.producers),
            "consumers": len(self.consumers),
        }

        if self.backend:
            health["backend_connected"] = await self.backend.health_check()

        return health

    async def _create_backend(self) -> IMessageBackend:
        """Create message backend based on configuration."""
        if self.config.backend.type == BackendType.MEMORY:
            return MemoryMessageBackend(self.config.backend)
        else:
            # In real implementation, create other backend types
            raise MessagingError(f"Unsupported backend type: {self.config.backend.type}")


# --- Bootstrap Functions ---


def create_messaging_manager(config: MessagingConfig | None = None) -> MessagingManager:
    """Create a fully configured messaging manager."""
    if config is None:
        # Create default memory backend config
        backend_config = BackendConfig(type=BackendType.MEMORY, connection_url="memory://localhost")
        config = MessagingConfig(backend=backend_config)

    return MessagingManager(config)


async def setup_messaging_system(config: MessagingConfig | None = None) -> MessagingManager:
    """Set up and initialize the complete messaging system."""
    manager = create_messaging_manager(config)
    await manager.initialize()
    return manager


# --- Compatibility Classes ---


class MessageQueue:
    """Compatibility wrapper for message queue operations."""

    def __init__(self, backend: IMessageBackend, queue_name: str = "default"):
        self.backend = backend
        self.queue_name = queue_name
        self.queue: IMessageQueue | None = None
        self.logger = logging.getLogger(__name__)

    async def bind(self) -> bool:
        """Bind/initialize the queue."""
        config = QueueConfig(name=self.queue_name)
        self.queue = await self.backend.create_queue(config)
        return True

    async def publish(self, message_data: Any) -> bool:
        """Publish a message to the queue."""
        message = Message(body=message_data)
        # In real implementation, this would use the queue's publish mechanism
        self.logger.info(f"Published message to queue {self.queue_name}: {message.id}")
        return True

    async def consume(self, handler: Callable[[Any], bool]) -> None:
        """Consume messages from the queue."""
        # In real implementation, this would set up message consumption
        self.logger.info(f"Started consuming from queue {self.queue_name}")


class EventStreamManager:
    """Compatibility wrapper for event stream management."""

    def __init__(self, backend: IMessageBackend | None = None):
        self.backend = backend
        self.streams: dict[str, Any] = {}
        self.logger = logging.getLogger(__name__)

    async def create_stream(self, stream_name: str) -> Any:
        """Create an event stream."""
        # In real implementation, this would create actual streams
        stream = {"name": stream_name, "backend": self.backend}
        self.streams[stream_name] = stream
        self.logger.info(f"Created event stream: {stream_name}")
        return stream

    async def publish_event(self, stream_name: str, event_data: Any) -> bool:
        """Publish event to stream."""
        if stream_name not in self.streams:
            await self.create_stream(stream_name)

        self.logger.info(f"Published event to stream {stream_name}: {event_data}")
        return True

    async def subscribe(self, stream_name: str, handler: Callable[[Any], None]) -> None:
        """Subscribe to events from stream."""
        if stream_name not in self.streams:
            await self.create_stream(stream_name)

        self.logger.info(f"Subscribed to stream: {stream_name}")


class DLQHandler:
    """Handler for Dead Letter Queue operations."""

    def __init__(self, config: Any | None = None, logger: logging.Logger | None = None):
        self.config = config or {}
        self.logger = logger or logging.getLogger(__name__)
        self.dlq_manager = DLQManager(config, logger)

    async def handle_failed_message(self, message: Any, error: Exception) -> bool:
        """Handle a failed message by sending it to DLQ."""
        try:
            return await self.dlq_manager.send_to_dlq(message, str(error))
        except Exception as e:
            self.logger.error(f"Failed to handle DLQ message: {e}")
            return False

    async def process_dlq_message(self, message: Any) -> bool:
        """Process a message from the DLQ."""
        try:
            # In real implementation, this would attempt reprocessing
            self.logger.info(f"Processing DLQ message: {message}")
            return True
        except Exception as e:
            self.logger.error(f"Failed to process DLQ message: {e}")
            return False


# Compatibility alias
MessageBus = MessagingManager
