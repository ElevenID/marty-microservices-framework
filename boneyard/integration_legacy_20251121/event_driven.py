"""
Event-Driven Architecture and Message Broker Integration for Marty Microservices Framework

This module implements comprehensive event-driven patterns including publish-subscribe,
message brokers, event sourcing integration, and enterprise messaging patterns.
"""

import asyncio
import builtins
import json
import logging
import threading
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

# For message broker operations
import pika  # RabbitMQ

# import aiokafka  # Kafka (would be imported in production)


class EventState(Enum):
    """Event processing states."""

    PENDING = "pending"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTER = "dead_letter"


class DeliveryGuarantee(Enum):
    """Message delivery guarantees."""

    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


class PartitionStrategy(Enum):
    """Partitioning strategies for message distribution."""

    ROUND_ROBIN = "round_robin"
    KEY_HASH = "key_hash"
    RANDOM = "random"
    STICKY = "sticky"
    CUSTOM = "custom"


class SerializationFormat(Enum):
    """Message serialization formats."""

    JSON = "json"
    AVRO = "avro"
    PROTOBUF = "protobuf"
    XML = "xml"
    MSGPACK = "msgpack"
    CUSTOM = "custom"


@dataclass
class EventMessage:
    """Event message definition."""

    message_id: str
    event_type: str
    source: str
    data: builtins.dict[str, Any]

    # Event metadata
    correlation_id: str | None = None
    causation_id: str | None = None
    version: str = "1.0.0"

    # Routing
    routing_key: str | None = None
    partition_key: str | None = None

    # Delivery
    delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE
    retry_count: int = 0
    max_retries: int = 3

    # Serialization
    content_type: str = "application/json"
    compression: bool = False

    # Timestamps
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None

    # Processing state
    state: EventState = EventState.PENDING
    processed_at: datetime | None = None
    error_message: str | None = None


@dataclass
class EventSubscription:
    """Event subscription definition."""

    subscription_id: str
    consumer_group: str
    event_types: builtins.list[str]
    handler: Callable[[EventMessage], bool]

    # Subscription configuration
    auto_acknowledge: bool = True
    max_concurrent: int = 10
    batch_size: int = 1

    # Filtering
    filters: builtins.dict[str, Any] = field(default_factory=dict)

    # Error handling
    retry_policy: builtins.dict[str, Any] = field(default_factory=dict)
    dead_letter_queue: str | None = None

    # Metrics
    processed_count: int = 0
    error_count: int = 0

    # State
    active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class MessageBrokerConfig:
    """Message broker configuration."""

    broker_type: str  # "rabbitmq", "kafka", "redis", etc.
    connection_string: str

    # Authentication
    username: str | None = None
    password: str | None = None
    ssl_enabled: bool = False

    # Connection settings
    max_connections: int = 10
    connection_timeout: int = 30
    heartbeat_interval: int = 60

    # Performance settings
    prefetch_count: int = 100
    batch_size: int = 10
    compression_enabled: bool = False

    # Durability
    durable_queues: bool = True
    persistent_messages: bool = True

    # Monitoring
    metrics_enabled: bool = True


@dataclass
class TopicConfiguration:
    """Topic/queue configuration."""

    name: str
    partitions: int = 1
    replication_factor: int = 1
    retention_ms: int | None = None  # None for infinite

    # Message settings
    max_message_size: int = 1024 * 1024  # 1MB
    compression_type: str = "gzip"

    # Cleanup policy
    cleanup_policy: str = "delete"  # or "compact"

    # Access control
    read_access: builtins.list[str] = field(default_factory=list)
    write_access: builtins.list[str] = field(default_factory=list)


class EventBus(ABC):
    """Abstract event bus interface."""

    @abstractmethod
    async def publish(self, event: EventMessage) -> bool:
        """Publish event to the bus."""

    @abstractmethod
    async def subscribe(self, subscription: EventSubscription) -> bool:
        """Subscribe to events."""

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""

    @abstractmethod
    async def start(self):
        """Start the event bus."""

    @abstractmethod
    async def stop(self):
        """Stop the event bus."""


class InMemoryEventBus(EventBus):
    """In-memory event bus implementation for testing."""

    def __init__(self):
        """Initialize in-memory event bus."""
        self.events: deque = deque(maxlen=10000)
        self.subscriptions: builtins.dict[str, EventSubscription] = {}
        self.event_handlers: builtins.dict[str, builtins.list[EventSubscription]] = defaultdict(
            list
        )

        # Processing
        self.processing_tasks: builtins.dict[str, asyncio.Task] = {}
        self.running = False

        # Metrics
        self.metrics: builtins.dict[str, int] = defaultdict(int)

        # Thread safety
        self._lock = threading.RLock()

    async def publish(self, event: EventMessage) -> bool:
        """Publish event to in-memory bus."""
        try:
            with self._lock:
                self.events.append(event)
                self.metrics["events_published"] += 1

            # Trigger processing
            await self._process_event(event)

            logging.info(f"Published event: {event.event_type}")
            return True

        except Exception as e:
            logging.exception(f"Failed to publish event: {e}")
            return False

    async def subscribe(self, subscription: EventSubscription) -> bool:
        """Subscribe to events."""
        try:
            with self._lock:
                self.subscriptions[subscription.subscription_id] = subscription

                # Register handlers for event types
                for event_type in subscription.event_types:
                    self.event_handlers[event_type].append(subscription)

                self.metrics["subscriptions_created"] += 1

            logging.info(f"Created subscription: {subscription.subscription_id}")
            return True

        except Exception as e:
            logging.exception(f"Failed to create subscription: {e}")
            return False

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from events."""
        try:
            with self._lock:
                subscription = self.subscriptions.get(subscription_id)
                if not subscription:
                    return False

                # Remove from event handlers
                for event_type in subscription.event_types:
                    if subscription in self.event_handlers[event_type]:
                        self.event_handlers[event_type].remove(subscription)

                del self.subscriptions[subscription_id]
                self.metrics["subscriptions_removed"] += 1

            logging.info(f"Removed subscription: {subscription_id}")
            return True

        except Exception as e:
            logging.exception(f"Failed to remove subscription: {e}")
            return False

    async def start(self):
        """Start the event bus."""
        self.running = True
        logging.info("Started in-memory event bus")

    async def stop(self):
        """Stop the event bus."""
        self.running = False

        # Cancel processing tasks
        for task in self.processing_tasks.values():
            task.cancel()

        self.processing_tasks.clear()
        logging.info("Stopped in-memory event bus")

    async def _process_event(self, event: EventMessage):
        """Process event by delivering to subscribers."""
        handlers = self.event_handlers.get(event.event_type, [])

        for subscription in handlers:
            if not subscription.active:
                continue

            # Apply filters
            if not self._matches_filters(event, subscription.filters):
                continue

            # Process event with handler
            task = asyncio.create_task(self._handle_event(event, subscription))

            task_id = f"{subscription.subscription_id}:{event.message_id}"
            self.processing_tasks[task_id] = task

    def _matches_filters(self, event: EventMessage, filters: builtins.dict[str, Any]) -> bool:
        """Check if event matches subscription filters."""
        if not filters:
            return True

        for filter_key, filter_value in filters.items():
            event_value = event.data.get(filter_key)

            if isinstance(filter_value, list):
                if event_value not in filter_value:
                    return False
            elif event_value != filter_value:
                return False

        return True

    async def _handle_event(self, event: EventMessage, subscription: EventSubscription):
        """Handle event with subscription handler."""
        try:
            event.state = EventState.PROCESSING

            # Call handler
            success = await self._call_handler(subscription.handler, event)

            if success:
                event.state = EventState.PROCESSED
                event.processed_at = datetime.now(timezone.utc)
                subscription.processed_count += 1
                self.metrics["events_processed"] += 1
            else:
                await self._handle_processing_error(event, subscription, "Handler returned False")

        except Exception as e:
            await self._handle_processing_error(event, subscription, str(e))

        finally:
            # Clean up task
            task_id = f"{subscription.subscription_id}:{event.message_id}"
            self.processing_tasks.pop(task_id, None)

    async def _call_handler(self, handler: Callable, event: EventMessage) -> bool:
        """Call event handler safely."""
        try:
            if asyncio.iscoroutinefunction(handler):
                return await handler(event)
            # Run sync handler in thread pool
            loop = asyncio.get_event_loop()
            return await loop.run_in_executor(None, handler, event)

        except Exception as e:
            logging.exception(f"Handler error: {e}")
            return False

    async def _handle_processing_error(
        self, event: EventMessage, subscription: EventSubscription, error_msg: str
    ):
        """Handle event processing error."""
        event.error_message = error_msg
        event.retry_count += 1
        subscription.error_count += 1

        if event.retry_count <= event.max_retries:
            event.state = EventState.RETRYING

            # Retry with exponential backoff
            retry_delay = min(2**event.retry_count, 60)  # Max 60 seconds
            await asyncio.sleep(retry_delay)

            # Retry processing
            await self._handle_event(event, subscription)
        else:
            event.state = EventState.DEAD_LETTER

            # Send to dead letter queue if configured
            if subscription.dead_letter_queue:
                await self._send_to_dead_letter_queue(event, subscription.dead_letter_queue)

            self.metrics["events_failed"] += 1
            logging.error(f"Event processing failed permanently: {event.message_id}")

    async def _send_to_dead_letter_queue(self, event: EventMessage, dead_letter_queue: str):
        """Send event to dead letter queue."""
        # Simplified dead letter queue implementation
        logging.warning(
            f"Sending event {event.message_id} to dead letter queue: {dead_letter_queue}"
        )

    def get_metrics(self) -> builtins.dict[str, Any]:
        """Get event bus metrics."""
        with self._lock:
            return {
                "total_events": len(self.events),
                "total_subscriptions": len(self.subscriptions),
                "active_processing_tasks": len(self.processing_tasks),
                "metrics": dict(self.metrics),
            }


class RabbitMQEventBus(EventBus):
    """RabbitMQ-based event bus implementation."""

    def __init__(self, config: MessageBrokerConfig):
        """Initialize RabbitMQ event bus."""
        self.config = config
        self.connection = None
        self.channel = None
        self.subscriptions: builtins.dict[str, EventSubscription] = {}

        # Processing
        self.consumer_tasks: builtins.dict[str, asyncio.Task] = {}
        self.running = False

        # Metrics
        self.metrics: builtins.dict[str, int] = defaultdict(int)

        # Thread safety
        self._lock = threading.RLock()

    async def start(self):
        """Start RabbitMQ connection."""
        try:
            # Parse connection string
            connection_params = pika.URLParameters(self.config.connection_string)

            # Create connection
            self.connection = pika.BlockingConnection(connection_params)
            self.channel = self.connection.channel()

            # Declare exchange for events
            self.channel.exchange_declare(
                exchange="marty.events", exchange_type="topic", durable=True
            )

            self.running = True
            logging.info("Started RabbitMQ event bus")

        except Exception as e:
            logging.exception(f"Failed to start RabbitMQ event bus: {e}")
            raise

    async def stop(self):
        """Stop RabbitMQ connection."""
        self.running = False

        # Cancel consumer tasks
        for task in self.consumer_tasks.values():
            task.cancel()

        self.consumer_tasks.clear()

        # Close connection
        if self.channel:
            self.channel.close()

        if self.connection:
            self.connection.close()

        logging.info("Stopped RabbitMQ event bus")

    async def publish(self, event: EventMessage) -> bool:
        """Publish event to RabbitMQ."""
        try:
            if not self.running:
                return False

            # Serialize event
            message_body = json.dumps(
                {
                    "message_id": event.message_id,
                    "event_type": event.event_type,
                    "source": event.source,
                    "data": event.data,
                    "correlation_id": event.correlation_id,
                    "causation_id": event.causation_id,
                    "version": event.version,
                    "created_at": event.created_at.isoformat(),
                    "expires_at": event.expires_at.isoformat() if event.expires_at else None,
                }
            )

            # Publish to exchange
            routing_key = event.routing_key or event.event_type

            self.channel.basic_publish(
                exchange="marty.events",
                routing_key=routing_key,
                body=message_body,
                properties=pika.BasicProperties(
                    delivery_mode=2 if self.config.persistent_messages else 1,  # Persistent
                    message_id=event.message_id,
                    correlation_id=event.correlation_id,
                    content_type=event.content_type,
                    timestamp=int(event.created_at.timestamp()),
                ),
            )

            self.metrics["events_published"] += 1
            logging.info(f"Published event to RabbitMQ: {event.event_type}")
            return True

        except Exception as e:
            logging.exception(f"Failed to publish event to RabbitMQ: {e}")
            return False

    async def subscribe(self, subscription: EventSubscription) -> bool:
        """Subscribe to events in RabbitMQ."""
        try:
            with self._lock:
                self.subscriptions[subscription.subscription_id] = subscription

            # Create queue for subscription
            queue_name = f"{subscription.consumer_group}.{subscription.subscription_id}"

            self.channel.queue_declare(queue=queue_name, durable=self.config.durable_queues)

            # Bind queue to exchange for each event type
            for event_type in subscription.event_types:
                self.channel.queue_bind(
                    exchange="marty.events", queue=queue_name, routing_key=event_type
                )

            # Start consumer task
            consumer_task = asyncio.create_task(self._consume_messages(subscription, queue_name))

            self.consumer_tasks[subscription.subscription_id] = consumer_task
            self.metrics["subscriptions_created"] += 1

            logging.info(f"Created RabbitMQ subscription: {subscription.subscription_id}")
            return True

        except Exception as e:
            logging.exception(f"Failed to create RabbitMQ subscription: {e}")
            return False

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from RabbitMQ events."""
        try:
            with self._lock:
                subscription = self.subscriptions.get(subscription_id)
                if not subscription:
                    return False

                # Cancel consumer task
                if subscription_id in self.consumer_tasks:
                    self.consumer_tasks[subscription_id].cancel()
                    del self.consumer_tasks[subscription_id]

                # Delete queue
                queue_name = f"{subscription.consumer_group}.{subscription_id}"
                self.channel.queue_delete(queue=queue_name)

                del self.subscriptions[subscription_id]
                self.metrics["subscriptions_removed"] += 1

            logging.info(f"Removed RabbitMQ subscription: {subscription_id}")
            return True

        except Exception as e:
            logging.exception(f"Failed to remove RabbitMQ subscription: {e}")
            return False

    async def _consume_messages(self, subscription: EventSubscription, queue_name: str):
        """Consume messages from RabbitMQ queue."""
        try:
            # Set up consumer
            self.channel.basic_qos(prefetch_count=self.config.prefetch_count)

            def callback(ch, method, properties, body):
                # Convert to EventMessage
                try:
                    message_data = json.loads(body.decode("utf-8"))

                    event = EventMessage(
                        message_id=message_data["message_id"],
                        event_type=message_data["event_type"],
                        source=message_data["source"],
                        data=message_data["data"],
                        correlation_id=message_data.get("correlation_id"),
                        causation_id=message_data.get("causation_id"),
                        version=message_data.get("version", "1.0.0"),
                        created_at=datetime.fromisoformat(message_data["created_at"]),
                    )

                    # Process event
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)

                    try:
                        success = loop.run_until_complete(
                            self._process_rabbitmq_event(event, subscription)
                        )

                        if success and subscription.auto_acknowledge:
                            ch.basic_ack(delivery_tag=method.delivery_tag)
                        elif not success:
                            ch.basic_nack(delivery_tag=method.delivery_tag, requeue=True)

                    finally:
                        loop.close()

                except Exception as e:
                    logging.exception(f"Message processing error: {e}")
                    ch.basic_nack(delivery_tag=method.delivery_tag, requeue=False)

            # Start consuming
            self.channel.basic_consume(queue=queue_name, on_message_callback=callback)

            # Keep consuming
            while self.running and subscription.active:
                self.connection.process_data_events(time_limit=1)
                await asyncio.sleep(0.1)

        except Exception as e:
            logging.exception(f"RabbitMQ consumer error: {e}")

    async def _process_rabbitmq_event(
        self, event: EventMessage, subscription: EventSubscription
    ) -> bool:
        """Process event from RabbitMQ."""
        try:
            # Call handler
            if asyncio.iscoroutinefunction(subscription.handler):
                success = await subscription.handler(event)
            else:
                success = subscription.handler(event)

            if success:
                subscription.processed_count += 1
                self.metrics["events_processed"] += 1
            else:
                subscription.error_count += 1
                self.metrics["events_failed"] += 1

            return success

        except Exception as e:
            subscription.error_count += 1
            self.metrics["events_failed"] += 1
            logging.exception(f"Event processing error: {e}")
            return False


class MessageTransformer:
    """Message transformation utilities."""

    def __init__(self):
        """Initialize message transformer."""
        self.transformations: builtins.dict[str, Callable] = {}
        self.serializers: builtins.dict[SerializationFormat, Callable] = {
            SerializationFormat.JSON: self._serialize_json,
            SerializationFormat.XML: self._serialize_xml,
        }

        self.deserializers: builtins.dict[SerializationFormat, Callable] = {
            SerializationFormat.JSON: self._deserialize_json,
            SerializationFormat.XML: self._deserialize_xml,
        }

    def register_transformation(
        self,
        name: str,
        transformer: Callable[[builtins.dict[str, Any]], builtins.dict[str, Any]],
    ):
        """Register message transformation."""
        self.transformations[name] = transformer
        logging.info(f"Registered transformation: {name}")

    def transform_message(
        self, message: builtins.dict[str, Any], transformation_name: str
    ) -> builtins.dict[str, Any]:
        """Apply transformation to message."""
        if transformation_name not in self.transformations:
            raise ValueError(f"Unknown transformation: {transformation_name}")

        transformer = self.transformations[transformation_name]
        return transformer(message)

    def serialize_message(
        self, message: builtins.dict[str, Any], format: SerializationFormat
    ) -> bytes:
        """Serialize message to bytes."""
        if format not in self.serializers:
            raise ValueError(f"Unsupported serialization format: {format}")

        serializer = self.serializers[format]
        return serializer(message)

    def deserialize_message(
        self, data: bytes, format: SerializationFormat
    ) -> builtins.dict[str, Any]:
        """Deserialize message from bytes."""
        if format not in self.deserializers:
            raise ValueError(f"Unsupported deserialization format: {format}")

        deserializer = self.deserializers[format]
        return deserializer(data)

    def _serialize_json(self, message: builtins.dict[str, Any]) -> bytes:
        """Serialize to JSON."""
        return json.dumps(message, default=str).encode("utf-8")

    def _deserialize_json(self, data: bytes) -> builtins.dict[str, Any]:
        """Deserialize from JSON."""
        return json.loads(data.decode("utf-8"))

    def _serialize_xml(self, message: builtins.dict[str, Any]) -> bytes:
        """Serialize to XML (simplified)."""
        # This is a very basic XML serialization
        # In production, use a proper XML library like lxml

        def dict_to_xml(data, root_name="message"):
            xml_parts = [f"<{root_name}>"]

            for key, value in data.items():
                if isinstance(value, dict):
                    xml_parts.append(dict_to_xml(value, key))
                elif isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            xml_parts.append(dict_to_xml(item, key))
                        else:
                            xml_parts.append(f"<{key}>{item}</{key}>")
                else:
                    xml_parts.append(f"<{key}>{value}</{key}>")

            xml_parts.append(f"</{root_name}>")
            return "".join(xml_parts)

        xml_string = dict_to_xml(message)
        return xml_string.encode("utf-8")

    def _deserialize_xml(self, data: bytes) -> builtins.dict[str, Any]:
        """Deserialize from XML (simplified)."""
        # This is a very basic XML deserialization
        # In production, use a proper XML library like lxml

        xml_string = data.decode("utf-8")

        # Very simplified XML parsing - just extract text content
        # This is for demonstration only
        result = {"xml_content": xml_string}

        return result


class EventOrchestrator:
    """Orchestrates complex event-driven workflows."""

    def __init__(self, event_bus: EventBus):
        """Initialize event orchestrator."""
        self.event_bus = event_bus
        self.workflows: builtins.dict[str, builtins.dict[str, Any]] = {}
        self.active_workflows: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Workflow state tracking
        self.workflow_states: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Pattern matching
        self.event_patterns: builtins.dict[str, builtins.list[builtins.dict[str, Any]]] = (
            defaultdict(list)
        )

        # Saga support
        self.sagas: builtins.dict[str, builtins.dict[str, Any]] = {}

        # Thread safety
        self._lock = threading.RLock()

    def register_workflow(
        self, workflow_id: str, workflow_definition: builtins.dict[str, Any]
    ) -> bool:
        """Register event workflow."""
        try:
            with self._lock:
                self.workflows[workflow_id] = workflow_definition

                # Register patterns from workflow
                for step in workflow_definition.get("steps", []):
                    trigger_event = step.get("trigger_event")
                    if trigger_event:
                        pattern = {
                            "workflow_id": workflow_id,
                            "step_id": step["step_id"],
                            "conditions": step.get("conditions", {}),
                            "actions": step.get("actions", []),
                        }
                        self.event_patterns[trigger_event].append(pattern)

            logging.info(f"Registered workflow: {workflow_id}")
            return True

        except Exception as e:
            logging.exception(f"Failed to register workflow: {e}")
            return False

    async def start_workflow(self, workflow_id: str, context: builtins.dict[str, Any]) -> str:
        """Start workflow instance."""
        try:
            workflow_instance_id = str(uuid.uuid4())

            with self._lock:
                workflow_def = self.workflows.get(workflow_id)
                if not workflow_def:
                    raise ValueError(f"Workflow not found: {workflow_id}")

                workflow_instance = {
                    "workflow_id": workflow_id,
                    "instance_id": workflow_instance_id,
                    "definition": workflow_def,
                    "context": context,
                    "current_step": 0,
                    "completed_steps": [],
                    "state": "running",
                    "started_at": datetime.now(timezone.utc),
                }

                self.active_workflows[workflow_instance_id] = workflow_instance
                self.workflow_states[workflow_instance_id] = {}

            # Trigger first step if auto-start
            if workflow_def.get("auto_start", True):
                await self._execute_workflow_step(workflow_instance_id, 0)

            logging.info(f"Started workflow instance: {workflow_instance_id}")
            return workflow_instance_id

        except Exception as e:
            logging.exception(f"Failed to start workflow: {e}")
            raise

    async def handle_event(self, event: EventMessage) -> bool:
        """Handle incoming event for workflow processing."""
        try:
            # Find matching patterns
            patterns = self.event_patterns.get(event.event_type, [])

            for pattern in patterns:
                # Check conditions
                if self._matches_conditions(event, pattern["conditions"]):
                    await self._execute_pattern_actions(event, pattern)

            # Check active workflows
            await self._check_workflow_triggers(event)

            return True

        except Exception as e:
            logging.exception(f"Event handling error in orchestrator: {e}")
            return False

    def _matches_conditions(self, event: EventMessage, conditions: builtins.dict[str, Any]) -> bool:
        """Check if event matches workflow conditions."""
        if not conditions:
            return True

        for condition_key, condition_value in conditions.items():
            event_value = event.data.get(condition_key)

            if isinstance(condition_value, dict):
                # Complex condition (e.g., {"op": "gt", "value": 100})
                op = condition_value.get("op")
                expected_value = condition_value.get("value")

                if (op == "eq" and event_value != expected_value) or (
                    op == "gt" and event_value <= expected_value
                ):
                    return False
                if (op == "lt" and event_value >= expected_value) or (
                    op == "in" and event_value not in expected_value
                ):
                    return False
            # Simple equality check
            elif event_value != condition_value:
                return False

        return True

    async def _execute_pattern_actions(self, event: EventMessage, pattern: builtins.dict[str, Any]):
        """Execute actions for matched pattern."""
        actions = pattern.get("actions", [])

        for action in actions:
            action_type = action.get("type")

            if action_type == "publish_event":
                # Publish new event
                new_event_data = action.get("event_data", {})
                new_event_data.update({"triggered_by": event.message_id})

                new_event = EventMessage(
                    message_id=str(uuid.uuid4()),
                    event_type=action.get("event_type"),
                    source="event_orchestrator",
                    data=new_event_data,
                    correlation_id=event.correlation_id,
                )

                await self.event_bus.publish(new_event)

            elif action_type == "update_workflow":
                # Update workflow state
                workflow_id = action.get("workflow_id")
                updates = action.get("updates", {})

                # Apply updates to active workflows
                for _instance_id, instance in self.active_workflows.items():
                    if instance["workflow_id"] == workflow_id:
                        instance["context"].update(updates)

            elif action_type == "complete_step":
                # Mark workflow step as complete
                workflow_instance_id = action.get("workflow_instance_id")
                step_id = action.get("step_id")

                if workflow_instance_id in self.active_workflows:
                    instance = self.active_workflows[workflow_instance_id]
                    if step_id not in instance["completed_steps"]:
                        instance["completed_steps"].append(step_id)

    async def _check_workflow_triggers(self, event: EventMessage):
        """Check if event triggers workflow steps."""
        with self._lock:
            instances_to_process = list(self.active_workflows.values())

        for instance in instances_to_process:
            if instance["state"] != "running":
                continue

            workflow_def = instance["definition"]
            steps = workflow_def.get("steps", [])

            for i, step in enumerate(steps):
                # Check if step is waiting for this event
                if (
                    step.get("trigger_event") == event.event_type
                    and i not in instance["completed_steps"]
                ):
                    # Check step conditions
                    if self._matches_conditions(event, step.get("conditions", {})):
                        await self._execute_workflow_step(instance["instance_id"], i)

    async def _execute_workflow_step(self, workflow_instance_id: str, step_index: int):
        """Execute workflow step."""
        try:
            instance = self.active_workflows.get(workflow_instance_id)
            if not instance:
                return

            workflow_def = instance["definition"]
            steps = workflow_def.get("steps", [])

            if step_index >= len(steps):
                # Workflow complete
                instance["state"] = "completed"
                instance["completed_at"] = datetime.now(timezone.utc)
                return

            step = steps[step_index]

            # Execute step actions
            for action in step.get("actions", []):
                await self._execute_step_action(instance, action)

            # Mark step as completed
            if step_index not in instance["completed_steps"]:
                instance["completed_steps"].append(step_index)

            # Check if workflow is complete
            if len(instance["completed_steps"]) == len(steps):
                instance["state"] = "completed"
                instance["completed_at"] = datetime.now(timezone.utc)

                logging.info(f"Workflow completed: {workflow_instance_id}")

        except Exception as e:
            # Mark workflow as failed
            instance["state"] = "failed"
            instance["error"] = str(e)
            instance["failed_at"] = datetime.now(timezone.utc)

            logging.exception(f"Workflow step execution failed: {e}")

    async def _execute_step_action(
        self, instance: builtins.dict[str, Any], action: builtins.dict[str, Any]
    ):
        """Execute individual step action."""
        action_type = action.get("type")

        if action_type == "publish_event":
            # Publish event
            event_data = action.get("event_data", {})

            # Substitute context variables
            event_data = self._substitute_context_variables(event_data, instance["context"])

            event = EventMessage(
                message_id=str(uuid.uuid4()),
                event_type=action.get("event_type"),
                source="workflow_orchestrator",
                data=event_data,
                correlation_id=instance.get("correlation_id"),
            )

            await self.event_bus.publish(event)

        elif action_type == "update_context":
            # Update workflow context
            updates = action.get("updates", {})
            instance["context"].update(updates)

        elif action_type == "delay":
            # Add delay
            delay_seconds = action.get("delay_seconds", 0)
            if delay_seconds > 0:
                await asyncio.sleep(delay_seconds)

    def _substitute_context_variables(self, data: Any, context: builtins.dict[str, Any]) -> Any:
        """Substitute context variables in data."""
        if isinstance(data, dict):
            return {
                key: self._substitute_context_variables(value, context)
                for key, value in data.items()
            }
        if isinstance(data, list):
            return [self._substitute_context_variables(item, context) for item in data]
        if isinstance(data, str) and data.startswith("${") and data.endswith("}"):
            # Variable substitution
            var_name = data[2:-1]
            return context.get(var_name, data)
        return data

    def get_workflow_status(self, workflow_instance_id: str) -> builtins.dict[str, Any] | None:
        """Get workflow instance status."""
        with self._lock:
            instance = self.active_workflows.get(workflow_instance_id)

            if not instance:
                return None

            return {
                "workflow_id": instance["workflow_id"],
                "instance_id": instance["instance_id"],
                "state": instance["state"],
                "current_step": instance.get("current_step", 0),
                "completed_steps": len(instance["completed_steps"]),
                "total_steps": len(instance["definition"].get("steps", [])),
                "started_at": instance["started_at"].isoformat(),
                "completed_at": instance.get("completed_at").isoformat()
                if instance.get("completed_at")
                else None,
                "context": instance["context"],
            }

    def get_orchestrator_status(self) -> builtins.dict[str, Any]:
        """Get orchestrator status."""
        with self._lock:
            active_count = len(
                [i for i in self.active_workflows.values() if i["state"] == "running"]
            )
            completed_count = len(
                [i for i in self.active_workflows.values() if i["state"] == "completed"]
            )
            failed_count = len(
                [i for i in self.active_workflows.values() if i["state"] == "failed"]
            )

            return {
                "total_workflows": len(self.workflows),
                "active_instances": active_count,
                "completed_instances": completed_count,
                "failed_instances": failed_count,
                "registered_patterns": sum(
                    len(patterns) for patterns in self.event_patterns.values()
                ),
            }


def create_event_driven_architecture(
    broker_config: MessageBrokerConfig | None = None,
) -> builtins.dict[str, Any]:
    """Create event-driven architecture components."""

    # Create event bus based on configuration
    if broker_config and broker_config.broker_type == "rabbitmq":
        event_bus = RabbitMQEventBus(broker_config)
    else:
        event_bus = InMemoryEventBus()

    # Create supporting components
    message_transformer = MessageTransformer()
    event_orchestrator = EventOrchestrator(event_bus)

    return {
        "event_bus": event_bus,
        "message_transformer": message_transformer,
        "event_orchestrator": event_orchestrator,
    }
