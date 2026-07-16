from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from mmf.core.messaging import IMessageBackend, IMessageQueue, Message, QueueConfig
from mmf.framework.messaging.application.dlq import DLQManager
from mmf.framework.messaging.application.manager import MessagingManager


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
