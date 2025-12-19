"""Unit tests for DLQ (Dead Letter Queue) Manager."""

import time
from unittest.mock import AsyncMock, MagicMock

import pytest

from mmf.core.messaging import DLQConfig, Message, MessageHeaders, MessageStatus
from mmf.framework.messaging.application.dlq import DLQManager


@pytest.fixture
def mock_backend():
    """Create a mock message backend."""
    return AsyncMock()


@pytest.fixture
def dlq_config():
    """Create a DLQ configuration."""
    return DLQConfig(
        enabled=True,
        queue_name="test-dlq",
        max_retries=3,
        retry_delay=1.0,
    )


@pytest.fixture
def dlq_manager(dlq_config, mock_backend):
    """Create a DLQ manager instance."""
    return DLQManager(config=dlq_config, backend=mock_backend)


@pytest.fixture
def sample_message():
    """Create a sample message for testing."""
    return Message(
        id="test-message-id",
        body={"key": "value"},
        headers=MessageHeaders(),
        status=MessageStatus.PENDING,
        retry_count=0,
    )


@pytest.mark.unit
class TestDLQManager:
    """Tests for DLQManager class."""

    @pytest.mark.asyncio
    async def test_send_to_dlq_success(self, dlq_manager, sample_message):
        """Test sending a message to DLQ successfully."""
        result = await dlq_manager.send_to_dlq(sample_message, "Test failure reason")

        assert result is True
        assert sample_message.status == MessageStatus.DEAD_LETTER
        assert sample_message.headers.get("dlq_reason") == "Test failure reason"
        assert sample_message.headers.get("dlq_timestamp") is not None
        assert sample_message.id in dlq_manager.dlq_messages

    @pytest.mark.asyncio
    async def test_send_to_dlq_sets_timestamp(self, dlq_manager, sample_message):
        """Test that sending to DLQ sets a timestamp header."""
        before = time.time()
        await dlq_manager.send_to_dlq(sample_message, "reason")
        after = time.time()

        timestamp = sample_message.headers.get("dlq_timestamp")
        assert before <= timestamp <= after

    @pytest.mark.asyncio
    async def test_get_dlq_messages_empty(self, dlq_manager):
        """Test getting messages when DLQ is empty."""
        messages = await dlq_manager.get_dlq_messages()
        assert messages == []

    @pytest.mark.asyncio
    async def test_get_dlq_messages_with_limit(self, dlq_manager):
        """Test getting messages with a limit."""
        # Add multiple messages to DLQ
        for i in range(5):
            msg = Message(id=f"msg-{i}", body={"index": i})
            await dlq_manager.send_to_dlq(msg, f"reason-{i}")

        messages = await dlq_manager.get_dlq_messages(limit=3)
        assert len(messages) == 3

    @pytest.mark.asyncio
    async def test_requeue_from_dlq_success(self, dlq_manager, sample_message):
        """Test requeuing a message from DLQ."""
        await dlq_manager.send_to_dlq(sample_message, "reason")

        result = await dlq_manager.requeue_from_dlq(sample_message.id)

        assert result is True
        assert sample_message.status == MessageStatus.PENDING
        assert sample_message.id not in dlq_manager.dlq_messages

    @pytest.mark.asyncio
    async def test_requeue_from_dlq_not_found(self, dlq_manager):
        """Test requeuing a non-existent message from DLQ."""
        result = await dlq_manager.requeue_from_dlq("non-existent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_process_dlq_retries_expired_messages(self, dlq_manager, sample_message):
        """Test that process_dlq retries messages after delay expires."""
        # Send message to DLQ with timestamp in the past
        await dlq_manager.send_to_dlq(sample_message, "reason")
        sample_message.headers.set("dlq_timestamp", time.time() - 10)  # 10 seconds ago

        await dlq_manager.process_dlq()

        # Message should be retried and removed from DLQ
        assert sample_message.id not in dlq_manager.dlq_messages
        assert sample_message.status == MessageStatus.RETRY
        assert sample_message.retry_count == 1

    @pytest.mark.asyncio
    async def test_process_dlq_respects_max_retries(self, dlq_manager, sample_message):
        """Test that process_dlq respects max retry count."""
        sample_message.retry_count = 3  # Already at max
        await dlq_manager.send_to_dlq(sample_message, "reason")
        sample_message.headers.set("dlq_timestamp", time.time() - 10)

        await dlq_manager.process_dlq()

        # Message should remain in DLQ (not retried)
        assert sample_message.id in dlq_manager.dlq_messages

    @pytest.mark.asyncio
    async def test_process_dlq_respects_retry_delay(self, dlq_manager, sample_message):
        """Test that process_dlq respects retry delay."""
        await dlq_manager.send_to_dlq(sample_message, "reason")
        # Timestamp is current, so delay hasn't expired

        await dlq_manager.process_dlq()

        # Message should remain in DLQ (delay not expired)
        assert sample_message.id in dlq_manager.dlq_messages
        assert sample_message.status == MessageStatus.DEAD_LETTER
