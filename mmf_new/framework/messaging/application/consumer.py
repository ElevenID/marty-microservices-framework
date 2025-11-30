from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import Any

from mmf_new.framework.messaging.domain.models import (
    ConsumerConfig,
    Message,
    MessageStatus,
)
from mmf_new.framework.messaging.domain.ports import (
    IMessageBackend,
    IMessageConsumer,
    IMessageSerializer,
)
from mmf_new.framework.messaging.infrastructure.adapters.serializer import (
    JSONMessageSerializer,
)


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
