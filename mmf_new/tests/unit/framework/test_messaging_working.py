"""
Working messaging tests with real framework implementations.

Tests messaging infrastructure components using actual implementations instead of mocks.
"""

from mmf_new.framework.messaging import (
    Message,
    MessageHeaders,
    MessagePriority,
    MessageStatus,
)
from mmf_new.framework.messaging.bootstrap import JSONMessageSerializer


class TestMessage:
    """Test Message core functionality."""

    def test_message_creation(self):
        """Test basic message creation."""
        body = {"user_id": 123, "action": "created"}
        message = Message(body=body)

        assert message.body == body
        assert message.status == MessageStatus.PENDING
        assert message.headers is not None
        assert message.id is not None
        assert len(message.id) > 0

    def test_message_with_headers(self):
        """Test message creation with custom headers."""
        body = {"test": "data"}
        headers = MessageHeaders(data={"custom": "value"})

        message = Message(
            body=body,
            headers=headers,
            correlation_id="test-correlation",
            priority=MessagePriority.HIGH,
        )

        assert message.body == body
        assert message.correlation_id == "test-correlation"
        assert message.priority == MessagePriority.HIGH
        assert message.headers.get("custom") == "value"

    def test_message_status_operations(self):
        """Test message status transitions."""
        message = Message(body={"test": "data"})

        # Initial state
        assert message.status == MessageStatus.PENDING

        # Mark processing
        message.status = MessageStatus.PROCESSING
        assert message.status == MessageStatus.PROCESSING

        # Mark completed
        message.status = MessageStatus.PROCESSED
        assert message.status == MessageStatus.PROCESSED

    def test_message_retry_operations(self):
        """Test message retry functionality."""
        message = Message(body={"test": "data"}, max_retries=3)

        # Initial retry state
        assert message.can_retry() is True
        assert message.retry_count == 0

        # Mark failed (increments retry)
        message.retry_count += 1
        message.status = MessageStatus.FAILED

        assert message.retry_count == 1
        assert message.status == MessageStatus.FAILED
        assert message.can_retry() is True

    def test_message_serialization(self):
        """Test message serialization using serializer."""
        body = {"user_id": 123, "action": "created"}
        message = Message(body=body)

        serializer = JSONMessageSerializer()
        serialized = serializer.serialize(message.body)

        assert serialized is not None
        deserialized = serializer.deserialize(serialized)
        assert deserialized == body


class TestMessageHeaders:
    """Test MessageHeaders functionality."""

    def test_headers_creation(self):
        """Test basic headers creation."""
        headers = MessageHeaders()
        assert headers.data == {}

    def test_headers_manipulation(self):
        """Test headers manipulation."""
        headers = MessageHeaders()
        headers.set("key", "value")
        assert headers.get("key") == "value"

        headers.remove("key")
        assert headers.get("key") is None


class TestMessagePriorities:
    """Test message priority handling."""

    def test_priority_levels(self):
        """Test different priority levels."""
        # Test all priority levels
        priorities = [
            (MessagePriority.LOW, 1),
            (MessagePriority.NORMAL, 5),
            (MessagePriority.HIGH, 10),
            (MessagePriority.CRITICAL, 15),
        ]

        for priority, expected_value in priorities:
            message = Message(body={"test": "data"}, priority=priority)

            assert message.priority == priority
            assert message.priority.value == expected_value

    def test_priority_comparison(self):
        """Test priority comparison logic."""
        low_msg = Message(body={"test": "low"}, priority=MessagePriority.LOW)
        high_msg = Message(body={"test": "high"}, priority=MessagePriority.HIGH)

        # Verify priority values for sorting
        assert low_msg.priority.value < high_msg.priority.value


class TestMessageStatuses:
    """Test message status handling."""

    def test_all_status_transitions(self):
        """Test all possible status transitions."""
        message = Message(body={"test": "data"})

        # PENDING -> PROCESSING
        assert message.status == MessageStatus.PENDING
        message.status = MessageStatus.PROCESSING
        assert message.status == MessageStatus.PROCESSING

        # PROCESSING -> PROCESSED
        message.status = MessageStatus.PROCESSED
        assert message.status == MessageStatus.PROCESSED

        # Test failure path
        message2 = Message(body={"test": "data2"})
        message2.status = MessageStatus.PROCESSING
        message2.status = MessageStatus.FAILED
        assert message2.status == MessageStatus.FAILED

        # Test dead letter
        message3 = Message(body={"test": "data3"})
        message3.status = MessageStatus.DEAD_LETTER
        assert message3.status == MessageStatus.DEAD_LETTER

    def test_retry_status_handling(self):
        """Test retry status with failures."""
        message = Message(body={"test": "data"}, max_retries=2)

        # First failure
        message.retry_count += 1
        message.status = MessageStatus.RETRY
        assert message.status == MessageStatus.RETRY
        assert message.can_retry() is True

        # Second failure
        message.retry_count += 1
        assert message.can_retry() is False
