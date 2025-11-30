from __future__ import annotations

import logging
import time

from mmf_new.framework.messaging.domain.models import DLQConfig, Message, MessageStatus
from mmf_new.framework.messaging.domain.ports import IDLQManager, IMessageBackend


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
