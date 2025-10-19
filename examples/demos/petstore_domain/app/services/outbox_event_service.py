"""
Enhanced Event Service with Transactional Outbox Pattern for Petstore Domain

This service implements the transactional outbox pattern to ensure reliable event publishing
while maintaining ACID guarantees for business data updates.
"""
import asyncio
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Integer,
    MetaData,
    String,
    Text,
    and_,
    create_engine,
    select,
    update,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

logger = logging.getLogger(__name__)

Base = declarative_base()


class OutboxEvent(Base):
    """Outbox event table for reliable event publishing"""
    __tablename__ = "outbox_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    aggregate_id = Column(String(255), nullable=False, index=True)
    aggregate_type = Column(String(100), nullable=False)
    event_type = Column(String(100), nullable=False)
    event_data = Column(Text, nullable=False)
    correlation_id = Column(String(255), nullable=True)
    topic = Column(String(255), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    processed_at = Column(DateTime(timezone=True), nullable=True)
    retry_count = Column(Integer, default=0, nullable=False)
    is_processed = Column(Boolean, default=False, nullable=False)
    error_message = Column(Text, nullable=True)


class PetstoreOutboxEventService:
    """Enhanced Event Service with Transactional Outbox Pattern"""

    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            "DATABASE_URL",
            "postgresql+asyncpg://postgres:postgres@localhost:5432/petstore"
        )
        self.kafka_brokers = os.getenv("KAFKA_BROKERS", "localhost:9092")
        self.topic_prefix = os.getenv("KAFKA_TOPIC_PREFIX", "petstore")

        # Database setup
        self.engine = create_async_engine(
            self.database_url,
            pool_size=20,
            max_overflow=50,
            pool_pre_ping=True,
            pool_recycle=3600
        )
        self.async_session = async_sessionmaker(
            self.engine,
            class_=AsyncSession,
            expire_on_commit=False
        )

        # Kafka setup
        self.producer: AIOKafkaProducer | None = None
        self._processing_task: asyncio.Task | None = None
        self._running = False

        # Configuration
        self.batch_size = int(os.getenv("OUTBOX_BATCH_SIZE", "100"))
        self.polling_interval = float(os.getenv("OUTBOX_POLLING_INTERVAL", "1.0"))
        self.max_retry_attempts = int(os.getenv("OUTBOX_MAX_RETRIES", "5"))

    async def start(self) -> None:
        """Initialize the outbox event service"""
        try:
            # Initialize Kafka producer
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.kafka_brokers,
                value_serializer=lambda v: json.dumps(v).encode('utf-8'),
                key_serializer=lambda k: k.encode('utf-8') if k else None,
                retry_backoff_ms=100,
                request_timeout_ms=30000,
                connections_max_idle_ms=540000,
                enable_idempotence=True,
                acks='all'
            )
            await self.producer.start()

            # Create tables if they don't exist
            await self._create_tables()

            # Start outbox processing
            self._running = True
            self._processing_task = asyncio.create_task(self._process_outbox_events())

            logger.info(f"Outbox Event Service started - Kafka: {self.kafka_brokers}")

        except Exception as e:
            logger.error(f"Failed to start Outbox Event Service: {e}")
            raise

    async def stop(self) -> None:
        """Stop the outbox event service"""
        self._running = False

        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass

        if self.producer:
            await self.producer.stop()

        await self.engine.dispose()
        logger.info("Outbox Event Service stopped")

    async def _create_tables(self) -> None:
        """Create outbox tables if they don't exist"""

        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Outbox tables created/verified")

    @asynccontextmanager
    async def get_session(self):
        """Get database session context manager"""
        async with self.async_session() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()

    async def enqueue_event_in_transaction(
        self,
        session: AsyncSession,
        aggregate_id: str,
        aggregate_type: str,
        event_type: str,
        event_data: dict[str, Any],
        correlation_id: str | None = None,
        topic: str | None = None
    ) -> str:
        """
        Enqueue an event within an existing transaction.
        This ensures ACID guarantees - the event is only saved if the business transaction succeeds.
        """
        event_id = str(uuid.uuid4())
        topic = topic or f"{self.topic_prefix}.{event_type}"

        # Create outbox event
        outbox_event = OutboxEvent(
            id=event_id,
            aggregate_id=aggregate_id,
            aggregate_type=aggregate_type,
            event_type=event_type,
            event_data=json.dumps(event_data),
            correlation_id=correlation_id,
            topic=topic,
            created_at=datetime.now(timezone.utc)
        )

        session.add(outbox_event)

        logger.info(
            f"Enqueued event {event_type} for {aggregate_type}:{aggregate_id} "
            f"in transaction (event_id: {event_id})"
        )

        return event_id

    async def publish_pet_event(
        self,
        session: AsyncSession,
        pet_id: str,
        event_type: str,
        pet_data: dict[str, Any],
        correlation_id: str | None = None
    ) -> str:
        """Publish pet-related events using outbox pattern"""
        return await self.enqueue_event_in_transaction(
            session=session,
            aggregate_id=pet_id,
            aggregate_type="pet",
            event_type=f"pet.{event_type}",
            event_data={
                "pet_id": pet_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **pet_data
            },
            correlation_id=correlation_id
        )

    async def publish_order_event(
        self,
        session: AsyncSession,
        order_id: str,
        event_type: str,
        order_data: dict[str, Any],
        correlation_id: str | None = None
    ) -> str:
        """Publish order-related events using outbox pattern"""
        return await self.enqueue_event_in_transaction(
            session=session,
            aggregate_id=order_id,
            aggregate_type="order",
            event_type=f"order.{event_type}",
            event_data={
                "order_id": order_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **order_data
            },
            correlation_id=correlation_id
        )

    async def publish_user_event(
        self,
        session: AsyncSession,
        user_id: str,
        event_type: str,
        user_data: dict[str, Any],
        correlation_id: str | None = None
    ) -> str:
        """Publish user-related events using outbox pattern"""
        return await self.enqueue_event_in_transaction(
            session=session,
            aggregate_id=user_id,
            aggregate_type="user",
            event_type=f"user.{event_type}",
            event_data={
                "user_id": user_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **user_data
            },
            correlation_id=correlation_id
        )

    async def _process_outbox_events(self) -> None:
        """Background task to process outbox events"""
        logger.info("Started outbox event processing")

        while self._running:
            try:
                await self._process_batch()
                await asyncio.sleep(self.polling_interval)
            except Exception as e:
                logger.error(f"Error in outbox processing: {e}")
                await asyncio.sleep(self.polling_interval * 2)  # Back off on error

    async def _process_batch(self) -> None:
        """Process a batch of unprocessed events"""
        async with self.get_session() as session:
            # Get unprocessed events
            stmt = select(OutboxEvent).where(
                and_(
                    ~OutboxEvent.is_processed,
                    OutboxEvent.retry_count < self.max_retry_attempts
                )
            ).order_by(OutboxEvent.created_at).limit(self.batch_size)

            result = await session.execute(stmt)
            events = result.scalars().all()

            if not events:
                return

            logger.info(f"Processing {len(events)} outbox events")

            # Process events
            for event in events:
                success = await self._publish_single_event(event)

                if success:
                    # Mark as processed
                    await session.execute(
                        update(OutboxEvent)
                        .where(OutboxEvent.id == event.id)
                        .values(
                            is_processed=True,
                            processed_at=datetime.now(timezone.utc),
                            error_message=None
                        )
                    )
                else:
                    # Increment retry count
                    await session.execute(
                        update(OutboxEvent)
                        .where(OutboxEvent.id == event.id)
                        .values(retry_count=event.retry_count + 1)
                    )

            await session.commit()

    async def _publish_single_event(self, event: OutboxEvent) -> bool:
        """Publish a single event to Kafka"""
        try:
            if not self.producer:
                logger.warning("Kafka producer not available")
                return False

            # Parse event data
            event_data = json.loads(event.event_data)

            # Prepare message with metadata
            message = {
                "event_id": str(event.id),
                "event_type": event.event_type,
                "aggregate_id": event.aggregate_id,
                "aggregate_type": event.aggregate_type,
                "correlation_id": event.correlation_id,
                "created_at": event.created_at.isoformat(),
                "data": event_data,
                "service": "petstore-domain"
            }

            # Send to Kafka
            await self.producer.send(
                topic=event.topic,
                value=message,
                key=event.aggregate_id
            )

            logger.info(
                f"Published event {event.event_type} for {event.aggregate_type}:"
                f"{event.aggregate_id} to topic {event.topic}"
            )
            return True

        except Exception as e:
            logger.error(
                f"Failed to publish event {event.id} ({event.event_type}): {e}"
            )
            # Update error message
            try:
                async with self.get_session() as session:
                    await session.execute(
                        update(OutboxEvent)
                        .where(OutboxEvent.id == event.id)
                        .values(error_message=str(e))
                    )
                    await session.commit()
            except Exception as update_error:
                logger.error(f"Failed to update error message: {update_error}")

            return False

    async def get_outbox_metrics(self) -> dict[str, Any]:
        """Get outbox processing metrics"""
        async with self.get_session() as session:
            # Count pending events
            pending_stmt = select(func.count(OutboxEvent.id)).where(
                ~OutboxEvent.is_processed
            )
            pending_result = await session.execute(pending_stmt)
            pending_count = pending_result.scalar()

            # Count failed events (max retries exceeded)
            failed_stmt = select(func.count(OutboxEvent.id)).where(
                and_(
                    ~OutboxEvent.is_processed,
                    OutboxEvent.retry_count >= self.max_retry_attempts
                )
            )
            failed_result = await session.execute(failed_stmt)
            failed_count = failed_result.scalar()

            # Count processed events (today)
            today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
            processed_stmt = select(func.count(OutboxEvent.id)).where(
                and_(
                    OutboxEvent.is_processed,
                    OutboxEvent.processed_at >= today
                )
            )
            processed_result = await session.execute(processed_stmt)
            processed_today = processed_result.scalar()

            return {
                "pending_events": pending_count,
                "failed_events": failed_count,
                "processed_today": processed_today,
                "running": self._running,
                "kafka_connected": self.producer is not None
            }


# Global instance
outbox_event_service = PetstoreOutboxEventService()
