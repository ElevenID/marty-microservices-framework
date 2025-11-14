"""
Extended Messaging Architecture Design for Marty Microservices Framework

This document outlines the design for extended messaging options including NATS,
AWS SNS, and unified event-bus abstractions with pattern examples.
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Union


# Enhanced Backend Types
class MessageBackendType(Enum):
    """Extended message backend types."""

    MEMORY = "memory"
    RABBITMQ = "rabbitmq"
    REDIS = "redis"
    AWS_SQS = "aws_sqs"
    AWS_SNS = "aws_sns"  # New
    NATS = "nats"  # New
    KAFKA = "kafka"


class MessagingPattern(Enum):
    """Core messaging patterns supported."""

    PUBLISH_SUBSCRIBE = "pub_sub"
    REQUEST_RESPONSE = "req_resp"
    STREAM_PROCESSING = "streaming"
    POINT_TO_POINT = "p2p"
    BROADCAST = "broadcast"


class DeliveryGuarantee(Enum):
    """Message delivery guarantees."""

    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


@dataclass
class MessagingPatternConfig:
    """Configuration for specific messaging patterns."""

    pattern: MessagingPattern
    delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE
    timeout: timedelta = timedelta(seconds=30)
    retry_count: int = 3
    dead_letter_enabled: bool = True
    ordering_enabled: bool = False
    content_based_routing: bool = False
    options: dict[str, Any] | None = None

    def __post_init__(self):
        if self.options is None:
            self.options = {}


@dataclass
class MessageMetadata:
    """Enhanced message metadata."""

    message_id: str
    correlation_id: str | None = None
    causation_id: str | None = None
    timestamp: datetime = None
    ttl: timedelta | None = None
    priority: int = 0
    content_type: str = "application/json"
    encoding: str = "utf-8"
    headers: dict[str, Any] | None = None
    routing_key: str | None = None
    reply_to: str | None = None
    message_type: str | None = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.headers is None:
            self.headers = {}


# Generic Message Interface
class GenericMessage(ABC):
    """Generic message interface for all messaging patterns."""

    def __init__(self, payload: Any, metadata: MessageMetadata, pattern: MessagingPattern):
        self.payload = payload
        self.metadata = metadata
        self.pattern = pattern
        self._acknowledged = False
        self._processing_started = False

    @abstractmethod
    async def ack(self) -> bool:
        """Acknowledge message processing."""

    @abstractmethod
    async def nack(self, requeue: bool = True) -> bool:
        """Negative acknowledge message."""

    @abstractmethod
    async def reject(self, requeue: bool = False) -> bool:
        """Reject message processing."""


# Enhanced Backend Interface
class EnhancedMessageBackend(ABC):
    """Enhanced message backend supporting multiple patterns."""

    @abstractmethod
    async def connect(self) -> bool:
        """Connect to message backend."""

    @abstractmethod
    async def disconnect(self) -> bool:
        """Disconnect from message backend."""

    @abstractmethod
    async def publish(
        self, topic: str, message: GenericMessage, pattern_config: MessagingPatternConfig
    ) -> bool:
        """Publish message using specified pattern."""

    @abstractmethod
    async def subscribe(
        self,
        topic: str,
        handler: Callable[[GenericMessage], Awaitable[bool]],
        pattern_config: MessagingPatternConfig,
    ) -> str:
        """Subscribe to topic with pattern configuration."""

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe from topic."""

    @abstractmethod
    async def request(
        self, topic: str, message: GenericMessage, timeout: timedelta = timedelta(seconds=30)
    ) -> GenericMessage:
        """Send request and wait for response."""

    @abstractmethod
    async def reply(self, original_message: GenericMessage, response: GenericMessage) -> bool:
        """Reply to a request message."""

    @abstractmethod
    def supports_pattern(self, pattern: MessagingPattern) -> bool:
        """Check if backend supports messaging pattern."""

    @abstractmethod
    def get_supported_guarantees(self) -> list[DeliveryGuarantee]:
        """Get supported delivery guarantees."""


# Unified Event Bus Interface
class UnifiedEventBus(ABC):
    """Unified event bus supporting all messaging patterns."""

    @abstractmethod
    async def publish_event(
        self, event_type: str, data: Any, metadata: MessageMetadata | None = None
    ) -> bool:
        """Publish domain event (pub/sub pattern)."""

    @abstractmethod
    async def send_command(
        self,
        command_type: str,
        data: Any,
        target_service: str,
        metadata: MessageMetadata | None = None,
    ) -> bool:
        """Send command (point-to-point pattern)."""

    @abstractmethod
    async def query(
        self,
        query_type: str,
        data: Any,
        target_service: str,
        timeout: timedelta = timedelta(seconds=30),
    ) -> Any:
        """Send query and wait for response (request/response pattern)."""

    @abstractmethod
    async def stream_events(
        self, stream_name: str, events: list[Any], partition_key: str | None = None
    ) -> bool:
        """Stream events for processing (streaming pattern)."""

    @abstractmethod
    async def subscribe_to_events(
        self,
        event_types: list[str],
        handler: Callable[[str, Any, MessageMetadata], Awaitable[bool]],
        consumer_group: str | None = None,
    ) -> str:
        """Subscribe to domain events."""

    @abstractmethod
    async def handle_commands(
        self,
        command_types: list[str],
        handler: Callable[[str, Any, MessageMetadata], Awaitable[bool]],
        service_name: str,
    ) -> str:
        """Handle incoming commands."""

    @abstractmethod
    async def handle_queries(
        self,
        query_types: list[str],
        handler: Callable[[str, Any, MessageMetadata], Awaitable[Any]],
        service_name: str,
    ) -> str:
        """Handle incoming queries."""

    @abstractmethod
    async def process_stream(
        self,
        stream_name: str,
        processor: Callable[[list[Any]], Awaitable[bool]],
        consumer_group: str,
        batch_size: int = 100,
    ) -> str:
        """Process event stream."""


# Backend-Specific Configurations
@dataclass
class NATSConfig:
    """NATS-specific configuration."""

    servers: list[str] | None = None
    user: str | None = None
    password: str | None = None
    token: str | None = None
    tls_enabled: bool = False
    jetstream_enabled: bool = True
    max_reconnect_attempts: int = 10
    reconnect_time_wait: int = 2

    def __post_init__(self):
        if self.servers is None:
            self.servers = ["nats://localhost:4222"]


@dataclass
class AWSSNSConfig:
    """AWS SNS-specific configuration."""

    region_name: str = "us-east-1"
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    endpoint_url: str | None = None
    fifo_topics: bool = False
    content_based_deduplication: bool = False
    kms_master_key_id: str | None = None


# Pattern Selection Guidelines
class PatternSelector:
    """Helper class to select appropriate messaging patterns."""

    @staticmethod
    def recommend_pattern(
        use_case: str,
        durability_required: bool = True,
        ordering_required: bool = False,
        response_needed: bool = False,
        high_throughput: bool = False,
    ) -> MessagingPattern:
        """Recommend messaging pattern based on use case characteristics."""

        if response_needed:
            return MessagingPattern.REQUEST_RESPONSE

        if high_throughput and ordering_required:
            return MessagingPattern.STREAM_PROCESSING

        if "notification" in use_case.lower() or "event" in use_case.lower():
            return MessagingPattern.PUBLISH_SUBSCRIBE

        if "command" in use_case.lower() or "task" in use_case.lower():
            return MessagingPattern.POINT_TO_POINT

        if "broadcast" in use_case.lower():
            return MessagingPattern.BROADCAST

        return MessagingPattern.PUBLISH_SUBSCRIBE  # Default

    @staticmethod
    def recommend_backend(
        pattern: MessagingPattern,
        scale_requirements: str = "medium",
        cloud_preference: str = "agnostic",
    ) -> MessageBackendType:
        """Recommend backend based on pattern and requirements."""

        pattern_backend_map = {
            MessagingPattern.PUBLISH_SUBSCRIBE: {
                "low": MessageBackendType.REDIS,
                "medium": MessageBackendType.NATS,
                "high": MessageBackendType.KAFKA,
            },
            MessagingPattern.REQUEST_RESPONSE: {
                "low": MessageBackendType.NATS,
                "medium": MessageBackendType.RABBITMQ,
                "high": MessageBackendType.NATS,
            },
            MessagingPattern.STREAM_PROCESSING: {
                "low": MessageBackendType.REDIS,
                "medium": MessageBackendType.KAFKA,
                "high": MessageBackendType.KAFKA,
            },
            MessagingPattern.POINT_TO_POINT: {
                "low": MessageBackendType.RABBITMQ,
                "medium": MessageBackendType.AWS_SQS,
                "high": MessageBackendType.RABBITMQ,
            },
            MessagingPattern.BROADCAST: {
                "low": MessageBackendType.REDIS,
                "medium": MessageBackendType.AWS_SNS,
                "high": MessageBackendType.NATS,
            },
        }

        if cloud_preference == "aws":
            if pattern in [MessagingPattern.POINT_TO_POINT]:
                return MessageBackendType.AWS_SQS
            elif pattern in [MessagingPattern.PUBLISH_SUBSCRIBE, MessagingPattern.BROADCAST]:
                return MessageBackendType.AWS_SNS

        return pattern_backend_map.get(pattern, {}).get(scale_requirements, MessageBackendType.NATS)


# Integration with Saga Pattern
class SagaEventBus:
    """Event bus specifically designed for Saga pattern integration."""

    def __init__(self, unified_bus: UnifiedEventBus):
        self.unified_bus = unified_bus
        self.saga_subscriptions: dict[str, str] = {}

    async def publish_saga_event(
        self, saga_id: str, event_type: str, event_data: Any, step_id: str | None = None
    ) -> bool:
        """Publish saga-related event."""
        metadata = MessageMetadata(
            message_id=f"saga-{saga_id}-{datetime.utcnow().isoformat()}",
            correlation_id=saga_id,
            message_type=event_type,
            headers={"saga_id": saga_id, "step_id": step_id, "event_category": "saga"},
        )

        return await self.unified_bus.publish_event(
            event_type=f"saga.{event_type}", data=event_data, metadata=metadata
        )

    async def subscribe_to_saga_events(
        self, saga_id: str, handler: Callable[[str, Any], Awaitable[bool]]
    ) -> str:
        """Subscribe to events for a specific saga."""

        async def saga_handler(event_type: str, data: Any, metadata: MessageMetadata) -> bool:
            if metadata.headers and metadata.headers.get("saga_id") == saga_id:
                return await handler(event_type, data)
            return True  # Ignore events for other sagas

        subscription_id = await self.unified_bus.subscribe_to_events(
            event_types=[f"saga.{saga_id}.*"], handler=saga_handler
        )

        self.saga_subscriptions[saga_id] = subscription_id
        return subscription_id

    async def send_saga_command(
        self,
        saga_id: str,
        command_type: str,
        command_data: Any,
        target_service: str,
        step_id: str | None = None,
    ) -> bool:
        """Send command as part of saga execution."""
        metadata = MessageMetadata(
            message_id=f"saga-cmd-{saga_id}-{datetime.utcnow().isoformat()}",
            correlation_id=saga_id,
            message_type=command_type,
            headers={"saga_id": saga_id, "step_id": step_id, "command_category": "saga"},
        )

        return await self.unified_bus.send_command(
            command_type=f"saga.{command_type}",
            data=command_data,
            target_service=target_service,
            metadata=metadata,
        )


# When to Choose Which Pattern - Decision Matrix
PATTERN_DECISION_MATRIX = {
    "user_registration": {
        "pattern": MessagingPattern.PUBLISH_SUBSCRIBE,
        "backend": MessageBackendType.NATS,
        "reason": "Multiple services need to react to user registration (email, analytics, etc.)",
    },
    "order_processing": {
        "pattern": MessagingPattern.STREAM_PROCESSING,
        "backend": MessageBackendType.KAFKA,
        "reason": "High throughput, ordering matters, complex processing pipeline",
    },
    "payment_authorization": {
        "pattern": MessagingPattern.REQUEST_RESPONSE,
        "backend": MessageBackendType.NATS,
        "reason": "Immediate response required, critical operation",
    },
    "inventory_update": {
        "pattern": MessagingPattern.POINT_TO_POINT,
        "backend": MessageBackendType.AWS_SQS,
        "reason": "Single consumer, guaranteed delivery, idempotent operation",
    },
    "system_alerts": {
        "pattern": MessagingPattern.BROADCAST,
        "backend": MessageBackendType.AWS_SNS,
        "reason": "All services/operators need immediate notification",
    },
    "data_analytics": {
        "pattern": MessagingPattern.STREAM_PROCESSING,
        "backend": MessageBackendType.KAFKA,
        "reason": "Continuous data flow, replay capability, multiple consumers",
    },
    "task_queue": {
        "pattern": MessagingPattern.POINT_TO_POINT,
        "backend": MessageBackendType.RABBITMQ,
        "reason": "Worker pools, priority queues, complex routing",
    },
}
