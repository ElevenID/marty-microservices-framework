"""
Event and notification adapters for the Morty service.

These adapters implement the output ports for event publishing and notifications,
providing concrete implementations using Kafka and email services.
"""

import builtins
import json
import logging
from uuid import UUID

from ...application.ports.output_ports import EventPublisherPort, NotificationPort
from ...domain.events import DomainEvent

logger = logging.getLogger(__name__)


class KafkaEventPublisher(EventPublisherPort):
    """Kafka implementation of the event publisher port."""

    def __init__(self, kafka_producer=None, topic_prefix: str = "morty"):
        self._producer = kafka_producer
        self._topic_prefix = topic_prefix

    async def publish(self, event: DomainEvent) -> None:
        """Publish a single domain event."""
        if not self._producer:
            # Log event if no producer configured (for testing/development)
            logger.info(f"Would publish event: {event.event_type} - {event.event_id}")
            return

        topic = f"{self._topic_prefix}.{event.event_type.lower()}"

        event_data = {
            "event_id": event.event_id,
            "event_type": event.event_type,
            "occurred_at": event.occurred_at.isoformat(),
            "data": self._serialize_event(event),
        }

        try:
            await self._producer.send(topic, value=json.dumps(event_data))
            logger.info(f"Published event {event.event_id} to topic {topic}")
        except Exception as e:
            logger.error(f"Failed to publish event {event.event_id}: {e}")
            raise

    async def publish_batch(self, events: builtins.list[DomainEvent]) -> None:
        """Publish multiple domain events as a batch."""
        for event in events:
            await self.publish(event)

    def _serialize_event(self, event: DomainEvent) -> dict:
        """Serialize event-specific data."""
        data = {}

        # Extract event-specific properties
        for attr_name in dir(event):
            if not attr_name.startswith("_") and attr_name not in [
                "event_id",
                "event_type",
                "occurred_at",
            ]:
                attr_value = getattr(event, attr_name)
                if not callable(attr_value):
                    # Convert UUID to string for JSON serialization
                    if isinstance(attr_value, UUID):
                        data[attr_name] = str(attr_value)
                    else:
                        data[attr_name] = attr_value

        return data


class EmailNotificationService(NotificationPort):
    """Email implementation of the notification port."""

    def __init__(self, email_client=None, from_email: str = "noreply@morty.dev"):
        self._email_client = email_client
        self._from_email = from_email

    async def send_task_assigned_notification(
        self, user_email: str, task_title: str, task_id: UUID
    ) -> None:
        """Send notification when a task is assigned."""
        subject = f"New Task Assigned: {task_title}"
        body = f"""
        Hello,

        You have been assigned a new task:

        Task: {task_title}
        Task ID: {task_id}

        Please log in to the system to view the details.

        Best regards,
        Morty Task Management System
        """

        await self._send_email(user_email, subject, body)

    async def send_task_completed_notification(
        self, user_email: str, task_title: str, task_id: UUID
    ) -> None:
        """Send notification when a task is completed."""
        subject = f"Task Completed: {task_title}"
        body = f"""
        Hello,

        Congratulations! You have completed a task:

        Task: {task_title}
        Task ID: {task_id}

        Keep up the great work!

        Best regards,
        Morty Task Management System
        """

        await self._send_email(user_email, subject, body)

    async def send_user_workload_alert(self, user_email: str, pending_task_count: int) -> None:
        """Send alert when user workload is high."""
        subject = "High Workload Alert"
        body = f"""
        Hello,

        You currently have {pending_task_count} pending tasks assigned to you.

        This is a reminder to help you manage your workload effectively.
        Consider prioritizing your tasks or reaching out for assistance if needed.

        Best regards,
        Morty Task Management System
        """

        await self._send_email(user_email, subject, body)

    async def _send_email(self, to_email: str, subject: str, body: str) -> None:
        """Send an email using the configured email client."""
        if not self._email_client:
            # Log email if no client configured (for testing/development)
            logger.info(f"Would send email to {to_email}: {subject}")
            logger.debug(f"Email body: {body}")
            return

        try:
            await self._email_client.send_email(
                to_email=to_email,
                from_email=self._from_email,
                subject=subject,
                body=body,
            )
            logger.info(f"Sent email to {to_email}: {subject}")
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            raise


class RedisCache:
    """Redis implementation of the cache port."""

    def __init__(self, redis_client=None):
        self._redis = redis_client

    async def get(self, key: str) -> str | None:
        """Get a value from cache."""
        if not self._redis:
            return None

        try:
            value = await self._redis.get(key)
            return value.decode("utf-8") if value else None
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    async def set(self, key: str, value: str, ttl_seconds: int | None = None) -> None:
        """Set a value in cache with optional TTL."""
        if not self._redis:
            return

        try:
            if ttl_seconds:
                await self._redis.setex(key, ttl_seconds, value)
            else:
                await self._redis.set(key, value)
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")

    async def delete(self, key: str) -> None:
        """Delete a value from cache."""
        if not self._redis:
            return

        try:
            await self._redis.delete(key)
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")

    async def invalidate_pattern(self, pattern: str) -> None:
        """Invalidate all cache keys matching a pattern."""
        if not self._redis:
            return

        try:
            keys = await self._redis.keys(pattern)
            if keys:
                await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"Cache invalidate pattern error for pattern {pattern}: {e}")
