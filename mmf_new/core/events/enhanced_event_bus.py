"""
Enhanced Event Bus with Kafka Support Only

This module provides a unified, enterprise-grade event bus with:
- Kafka-only backend support
- Robust event routing and filtering
- Plugin subscription support
- Circuit breaker and retry mechanisms
- Event replay capabilities
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Generic, Optional, TypeVar

from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session, sessionmaker

logger = logging.getLogger(__name__)

# Type variables
E = TypeVar("E", bound="BaseEvent")
H = TypeVar("H", bound="EventHandler")

# Base for persistence tables
PersistenceBase = declarative_base()


class EventStatus(Enum):
    """Event processing status for outbox pattern."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"


@dataclass
class KafkaConfig:
    """Configuration for Kafka backend."""

    bootstrap_servers: list[str] = field(default_factory=lambda: ["localhost:9092"])
    security_protocol: str = "PLAINTEXT"
    sasl_mechanism: str | None = None
    sasl_plain_username: str | None = None
    sasl_plain_password: str | None = None
    consumer_group_id: str = "marty-enhanced-event-bus"
    auto_offset_reset: str = "latest"
    enable_auto_commit: bool = True
    max_poll_records: int = 500
    session_timeout_ms: int = 30000
    heartbeat_interval_ms: int = 3000


@dataclass
class OutboxConfig:
    """Configuration for transactional outbox pattern."""

    database_url: str
    batch_size: int = 100
    poll_interval: timedelta = field(default_factory=lambda: timedelta(seconds=5))
    max_retries: int = 3
    retry_delay: timedelta = field(default_factory=lambda: timedelta(seconds=30))
    enable_dead_letter_queue: bool = True


class EventCategory(Enum):
    """Event category classification."""

    DOMAIN = "domain"
    INTEGRATION = "integration"
    AUDIT = "audit"
    SYSTEM = "system"
    NOTIFICATION = "notification"


class EventBusMode(Enum):
    """Event bus operational modes."""

    DIRECT = "direct"  # Direct publishing to Kafka (no outbox)
    TRANSACTIONAL = "transactional"  # Outbox pattern for ACID compliance
    TESTING = "testing"  # Special mode for testing scenarios


class EventBackendType(Enum):
    """Event backend type enumeration."""

    KAFKA = "kafka"


class EventPriority(Enum):
    """Event processing priority."""

    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


class DeliveryGuarantee(Enum):
    """Event delivery guarantees."""

    AT_MOST_ONCE = "at_most_once"
    AT_LEAST_ONCE = "at_least_once"
    EXACTLY_ONCE = "exactly_once"


@dataclass
class EventMetadata:
    """Enhanced event metadata."""

    event_id: str
    event_type: str
    timestamp: datetime
    correlation_id: str | None = None
    causation_id: str | None = None
    user_id: str | None = None
    tenant_id: str | None = None
    source_service: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    version: int = 1
    priority: EventPriority = EventPriority.NORMAL
    headers: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    expiry: datetime | None = None


@dataclass
class EventFilter:
    """Enhanced event filtering criteria."""

    event_types: list[str] | None = None
    source_services: list[str] | None = None
    tenant_ids: list[str] | None = None
    correlation_ids: list[str] | None = None
    tags: list[str] | None = None
    priority_min: EventPriority | None = None
    timestamp_range: tuple[datetime, datetime] | None = None
    custom_filters: dict[str, Any] = field(default_factory=dict)


class BaseEvent:
    """Enhanced base event with comprehensive metadata."""

    def __init__(
        self,
        event_type: str | None = None,
        data: dict[str, Any] | None = None,
        metadata: EventMetadata | None = None,
        **kwargs,
    ):
        self.event_type = event_type or self.__class__.__name__
        self.data = data or {}

        # Generate metadata if not provided
        if metadata is None:
            self.metadata = EventMetadata(
                event_id=str(uuid.uuid4()),
                event_type=self.event_type,
                timestamp=datetime.now(timezone.utc),
                **kwargs,
            )
        else:
            self.metadata = metadata

    @property
    def event_id(self) -> str:
        """Get the event ID."""
        return self.metadata.event_id

    @property
    def timestamp(self) -> datetime:
        """Get the event timestamp."""
        return self.metadata.timestamp

    def matches_filter(self, event_filter: EventFilter) -> bool:
        """Check if event matches the given filter."""
        if event_filter.event_types and self.event_type not in event_filter.event_types:
            return False

        if (
            event_filter.source_services
            and self.metadata.source_service not in event_filter.source_services
        ):
            return False

        if event_filter.tenant_ids and self.metadata.tenant_id not in event_filter.tenant_ids:
            return False

        if (
            event_filter.correlation_ids
            and self.metadata.correlation_id not in event_filter.correlation_ids
        ):
            return False

        if event_filter.tags and not any(tag in self.metadata.tags for tag in event_filter.tags):
            return False

        if (
            event_filter.priority_min
            and self.metadata.priority.value < event_filter.priority_min.value
        ):
            return False

        if event_filter.timestamp_range:
            start, end = event_filter.timestamp_range
            if not (start <= self.timestamp <= end):
                return False

        # Apply custom filters
        for key, value in event_filter.custom_filters.items():
            if key in self.data and self.data[key] != value:
                return False

        return True

    def to_dict(self) -> dict[str, Any]:
        """Convert event to dictionary representation."""
        return {
            "event_type": self.event_type,
            "data": self.data,
            "metadata": {
                "event_id": self.metadata.event_id,
                "event_type": self.metadata.event_type,
                "timestamp": self.metadata.timestamp.isoformat(),
                "correlation_id": self.metadata.correlation_id,
                "causation_id": self.metadata.causation_id,
                "user_id": self.metadata.user_id,
                "tenant_id": self.metadata.tenant_id,
                "source_service": self.metadata.source_service,
                "trace_id": self.metadata.trace_id,
                "span_id": self.metadata.span_id,
                "version": self.metadata.version,
                "priority": self.metadata.priority.value,
                "headers": self.metadata.headers,
                "tags": self.metadata.tags,
                "expiry": self.metadata.expiry.isoformat() if self.metadata.expiry else None,
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> BaseEvent:
        """Create event from dictionary representation."""
        metadata_dict = data.get("metadata", {})

        # Parse timestamps
        timestamp = datetime.fromisoformat(
            metadata_dict.get("timestamp", datetime.now(timezone.utc).isoformat())
        )
        expiry = None
        if metadata_dict.get("expiry"):
            expiry = datetime.fromisoformat(metadata_dict["expiry"])

        metadata = EventMetadata(
            event_id=metadata_dict.get("event_id", str(uuid.uuid4())),
            event_type=metadata_dict.get("event_type", data.get("event_type", "BaseEvent")),
            timestamp=timestamp,
            correlation_id=metadata_dict.get("correlation_id"),
            causation_id=metadata_dict.get("causation_id"),
            user_id=metadata_dict.get("user_id"),
            tenant_id=metadata_dict.get("tenant_id"),
            source_service=metadata_dict.get("source_service"),
            trace_id=metadata_dict.get("trace_id"),
            span_id=metadata_dict.get("span_id"),
            version=metadata_dict.get("version", 1),
            priority=EventPriority(metadata_dict.get("priority", EventPriority.NORMAL.value)),
            headers=metadata_dict.get("headers", {}),
            tags=metadata_dict.get("tags", []),
            expiry=expiry,
        )

        return cls(event_type=data.get("event_type"), data=data.get("data", {}), metadata=metadata)


class EventHandler(ABC, Generic[E]):
    """Enhanced base class for event handlers."""

    def __init__(
        self,
        handler_id: str | None = None,
        priority: int = 0,
        max_concurrent: int = 1,
        timeout: timedelta | None = None,
    ):
        self.handler_id = handler_id or str(uuid.uuid4())
        self.priority = priority  # Higher numbers = higher priority
        self.max_concurrent = max_concurrent
        self.timeout = timeout or timedelta(seconds=30)
        self._active_tasks = 0
        self._lock = asyncio.Lock()

    @abstractmethod
    async def handle(self, event: E) -> None:
        """Handle the event."""
        ...

    @abstractmethod
    def can_handle(self, event: BaseEvent) -> bool:
        """Check if this handler can handle the event."""
        ...

    @property
    @abstractmethod
    def event_types(self) -> list[str]:
        """List of event types this handler can process."""
        ...

    async def safe_handle(self, event: E) -> bool:
        """Safely handle event with concurrency control and timeout."""
        async with self._lock:
            if self._active_tasks >= self.max_concurrent:
                return False
            self._active_tasks += 1

        try:
            await asyncio.wait_for(self.handle(event), timeout=self.timeout.total_seconds())
            return True
        except asyncio.TimeoutError:
            logger.error(f"Handler {self.handler_id} timed out processing event {event.event_id}")
            return False
        except Exception as e:
            logger.error(f"Handler {self.handler_id} failed processing event {event.event_id}: {e}")
            return False
        finally:
            async with self._lock:
                self._active_tasks -= 1


class PluginEventHandler(EventHandler[BaseEvent]):
    """Specialized event handler for plugin integration."""

    def __init__(
        self,
        plugin_id: str,
        plugin_name: str,
        event_filter: EventFilter,
        handler_func: Callable[[BaseEvent], Any],
        **kwargs,
    ):
        super().__init__(handler_id=f"plugin-{plugin_id}", **kwargs)
        self.plugin_id = plugin_id
        self.plugin_name = plugin_name
        self.event_filter = event_filter
        self.handler_func = handler_func

    async def handle(self, event: BaseEvent) -> None:
        """Handle event for plugin."""
        if asyncio.iscoroutinefunction(self.handler_func):
            await self.handler_func(event)
        else:
            self.handler_func(event)

    def can_handle(self, event: BaseEvent) -> bool:
        """Check if event matches plugin filter."""
        return event.matches_filter(self.event_filter)

    @property
    def event_types(self) -> list[str]:
        """Return event types from filter."""
        return self.event_filter.event_types or ["*"]


class EventBus(ABC):
    """Enhanced abstract event bus interface."""

    @abstractmethod
    async def publish(
        self,
        event: BaseEvent,
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
        delay: timedelta | None = None,
    ) -> None:
        """Publish an event with delivery guarantees."""
        ...

    @abstractmethod
    async def publish_batch(
        self,
        events: list[BaseEvent],
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
    ) -> None:
        """Publish multiple events as a batch."""
        ...

    @abstractmethod
    async def subscribe(
        self, handler: EventHandler, event_filter: EventFilter | None = None
    ) -> str:
        """Subscribe an event handler with optional filtering."""
        ...

    @abstractmethod
    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe a handler by subscription ID."""
        ...

    @abstractmethod
    async def start(self) -> None:
        """Start the event bus."""
        ...

    @abstractmethod
    async def stop(self) -> None:
        """Stop the event bus."""
        ...


class OutboxEvent(PersistenceBase):
    """Outbox table for transactional event publishing."""

    __tablename__ = "event_outbox"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    event_id = Column(String(36), nullable=False, unique=True, index=True)
    event_type = Column(String(255), nullable=False, index=True)
    event_data = Column(Text, nullable=False)
    event_metadata = Column(Text, nullable=True)
    status = Column(String(50), nullable=False, default=EventStatus.PENDING.value, index=True)
    priority = Column(Integer, nullable=False, default=EventPriority.NORMAL.value, index=True)
    created_at = Column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        index=True,
    )
    scheduled_at = Column(DateTime(timezone=True), nullable=True, index=True)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    error_message = Column(Text, nullable=True)
    correlation_id = Column(String(255), nullable=True, index=True)
    source_service = Column(String(255), nullable=True, index=True)
    tenant_id = Column(String(255), nullable=True, index=True)
    is_dead_letter = Column(Boolean, nullable=False, default=False, index=True)


class DeadLetterEvent(PersistenceBase):
    """Dead letter queue for failed events."""

    __tablename__ = "event_dead_letter"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    original_event_id = Column(String(36), nullable=False, index=True)
    event_type = Column(String(255), nullable=False, index=True)
    event_data = Column(Text, nullable=False)
    event_metadata = Column(Text, nullable=True)
    failure_reason = Column(Text, nullable=False)
    failed_at = Column(
        DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    attempts_made = Column(Integer, nullable=False)
    can_retry = Column(Boolean, nullable=False, default=True)
    source_service = Column(String(255), nullable=True, index=True)


class EnhancedEventBus(EventBus):
    """Kafka-only enhanced event bus implementation with transactional outbox pattern."""

    def __init__(
        self,
        kafka_config: KafkaConfig,
        outbox_config: OutboxConfig | None = None,
        max_retries: int = 3,
        retry_delay: timedelta = timedelta(seconds=1),
        batch_size: int = 100,
        batch_timeout: timedelta = timedelta(seconds=5),
        enable_dlq: bool = True,
        dlq_topic_suffix: str = ".dlq",
    ):
        """Initialize the enhanced event bus with Kafka support and optional outbox pattern."""
        self.kafka_config = kafka_config
        self.outbox_config = outbox_config
        self._backend_type = EventBackendType.KAFKA
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.enable_dlq = enable_dlq
        self.dlq_topic_suffix = dlq_topic_suffix

        # Event handlers and subscriptions
        self._handlers: dict[str, EventHandler] = {}
        self._subscriptions: dict[str, list[str]] = defaultdict(list)
        self._plugin_handlers: dict[str, PluginEventHandler] = {}

        # Kafka components
        self._kafka_producer: AIOKafkaProducer | None = None
        self._kafka_consumers: dict[str, AIOKafkaConsumer] = {}
        self._consumer_tasks: dict[str, asyncio.Task] = {}

        # Database components for outbox pattern
        self._engine = None
        self._session_factory = None
        self._outbox_processor_task: asyncio.Task | None = None

        # Event bus state
        self._running = False
        self._lock = asyncio.Lock()

        # Initialize database if outbox is configured
        if self.outbox_config:
            self._init_database()

    def _init_database(self) -> None:
        """Initialize database engine and session factory for outbox pattern."""
        if not self.outbox_config:
            return

        self._engine = create_engine(self.outbox_config.database_url)
        self._session_factory = sessionmaker(bind=self._engine)

        # Create tables if they don't exist
        PersistenceBase.metadata.create_all(self._engine)
        logger.info("Database initialized for outbox pattern")

    async def _save_to_outbox(self, event: BaseEvent, session: Session) -> None:
        """Save event to outbox table within transaction."""
        outbox_event = OutboxEvent(
            event_id=event.event_id,
            event_type=event.event_type,
            event_data=json.dumps(event.to_dict()),
            event_metadata=json.dumps(event.metadata.__dict__) if event.metadata else None,
            priority=event.metadata.priority.value,
            correlation_id=event.metadata.correlation_id,
            source_service=event.metadata.source_service,
            tenant_id=event.metadata.tenant_id,
            expires_at=event.metadata.expiry,
            max_attempts=self.outbox_config.max_retries if self.outbox_config else 3,
        )
        session.add(outbox_event)
        logger.debug(f"Saved event {event.event_id} to outbox")

    async def publish_transactional(
        self,
        event: BaseEvent,
        session: Session,
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
    ) -> None:
        """Publish event using transactional outbox pattern."""
        if not self.outbox_config:
            # Fall back to direct publishing if no outbox configured
            await self.publish(event, delivery_guarantee)
            return

        # Save to outbox within the provided transaction
        await self._save_to_outbox(event, session)
        logger.info(f"Event {event.event_id} saved to outbox for transactional publishing")

    # ENHANCED UNIFIED PUBLISHING METHODS
    async def publish_with_retry(
        self, event: BaseEvent, max_retries: int = 3, backoff_factor: float = 1.0
    ) -> None:
        """
        Publish event with automatic retry logic and exponential backoff.
        """
        for attempt in range(max_retries + 1):
            try:
                await self.publish(event)
                return
            except Exception as e:
                if attempt == max_retries:
                    logger.error(
                        f"Failed to publish event {event.event_id} after {max_retries} retries: {e}"
                    )
                    raise

                wait_time = backoff_factor * (2**attempt)
                logger.warning(
                    f"Publish attempt {attempt + 1} failed for event {event.event_id}, retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)

    async def publish_scheduled(
        self, event: BaseEvent, scheduled_for: datetime, session: Session | None = None
    ) -> None:
        """
        Schedule event for future publishing using the outbox pattern.
        """
        if not self.outbox_config:
            raise ValueError("Scheduled publishing requires outbox pattern to be enabled")

        delay_seconds = (scheduled_for - datetime.now(timezone.utc)).total_seconds()
        if delay_seconds <= 0:
            # If scheduled time is in the past, publish immediately
            if session:
                await self.publish_transactional(event, session)
            else:
                await self.publish(event)
            return

        # Modify event metadata to include scheduled time
        event.metadata.expiry = scheduled_for

        if session:
            await self.publish_transactional(event, session)
        else:
            # Create a temporary session for this operation
            if self._session_factory:
                with self._session_factory() as temp_session:
                    await self.publish_transactional(event, temp_session)
                    temp_session.commit()

    # PATTERN-BASED PUBLISHING METHODS
    async def publish_domain_aggregate_event(
        self,
        aggregate_type: str,
        aggregate_id: str,
        event_type: str,
        event_data: dict[str, Any],
        version: int = 1,
    ) -> None:
        """
        Publish domain event following DDD aggregate pattern.
        """
        event = BaseEvent(
            event_type=f"{aggregate_type}.{event_type}",
            data={
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "version": version,
                **event_data,
            },
            metadata=EventMetadata(
                event_id=str(uuid.uuid4()),
                event_type=f"{aggregate_type}.{event_type}",
                timestamp=datetime.now(timezone.utc),
                correlation_id=aggregate_id,
            ),
        )
        await self.publish(event)

    async def publish_saga_event(
        self,
        saga_id: str,
        saga_type: str,
        event_type: str,
        event_data: dict[str, Any],
        session: Session | None = None,
    ) -> None:
        """
        Publish saga orchestration event with transactional guarantees.
        """
        event = BaseEvent(
            event_type=f"saga.{saga_type}.{event_type}",
            data={"saga_id": saga_id, "saga_type": saga_type, **event_data},
            metadata=EventMetadata(
                event_id=str(uuid.uuid4()),
                event_type=f"saga.{saga_type}.{event_type}",
                timestamp=datetime.now(timezone.utc),
                correlation_id=saga_id,
            ),
        )

        if session:
            await self.publish_transactional(event, session)
        else:
            await self.publish(event)

    async def _process_outbox_events(self) -> None:
        """Background task to process events from outbox and publish to Kafka."""
        if not self.outbox_config or not self._session_factory:
            return

        while self._running:
            try:
                with self._session_factory() as session:
                    # Get pending events from outbox
                    pending_events = (
                        session.query(OutboxEvent)
                        .filter(
                            OutboxEvent.status == EventStatus.PENDING.value,
                            OutboxEvent.attempts < OutboxEvent.max_attempts,
                        )
                        .order_by(OutboxEvent.priority.desc(), OutboxEvent.created_at.asc())
                        .limit(self.outbox_config.batch_size)
                        .all()
                    )

                    for outbox_event in pending_events:
                        try:
                            # Mark as processing
                            outbox_event.status = EventStatus.PROCESSING.value
                            outbox_event.attempts += 1
                            session.commit()

                            # Check if event has expired
                            if (
                                outbox_event.expires_at
                                and datetime.now(timezone.utc) > outbox_event.expires_at
                            ):
                                outbox_event.status = EventStatus.FAILED.value
                                outbox_event.error_message = "Event expired"
                                session.commit()
                                continue

                            # Reconstruct and publish event
                            event_data = json.loads(outbox_event.event_data)
                            event = BaseEvent.from_dict(event_data)

                            # Publish to Kafka
                            await self._publish_to_kafka(event)

                            # Mark as completed
                            outbox_event.status = EventStatus.COMPLETED.value
                            outbox_event.processed_at = datetime.now(timezone.utc)
                            outbox_event.error_message = None
                            session.commit()

                        except Exception as e:
                            # Handle failure
                            if outbox_event.attempts >= outbox_event.max_attempts:
                                await self._move_to_dead_letter(outbox_event, str(e), session)
                            else:
                                outbox_event.status = EventStatus.PENDING.value
                                outbox_event.error_message = str(e)
                                session.commit()

                            logger.error(
                                f"Failed to process outbox event {outbox_event.event_id}: {e}"
                            )

                # Wait before next batch
                await asyncio.sleep(self.outbox_config.poll_interval.total_seconds())

            except Exception as e:
                logger.error(f"Error in outbox processor: {e}")
                await asyncio.sleep(self.outbox_config.retry_delay.total_seconds())

    async def _move_to_dead_letter(
        self, outbox_event: OutboxEvent, failure_reason: str, session: Session
    ) -> None:
        """Move failed event to dead letter queue."""
        if not self.outbox_config or not self.outbox_config.enable_dead_letter_queue:
            return

        dead_letter = DeadLetterEvent(
            original_event_id=outbox_event.event_id,
            event_type=outbox_event.event_type,
            event_data=outbox_event.event_data,
            event_metadata=outbox_event.event_metadata,
            failure_reason=failure_reason,
            attempts_made=outbox_event.attempts,
            source_service=outbox_event.source_service,
        )
        session.add(dead_letter)

        # Mark original as dead letter
        outbox_event.status = EventStatus.DEAD_LETTER.value
        outbox_event.is_dead_letter = True
        outbox_event.error_message = failure_reason
        session.commit()

        logger.info(f"Moved event {outbox_event.event_id} to dead letter queue")

    async def retry_dead_letter(self, dead_letter_id: str) -> bool:
        """Retry a dead letter event by moving it back to the outbox."""
        if not self.outbox_config or not self._session_factory:
            return False

        with self._session_factory() as session:
            dead_letter = (
                session.query(DeadLetterEvent)
                .filter(DeadLetterEvent.id == dead_letter_id, DeadLetterEvent.can_retry)
                .first()
            )

            if not dead_letter:
                return False

            try:
                # Reconstruct event data
                event_data = json.loads(dead_letter.event_data)
                event = BaseEvent.from_dict(event_data)

                # Create new outbox entry
                await self._save_to_outbox(event, session)

                # Mark dead letter as processed
                dead_letter.can_retry = False
                session.commit()

                logger.info(f"Retried dead letter event {dead_letter_id}")
                return True

            except Exception as e:
                logger.error(f"Failed to retry dead letter event {dead_letter_id}: {e}")
                return False

    async def get_dead_letters(self, limit: int = 100, event_type: str | None = None) -> list[dict]:
        """Get dead letter events for inspection."""
        if not self.outbox_config or not self._session_factory:
            return []

        with self._session_factory() as session:
            query = session.query(DeadLetterEvent)
            if event_type:
                query = query.filter(DeadLetterEvent.event_type == event_type)

            dead_letters = query.order_by(DeadLetterEvent.failed_at.desc()).limit(limit).all()

            result = []
            for dl in dead_letters:
                result.append(
                    {
                        "id": dl.id,
                        "original_event_id": dl.original_event_id,
                        "event_type": dl.event_type,
                        "failure_reason": dl.failure_reason,
                        "failed_at": dl.failed_at.isoformat(),
                        "attempts_made": dl.attempts_made,
                        "can_retry": dl.can_retry,
                        "source_service": dl.source_service,
                    }
                )

            return result

    async def _get_topic_name(self, event_type: str) -> str:
        """Get Kafka topic name for event type."""
        # Use event type as topic name, replacing dots with underscores
        return event_type.replace(".", "_").lower()

    async def _start_kafka_producer(self) -> None:
        """Start Kafka producer."""
        if self._kafka_producer is not None:
            return

        producer_config = {
            "bootstrap_servers": self.kafka_config.bootstrap_servers,
            "security_protocol": self.kafka_config.security_protocol,
        }

        # Add SASL configuration if provided
        if self.kafka_config.sasl_mechanism:
            producer_config.update(
                {
                    "sasl_mechanism": self.kafka_config.sasl_mechanism,
                    "sasl_plain_username": self.kafka_config.sasl_plain_username,
                    "sasl_plain_password": self.kafka_config.sasl_plain_password,
                }
            )

        self._kafka_producer = AIOKafkaProducer(**producer_config)
        await self._kafka_producer.start()
        logger.info("Kafka producer started")

    async def _stop_kafka_producer(self) -> None:
        """Stop Kafka producer."""
        if self._kafka_producer:
            await self._kafka_producer.stop()
            self._kafka_producer = None
            logger.info("Kafka producer stopped")

    async def _start_kafka_consumer(self, topic: str) -> None:
        """Start Kafka consumer for a topic."""
        if topic in self._kafka_consumers:
            return

        consumer_config = {
            "bootstrap_servers": self.kafka_config.bootstrap_servers,
            "group_id": self.kafka_config.consumer_group_id,
            "auto_offset_reset": self.kafka_config.auto_offset_reset,
            "enable_auto_commit": self.kafka_config.enable_auto_commit,
            "max_poll_records": self.kafka_config.max_poll_records,
            "session_timeout_ms": self.kafka_config.session_timeout_ms,
            "heartbeat_interval_ms": self.kafka_config.heartbeat_interval_ms,
            "security_protocol": self.kafka_config.security_protocol,
        }

        # Add SASL configuration if provided
        if self.kafka_config.sasl_mechanism:
            consumer_config.update(
                {
                    "sasl_mechanism": self.kafka_config.sasl_mechanism,
                    "sasl_plain_username": self.kafka_config.sasl_plain_username,
                    "sasl_plain_password": self.kafka_config.sasl_plain_password,
                }
            )

        consumer = AIOKafkaConsumer(topic, **consumer_config)
        await consumer.start()

        self._kafka_consumers[topic] = consumer
        self._consumer_tasks[topic] = asyncio.create_task(self._consume_messages(topic, consumer))

        logger.info(f"Started Kafka consumer for topic: {topic}")

    async def _stop_kafka_consumers(self) -> None:
        """Stop all Kafka consumers."""
        # Cancel consumer tasks
        for task in self._consumer_tasks.values():
            task.cancel()

        # Wait for tasks to complete
        if self._consumer_tasks:
            await asyncio.gather(*self._consumer_tasks.values(), return_exceptions=True)

        # Stop consumers
        for consumer in self._kafka_consumers.values():
            await consumer.stop()

        self._kafka_consumers.clear()
        self._consumer_tasks.clear()
        logger.info("All Kafka consumers stopped")

    async def _consume_messages(self, topic: str, consumer: AIOKafkaConsumer) -> None:
        """Consume messages from Kafka topic."""
        try:
            async for message in consumer:
                try:
                    # Deserialize event
                    event_data = json.loads(message.value.decode("utf-8"))
                    event = BaseEvent.from_dict(event_data)

                    # Process event with handlers
                    await self._dispatch_event(event)

                except Exception as e:
                    logger.error(f"Error processing message from topic {topic}: {e}")

        except asyncio.CancelledError:
            logger.info(f"Consumer task for topic {topic} was cancelled")
        except Exception as e:
            logger.error(f"Consumer task for topic {topic} failed: {e}")

    async def _dispatch_event(self, event: BaseEvent) -> None:
        """Dispatch event to appropriate handlers."""
        # Find handlers for this event type
        handlers = []

        # Add direct handlers
        for handler_id in self._subscriptions.get(event.event_type, []):
            if handler_id in self._handlers:
                handlers.append(self._handlers[handler_id])

        # Add wildcard handlers
        for handler_id in self._subscriptions.get("*", []):
            if handler_id in self._handlers:
                handlers.append(self._handlers[handler_id])

        # Add plugin handlers
        for plugin_handler in self._plugin_handlers.values():
            if plugin_handler.can_handle(event):
                handlers.append(plugin_handler)

        # Sort handlers by priority (highest first)
        handlers.sort(key=lambda h: h.priority, reverse=True)

        # Execute handlers concurrently
        tasks = []
        for handler in handlers:
            if handler.can_handle(event):
                tasks.append(handler.safe_handle(event))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log any failures
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    logger.error(f"Handler {handlers[i].handler_id} failed: {result}")

    async def _publish_to_kafka(self, event: BaseEvent) -> None:
        """Publish event to Kafka."""
        if not self._kafka_producer:
            raise RuntimeError("Kafka producer not started")

        topic = await self._get_topic_name(event.event_type)
        event_data = json.dumps(event.to_dict()).encode("utf-8")

        try:
            await self._kafka_producer.send_and_wait(
                topic, event_data, key=event.event_id.encode("utf-8")
            )
            logger.debug(f"Published event {event.event_id} to Kafka topic {topic}")
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id} to Kafka: {e}")
            raise

    async def publish(
        self,
        event: BaseEvent,
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
        delay: timedelta | None = None,
    ) -> None:
        """Publish an event to Kafka."""
        if not self._running:
            raise RuntimeError("Event bus is not running")

        if delay:
            # For delayed publishing, we could implement a scheduler
            # For now, just log a warning
            logger.warning(
                "Delayed publishing not yet implemented for Kafka backend, publishing immediately"
            )

        await self._publish_to_kafka(event)

    async def publish_batch(
        self,
        events: list[BaseEvent],
        delivery_guarantee: DeliveryGuarantee = DeliveryGuarantee.AT_LEAST_ONCE,
    ) -> None:
        """Publish multiple events as a batch to Kafka."""
        if not self._running:
            raise RuntimeError("Event bus is not running")

        # Publish events concurrently
        tasks = [self._publish_to_kafka(event) for event in events]
        await asyncio.gather(*tasks)

    async def subscribe(
        self, handler: EventHandler, event_filter: EventFilter | None = None
    ) -> str:
        """Subscribe an event handler."""
        async with self._lock:
            # Generate subscription ID
            subscription_id = str(uuid.uuid4())

            # Store handler
            self._handlers[handler.handler_id] = handler

            # Determine event types to subscribe to
            event_types = handler.event_types
            if event_filter and event_filter.event_types:
                event_types = [et for et in handler.event_types if et in event_filter.event_types]

            # Subscribe to event types
            for event_type in event_types:
                self._subscriptions[event_type].append(handler.handler_id)

                # Start Kafka consumer for this event type if running
                if self._running:
                    topic = await self._get_topic_name(event_type)
                    await self._start_kafka_consumer(topic)

            logger.info(f"Subscribed handler {handler.handler_id} to event types: {event_types}")
            return subscription_id

    async def unsubscribe(self, subscription_id: str) -> bool:
        """Unsubscribe a handler by subscription ID."""
        async with self._lock:
            # Find handler by subscription ID (for now, use handler_id as subscription_id)
            handler_to_remove = None
            for handler in self._handlers.values():
                if handler.handler_id == subscription_id:
                    handler_to_remove = handler
                    break

            if not handler_to_remove:
                return False

            # Remove from subscriptions
            for _event_type, handler_ids in self._subscriptions.items():
                if handler_to_remove.handler_id in handler_ids:
                    handler_ids.remove(handler_to_remove.handler_id)

            # Remove handler
            del self._handlers[handler_to_remove.handler_id]

            logger.info(f"Unsubscribed handler {handler_to_remove.handler_id}")
            return True

    async def subscribe_plugin(
        self,
        plugin_id: str,
        plugin_name: str,
        event_filter: EventFilter,
        handler_func: Callable[[BaseEvent], Any],
    ) -> str:
        """Subscribe a plugin to events."""
        plugin_handler = PluginEventHandler(
            plugin_id=plugin_id,
            plugin_name=plugin_name,
            event_filter=event_filter,
            handler_func=handler_func,
        )

        self._plugin_handlers[plugin_id] = plugin_handler

        # Start consumers for event types if running
        if self._running and event_filter.event_types:
            for event_type in event_filter.event_types:
                topic = await self._get_topic_name(event_type)
                await self._start_kafka_consumer(topic)

        logger.info(f"Subscribed plugin {plugin_name} ({plugin_id}) to events")
        return plugin_handler.handler_id

    async def unsubscribe_plugin(self, plugin_id: str) -> bool:
        """Unsubscribe a plugin from events."""
        if plugin_id not in self._plugin_handlers:
            return False

        del self._plugin_handlers[plugin_id]
        logger.info(f"Unsubscribed plugin {plugin_id}")
        return True

    async def start(self) -> None:
        """Start the Kafka event bus."""
        if self._running:
            return

        self._running = True

        # Start Kafka producer
        await self._start_kafka_producer()

        # Start outbox processor if configured
        if self.outbox_config and self._session_factory:
            self._outbox_processor_task = asyncio.create_task(self._process_outbox_events())
            logger.info("Started outbox processor")

        # Start consumers for already subscribed event types
        topics_to_consume = set()
        for event_types in self._subscriptions.keys():
            if event_types != "*":
                topics_to_consume.add(await self._get_topic_name(event_types))

        # Add topics for plugin subscriptions
        for plugin_handler in self._plugin_handlers.values():
            if plugin_handler.event_filter.event_types:
                for event_type in plugin_handler.event_filter.event_types:
                    topics_to_consume.add(await self._get_topic_name(event_type))

        # Start consumers
        for topic in topics_to_consume:
            await self._start_kafka_consumer(topic)

        logger.info("Enhanced event bus with transactional outbox started")

    async def stop(self) -> None:
        """Stop the event bus."""
        if not self._running:
            return

        self._running = False

        # Stop outbox processor
        if self._outbox_processor_task:
            self._outbox_processor_task.cancel()
            try:
                await self._outbox_processor_task
            except asyncio.CancelledError:
                pass
            self._outbox_processor_task = None
            logger.info("Stopped outbox processor")

        # Stop Kafka components
        await self._stop_kafka_producer()
        await self._stop_kafka_consumers()

        logger.info("Enhanced event bus stopped")

    async def health_check(self) -> dict[str, Any]:
        """Perform health check on the event bus."""
        health = {
            "status": "healthy" if self._running else "stopped",
            "backend": "kafka",
            "handlers_count": len(self._handlers),
            "plugin_handlers_count": len(self._plugin_handlers),
            "kafka_producer_running": self._kafka_producer is not None,
            "kafka_consumers_count": len(self._kafka_consumers),
            "active_topics": list(self._kafka_consumers.keys()),
            "outbox_enabled": self.outbox_config is not None,
            "outbox_processor_running": self._outbox_processor_task is not None
            and not self._outbox_processor_task.done()
            if self._outbox_processor_task
            else False,
        }

        return health


# Backwards compatibility aliases
EventBusInterface = EventBus
