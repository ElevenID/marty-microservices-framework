"""
Enhanced Transactional Outbox Pattern for Marty Microservices Framework

This module extends the existing outbox pattern with advanced features:
- Batch processing for improved performance
- Dead letter queue support for failed events
- Enhanced retry mechanisms wit    async def get_pending_events(
        self,
        limit: int = None,
        partition: int | None = None,
        priority_order: bool = True
    ) -> list[EnhancedOutboxEvent]:nential backoff
- Multi-broker support (Kafka + RabbitMQ)
- Event partitioning and ordering guarantees
- Monitoring and health checks
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Protocol, Union

from sqlalchemy import BigInteger, Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)


class OutboxEventStatus(Enum):
    """Enhanced outbox event status."""

    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    SKIPPED = "skipped"


class EventPartitionStrategy(Enum):
    """Event partitioning strategies."""

    ROUND_ROBIN = "round_robin"
    KEY_HASH = "key_hash"
    AGGREGATE_ID = "aggregate_id"
    CUSTOM = "custom"


@dataclass
class RetryConfig:
    """Configuration for retry behavior."""

    max_attempts: int = 3
    initial_delay_ms: int = 1000
    max_delay_ms: int = 30000
    exponential_base: float = 2.0
    jitter_factor: float = 0.1


@dataclass
class PartitionConfig:
    """Configuration for event partitioning."""

    strategy: EventPartitionStrategy = EventPartitionStrategy.KEY_HASH
    partition_count: int = 3
    custom_partitioner: Callable[[dict], int] | None = None


@dataclass
class BatchConfig:
    """Configuration for batch processing."""

    batch_size: int = 100
    batch_timeout_ms: int = 5000
    max_batch_bytes: int = 1024 * 1024  # 1MB
    enable_compression: bool = True


@dataclass
class OutboxConfig:
    """Enhanced outbox configuration."""

    # Processing configuration
    poll_interval_ms: int = 1000
    worker_count: int = 3
    enable_parallel_processing: bool = True

    # Retry configuration
    retry_config: RetryConfig = field(default_factory=RetryConfig)

    # Partition configuration
    partition_config: PartitionConfig = field(default_factory=PartitionConfig)

    # Batch configuration
    batch_config: BatchConfig = field(default_factory=BatchConfig)

    # Dead letter queue
    enable_dead_letter_queue: bool = True
    dead_letter_topic: str = "mmf.dead-letter-queue"

    # Monitoring
    enable_metrics: bool = True
    metrics_interval_ms: int = 30000

    # Cleanup
    auto_cleanup_enabled: bool = True
    cleanup_after_days: int = 7


class MessageBroker(Protocol):
    """Protocol for message broker implementations."""

    async def publish(
        self,
        topic: str,
        message: bytes,
        key: bytes | None = None,
        partition: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Publish message to broker."""
        ...

    async def publish_batch(self, messages: list[dict[str, Any]]) -> list[bool]:
        """Publish batch of messages."""
        ...


Base = declarative_base()


class EnhancedOutboxEvent(Base):
    """Enhanced outbox event model with additional features."""

    __tablename__ = "enhanced_outbox_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    event_id = Column(String(255), nullable=False, unique=True, index=True)
    aggregate_id = Column(String(255), nullable=True, index=True)
    aggregate_type = Column(String(100), nullable=True, index=True)
    event_type = Column(String(100), nullable=False, index=True)

    # Message details
    topic = Column(String(255), nullable=False)
    payload = Column(Text, nullable=False)
    message_key = Column(String(255), nullable=True)
    headers = Column(Text, nullable=True)  # JSON string

    # Partitioning
    partition = Column(Integer, nullable=True)
    partition_key = Column(String(255), nullable=True)

    # Status and processing
    status = Column(String(50), nullable=False, default=OutboxEventStatus.PENDING.value, index=True)
    created_at = Column(
        DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )
    scheduled_at = Column(DateTime, nullable=True, index=True)
    processed_at = Column(DateTime, nullable=True)

    # Retry mechanism
    attempt_count = Column(Integer, nullable=False, default=0)
    max_attempts = Column(Integer, nullable=False, default=3)
    next_retry_at = Column(DateTime, nullable=True, index=True)
    last_error = Column(Text, nullable=True)

    # Metadata
    priority = Column(Integer, nullable=False, default=5)  # 1-10 scale
    expires_at = Column(DateTime, nullable=True, index=True)
    correlation_id = Column(String(255), nullable=True, index=True)
    causation_id = Column(String(255), nullable=True)

    # Performance tracking
    processing_duration_ms = Column(Integer, nullable=True)
    payload_size_bytes = Column(Integer, nullable=True)


class EnhancedOutboxRepository:
    """Enhanced repository for managing outbox events with advanced features."""

    def __init__(self, session: Session, config: OutboxConfig = None):
        """Initialize enhanced outbox repository."""
        self.session = session
        self.config = config or OutboxConfig()
        self._partitioner = self._create_partitioner()

    def _create_partitioner(self) -> Callable[[dict], int]:
        """Create partitioner function based on configuration."""
        strategy = self.config.partition_config.strategy
        partition_count = self.config.partition_config.partition_count

        if strategy == EventPartitionStrategy.CUSTOM:
            return self.config.partition_config.custom_partitioner
        elif strategy == EventPartitionStrategy.ROUND_ROBIN:
            counter = 0

            def round_robin_partitioner(event_data: dict) -> int:
                nonlocal counter
                counter = (counter + 1) % partition_count
                return counter

            return round_robin_partitioner
        elif strategy == EventPartitionStrategy.AGGREGATE_ID:

            def aggregate_partitioner(event_data: dict) -> int:
                aggregate_id = event_data.get("aggregate_id", "")
                return hash(aggregate_id) % partition_count

            return aggregate_partitioner
        else:  # KEY_HASH

            def key_hash_partitioner(event_data: dict) -> int:
                key = event_data.get("message_key", event_data.get("event_id", ""))
                return hash(key) % partition_count

            return key_hash_partitioner

    async def enqueue_event(
        self,
        topic: str,
        event_type: str,
        payload: dict,
        *,
        event_id: str | None = None,
        aggregate_id: str | None = None,
        aggregate_type: str | None = None,
        message_key: str | None = None,
        headers: dict[str, str] | None = None,
        priority: int = 5,
        expires_at: datetime | None = None,
        correlation_id: str | None = None,
        causation_id: str | None = None,
        scheduled_at: datetime | None = None,
        max_attempts: int | None = None,
    ) -> str:
        """Enqueue an event with enhanced features."""
        if event_id is None:
            event_id = str(uuid.uuid4())

        # Calculate partition
        event_data = {
            "event_id": event_id,
            "aggregate_id": aggregate_id,
            "message_key": message_key or aggregate_id or event_id,
        }
        partition = self._partitioner(event_data)

        # Serialize payload and headers
        payload_json = json.dumps(payload, default=str)
        headers_json = json.dumps(headers) if headers else None

        # Create outbox event
        outbox_event = EnhancedOutboxEvent(
            event_id=event_id,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            event_type=event_type,
            topic=topic,
            payload=payload_json,
            message_key=message_key,
            headers=headers_json,
            partition=partition,
            partition_key=message_key or aggregate_id,
            priority=priority,
            expires_at=expires_at,
            correlation_id=correlation_id,
            causation_id=causation_id,
            scheduled_at=scheduled_at,
            max_attempts=max_attempts or self.config.retry_config.max_attempts,
            payload_size_bytes=len(payload_json.encode("utf-8")),
        )

        self.session.add(outbox_event)
        logger.debug(f"Enqueued event {event_id} for topic {topic} (partition: {partition})")

        return event_id

    def get_pending_events(
        self, limit: int = None, partition: int | None = None, priority_order: bool = True
    ) -> list[EnhancedOutboxEvent]:
        """Get pending events for processing."""
        limit = limit or self.config.batch_config.batch_size
        now = datetime.now(timezone.utc)

        query = self.session.query(EnhancedOutboxEvent).filter(
            EnhancedOutboxEvent.status == OutboxEventStatus.PENDING.value,
            (EnhancedOutboxEvent.scheduled_at.is_(None))
            | (EnhancedOutboxEvent.scheduled_at <= now),
            (EnhancedOutboxEvent.expires_at.is_(None)) | (EnhancedOutboxEvent.expires_at > now),
            (EnhancedOutboxEvent.next_retry_at.is_(None))
            | (EnhancedOutboxEvent.next_retry_at <= now),
        )

        if partition is not None:
            query = query.filter(EnhancedOutboxEvent.partition == partition)

        if priority_order:
            query = query.order_by(
                EnhancedOutboxEvent.priority.asc(), EnhancedOutboxEvent.created_at.asc()
            )
        else:
            query = query.order_by(EnhancedOutboxEvent.created_at.asc())

        return query.limit(limit).all()

    def get_events_by_status(
        self, status: OutboxEventStatus, limit: int = 100
    ) -> list[EnhancedOutboxEvent]:
        """Get events by status."""
        return (
            self.session.query(EnhancedOutboxEvent)
            .filter(EnhancedOutboxEvent.status == status.value)
            .order_by(EnhancedOutboxEvent.created_at.desc())
            .limit(limit)
            .all()
        )

    def mark_processing(self, event_id: str) -> bool:
        """Mark event as processing."""
        event = self.session.query(EnhancedOutboxEvent).filter_by(event_id=event_id).first()
        if event:
            event.status = OutboxEventStatus.PROCESSING.value
            event.attempt_count += 1
            self.session.commit()
            return True
        return False

    def mark_completed(self, event_id: str, processing_duration_ms: int | None = None) -> bool:
        """Mark event as completed."""
        event = self.session.query(EnhancedOutboxEvent).filter_by(event_id=event_id).first()
        if event:
            event.status = OutboxEventStatus.COMPLETED.value
            event.processed_at = datetime.now(timezone.utc)
            event.processing_duration_ms = processing_duration_ms
            event.last_error = None
            self.session.commit()
            return True
        return False

    def mark_failed(self, event_id: str, error_message: str, send_to_dlq: bool = None) -> bool:
        """Mark event as failed with retry logic."""
        event = self.session.query(EnhancedOutboxEvent).filter_by(event_id=event_id).first()
        if not event:
            return False

        event.last_error = error_message

        # Check if we should retry or send to dead letter queue
        if event.attempt_count >= event.max_attempts:
            if send_to_dlq is None:
                send_to_dlq = self.config.enable_dead_letter_queue

            if send_to_dlq:
                event.status = OutboxEventStatus.DEAD_LETTER.value
            else:
                event.status = OutboxEventStatus.FAILED.value
        else:
            # Schedule retry with exponential backoff
            retry_config = self.config.retry_config
            delay_ms = min(
                retry_config.initial_delay_ms
                * (retry_config.exponential_base ** (event.attempt_count - 1)),
                retry_config.max_delay_ms,
            )

            # Add jitter
            jitter = (
                delay_ms * retry_config.jitter_factor * (0.5 - asyncio.get_event_loop().time() % 1)
            )
            delay_ms += jitter

            event.next_retry_at = datetime.now(timezone.utc) + timedelta(milliseconds=delay_ms)
            event.status = OutboxEventStatus.PENDING.value

        self.session.commit()
        return True

    def get_statistics(self) -> dict[str, Any]:
        """Get outbox statistics."""
        stats = {}

        # Count by status
        for status in OutboxEventStatus:
            count = (
                self.session.query(EnhancedOutboxEvent)
                .filter(EnhancedOutboxEvent.status == status.value)
                .count()
            )
            stats[f"{status.value}_count"] = count

        # Processing metrics
        processing_times = (
            self.session.query(
                func.avg(EnhancedOutboxEvent.processing_duration_ms),
                func.max(EnhancedOutboxEvent.processing_duration_ms),
                func.min(EnhancedOutboxEvent.processing_duration_ms),
            )
            .filter(EnhancedOutboxEvent.processing_duration_ms.isnot(None))
            .first()
        )

        if processing_times[0]:
            stats.update(
                {
                    "avg_processing_time_ms": float(processing_times[0]),
                    "max_processing_time_ms": processing_times[1],
                    "min_processing_time_ms": processing_times[2],
                }
            )

        # Payload size metrics
        payload_sizes = self.session.query(
            func.avg(EnhancedOutboxEvent.payload_size_bytes),
            func.max(EnhancedOutboxEvent.payload_size_bytes),
            func.sum(EnhancedOutboxEvent.payload_size_bytes),
        ).first()

        if payload_sizes[0]:
            stats.update(
                {
                    "avg_payload_size_bytes": float(payload_sizes[0]),
                    "max_payload_size_bytes": payload_sizes[1],
                    "total_payload_bytes": payload_sizes[2],
                }
            )

        return stats

    def cleanup_old_events(self, older_than_days: int = None) -> int:
        """Clean up old processed events."""
        older_than_days = older_than_days or self.config.cleanup_after_days
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=older_than_days)

        deleted_count = (
            self.session.query(EnhancedOutboxEvent)
            .filter(
                EnhancedOutboxEvent.status == OutboxEventStatus.COMPLETED.value,
                EnhancedOutboxEvent.processed_at < cutoff_date,
            )
            .delete()
        )

        self.session.commit()
        logger.info(f"Cleaned up {deleted_count} old outbox events")
        return deleted_count


class EnhancedOutboxProcessor:
    """Enhanced outbox processor with advanced features."""

    def __init__(
        self,
        repository: EnhancedOutboxRepository,
        message_broker: MessageBroker,
        config: OutboxConfig = None,
    ):
        """Initialize enhanced outbox processor."""
        self.repository = repository
        self.message_broker = message_broker
        self.config = config or OutboxConfig()
        self._running = False
        self._workers: list[asyncio.Task] = []
        self._metrics = {
            "processed_count": 0,
            "failed_count": 0,
            "dlq_count": 0,
            "batch_count": 0,
            "last_batch_size": 0,
            "last_processing_time_ms": 0,
        }

    async def start(self) -> None:
        """Start the outbox processor."""
        if self._running:
            return

        self._running = True
        logger.info(f"Starting outbox processor with {self.config.worker_count} workers")

        # Start worker tasks
        for i in range(self.config.worker_count):
            if self.config.enable_parallel_processing:
                # Each worker processes a specific partition
                partition = i % self.config.partition_config.partition_count
                worker = asyncio.create_task(self._worker_loop(f"worker-{i}", partition))
            else:
                # All workers process all partitions
                worker = asyncio.create_task(self._worker_loop(f"worker-{i}", None))
            self._workers.append(worker)

        # Start metrics collection if enabled
        if self.config.enable_metrics:
            metrics_task = asyncio.create_task(self._metrics_loop())
            self._workers.append(metrics_task)

        # Start cleanup task if enabled
        if self.config.auto_cleanup_enabled:
            cleanup_task = asyncio.create_task(self._cleanup_loop())
            self._workers.append(cleanup_task)

    async def stop(self) -> None:
        """Stop the outbox processor."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping outbox processor...")

        # Cancel all worker tasks
        for worker in self._workers:
            worker.cancel()

        # Wait for tasks to complete
        await asyncio.gather(*self._workers, return_exceptions=True)
        self._workers.clear()

        logger.info("Outbox processor stopped")

    async def _worker_loop(self, worker_id: str, partition: int | None) -> None:
        """Worker loop for processing events."""
        logger.info(f"Starting worker {worker_id} (partition: {partition})")

        while self._running:
            try:
                # Get batch of events to process
                events = self.repository.get_pending_events(
                    limit=self.config.batch_config.batch_size, partition=partition
                )

                if not events:
                    await asyncio.sleep(self.config.poll_interval_ms / 1000)
                    continue

                # Process batch
                await self._process_batch(worker_id, events)

            except Exception as e:
                logger.error(f"Worker {worker_id} error: {e}")
                await asyncio.sleep(1)  # Brief pause on error

    async def _process_batch(self, worker_id: str, events: list[EnhancedOutboxEvent]) -> None:
        """Process a batch of events."""
        start_time = time.time()

        # Prepare batch messages
        batch_messages = []
        event_map = {}

        for event in events:
            # Mark as processing
            self.repository.mark_processing(event.event_id)

            # Prepare message
            headers = json.loads(event.headers) if event.headers else {}
            headers.update(
                {
                    "event-id": event.event_id,
                    "event-type": event.event_type,
                    "correlation-id": event.correlation_id or "",
                    "causation-id": event.causation_id or "",
                    "created-at": event.created_at.isoformat(),
                }
            )

            message = {
                "topic": event.topic,
                "message": event.payload.encode("utf-8"),
                "key": event.message_key.encode("utf-8") if event.message_key else None,
                "partition": event.partition,
                "headers": headers,
            }

            batch_messages.append(message)
            event_map[len(batch_messages) - 1] = event

        try:
            # Publish batch
            results = await self.message_broker.publish_batch(batch_messages)

            # Process results
            for i, success in enumerate(results):
                event = event_map[i]
                processing_time_ms = int((time.time() - start_time) * 1000)

                if success:
                    self.repository.mark_completed(event.event_id, processing_time_ms)
                    self._metrics["processed_count"] += 1
                else:
                    self.repository.mark_failed(
                        event.event_id, f"Failed to publish to {event.topic}"
                    )
                    self._metrics["failed_count"] += 1

            # Update batch metrics
            self._metrics["batch_count"] += 1
            self._metrics["last_batch_size"] = len(events)
            self._metrics["last_processing_time_ms"] = int((time.time() - start_time) * 1000)

            logger.debug(f"Worker {worker_id} processed batch of {len(events)} events")

        except Exception as e:
            # Mark all events as failed
            for event in events:
                self.repository.mark_failed(event.event_id, str(e))
                self._metrics["failed_count"] += 1

            logger.error(f"Batch processing failed for worker {worker_id}: {e}")

    async def _metrics_loop(self) -> None:
        """Metrics collection loop."""
        while self._running:
            try:
                # Log current metrics
                stats = self.repository.get_statistics()
                stats.update(self._metrics)

                logger.info(f"Outbox metrics: {stats}")

                await asyncio.sleep(self.config.metrics_interval_ms / 1000)

            except Exception as e:
                logger.error(f"Metrics collection error: {e}")
                await asyncio.sleep(10)

    async def _cleanup_loop(self) -> None:
        """Cleanup loop for old events."""
        while self._running:
            try:
                # Cleanup old events daily
                self.repository.cleanup_old_events()

                # Sleep for 24 hours
                await asyncio.sleep(24 * 60 * 60)

            except Exception as e:
                logger.error(f"Cleanup error: {e}")
                await asyncio.sleep(60 * 60)  # Retry in 1 hour

    def get_metrics(self) -> dict[str, Any]:
        """Get current processing metrics."""
        stats = self.repository.get_statistics()
        stats.update(self._metrics)
        stats["is_running"] = self._running
        stats["worker_count"] = len(self._workers)
        return stats


# Integration with existing framework
class KafkaMessageBroker:
    """Kafka implementation of message broker."""

    def __init__(self, producer):
        """Initialize with Kafka producer."""
        self.producer = producer

    async def publish(
        self,
        topic: str,
        message: bytes,
        key: bytes | None = None,
        partition: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Publish single message to Kafka."""
        try:
            await self.producer.send_and_wait(
                topic=topic, value=message, key=key, partition=partition, headers=headers
            )
            return True
        except Exception as e:
            logger.error(f"Failed to publish to Kafka topic {topic}: {e}")
            return False

    async def publish_batch(self, messages: list[dict[str, Any]]) -> list[bool]:
        """Publish batch of messages to Kafka."""
        results = []

        # Create batch of futures
        futures = []
        for msg in messages:
            future = self.producer.send(
                topic=msg["topic"],
                value=msg["message"],
                key=msg.get("key"),
                partition=msg.get("partition"),
                headers=msg.get("headers"),
            )
            futures.append(future)

        # Wait for all futures
        for future in futures:
            try:
                await future
                results.append(True)
            except Exception as e:
                logger.error(f"Batch publish failed: {e}")
                results.append(False)

        return results


class RabbitMQMessageBroker:
    """RabbitMQ implementation of message broker."""

    def __init__(self, connection):
        """Initialize with RabbitMQ connection."""
        self.connection = connection

    async def publish(
        self,
        topic: str,
        message: bytes,
        key: bytes | None = None,
        partition: int | None = None,
        headers: dict[str, str] | None = None,
    ) -> bool:
        """Publish single message to RabbitMQ."""
        try:
            # RabbitMQ implementation would go here
            # This is a placeholder for the actual implementation
            logger.debug(f"Publishing to RabbitMQ topic {topic}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to RabbitMQ topic {topic}: {e}")
            return False

    async def publish_batch(self, messages: list[dict[str, Any]]) -> list[bool]:
        """Publish batch of messages to RabbitMQ."""
        results = []
        for msg in messages:
            success = await self.publish(
                topic=msg["topic"],
                message=msg["message"],
                key=msg.get("key"),
                headers=msg.get("headers"),
            )
            results.append(success)
        return results


# Factory functions
def create_enhanced_outbox_processor(
    session: Session, message_broker: MessageBroker, config: OutboxConfig = None
) -> EnhancedOutboxProcessor:
    """Create enhanced outbox processor with default configuration."""
    repository = EnhancedOutboxRepository(session, config)
    return EnhancedOutboxProcessor(repository, message_broker, config)


def create_kafka_message_broker(kafka_producer) -> KafkaMessageBroker:
    """Create Kafka message broker."""
    return KafkaMessageBroker(kafka_producer)


def create_rabbitmq_message_broker(rabbitmq_connection) -> RabbitMQMessageBroker:
    """Create RabbitMQ message broker."""
    return RabbitMQMessageBroker(rabbitmq_connection)
