"""
Working messaging tests with real framework implementations.

Tests messaging infrastructure components using actual implementations instead of mocks.
"""

from marty_msf.framework.messaging import (
    Message,
    MessageHeaders,
    MessagePriority,
    MessageStatus,
)


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
        headers = MessageHeaders()
        headers.correlation_id = "test-correlation"
        headers.priority = MessagePriority.HIGH

        message = Message(body=body, headers=headers)

        assert message.body == body
        assert message.correlation_id == "test-correlation"
        assert message.priority == MessagePriority.HIGH

    def test_message_status_operations(self):
        """Test message status transitions."""
        message = Message(body={"test": "data"})

        # Initial state
        assert message.status == MessageStatus.PENDING

        # Mark processing
        message.mark_processing()
        assert message.status == MessageStatus.PROCESSING

        # Mark completed
        message.mark_completed()
        assert message.status == MessageStatus.COMPLETED

    def test_message_retry_operations(self):
        """Test message retry functionality."""
        message = Message(body={"test": "data"})

        # Initial retry state
        assert message.should_retry() is True
        assert message.headers.retry_count == 0

        # Mark failed (increments retry)
        message.mark_failed()
        assert message.headers.retry_count == 1
        assert message.status == MessageStatus.FAILED

    def test_message_serialization(self):
        """Test message to/from dict conversion."""
        body = {"user_id": 123, "action": "created"}
        message = Message(body=body)

        # Convert to dict
        message_dict = message.to_dict()
        assert message_dict["body"] == body
        assert message_dict["status"] == MessageStatus.PENDING.value
        assert "headers" in message_dict

        # Convert back from dict
        restored_message = Message.from_dict(message_dict)
        assert restored_message.body == body
        assert restored_message.status == MessageStatus.PENDING


class TestMessageHeaders:
    """Test MessageHeaders functionality."""

    def test_headers_creation(self):
        """Test basic headers creation."""
        headers = MessageHeaders()

        assert headers.message_id is not None
        assert headers.priority == MessagePriority.NORMAL
        assert headers.retry_count == 0
        assert headers.max_retries == 3

    def test_headers_serialization(self):
        """Test headers to/from dict conversion."""
        headers = MessageHeaders()
        headers.correlation_id = "test-correlation"
        headers.priority = MessagePriority.HIGH

        # Convert to dict
        headers_dict = headers.to_dict()
        assert headers_dict["correlation_id"] == "test-correlation"
        assert headers_dict["priority"] == MessagePriority.HIGH.value

        # Convert back from dict
        restored_headers = MessageHeaders.from_dict(headers_dict)
        assert restored_headers.correlation_id == "test-correlation"
        assert restored_headers.priority == MessagePriority.HIGH

    def test_headers_retry_logic(self):
        """Test headers retry functionality."""
        headers = MessageHeaders()
        headers.max_retries = 2

        # Initial state
        assert headers.should_retry() is True
        assert headers.retry_count == 0

        # First retry
        headers.increment_retry()
        assert headers.retry_count == 1
        assert headers.should_retry() is True

        # Second retry
        headers.increment_retry()
        assert headers.retry_count == 2
        assert headers.should_retry() is False  # Max retries reached


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
            headers = MessageHeaders()
            headers.priority = priority
            message = Message(body={"test": "data"}, headers=headers)

            assert message.priority == priority
            assert message.priority.value == expected_value

    def test_priority_comparison(self):
        """Test priority comparison logic."""
        low_msg = Message(body={"test": "low"})
        low_msg.headers.priority = MessagePriority.LOW

        high_msg = Message(body={"test": "high"})
        high_msg.headers.priority = MessagePriority.HIGH

        # Verify priority values for sorting
        assert low_msg.priority.value < high_msg.priority.value


class TestMessageStatuses:
    """Test message status handling."""

    def test_all_status_transitions(self):
        """Test all possible status transitions."""
        message = Message(body={"test": "data"})

        # PENDING -> PROCESSING
        assert message.status == MessageStatus.PENDING
        message.mark_processing()
        assert message.status == MessageStatus.PROCESSING

        # PROCESSING -> COMPLETED
        message.mark_completed()
        assert message.status == MessageStatus.COMPLETED

        # Test failure path
        message2 = Message(body={"test": "data2"})
        message2.mark_processing()
        message2.mark_failed()
        assert message2.status == MessageStatus.FAILED

        # Test dead letter
        message3 = Message(body={"test": "data3"})
        message3.mark_dead_letter()
        assert message3.status == MessageStatus.DEAD_LETTER

    def test_retry_status_handling(self):
        """Test retry status with failures."""
        message = Message(body={"test": "data"})
        message.headers.max_retries = 2

        # First failure
        message.mark_failed()
        assert message.status == MessageStatus.FAILED
        assert message.headers.retry_count == 1
        assert message.should_retry() is True

        # Second failure
        message.mark_failed()
        assert message.headers.retry_count == 2
        assert message.should_retry() is False


class TestMessagingIntegration:
    """Test integration scenarios for messaging components."""

    def test_message_workflow_simulation(self):
        """Test simulated message processing workflow."""
        # Create order message
        order_data = {
            "order_id": "order-123",
            "customer_id": "customer-456",
            "items": [{"product_id": "p1", "quantity": 2}, {"product_id": "p2", "quantity": 1}],
            "total_amount": 89.99,
        }

        headers = MessageHeaders()
        headers.correlation_id = "workflow-123"
        headers.priority = MessagePriority.HIGH
        headers.routing_key = "order.created"

        message = Message(body=order_data, headers=headers)

        # Simulate processing stages
        assert message.status == MessageStatus.PENDING

        # Start processing
        message.mark_processing()
        assert message.status == MessageStatus.PROCESSING

        # Complete processing
        message.mark_completed()
        assert message.status == MessageStatus.COMPLETED

        # Verify message content preserved
        assert message.body["order_id"] == "order-123"
        assert message.correlation_id == "workflow-123"
        assert message.headers.routing_key == "order.created"

    def test_message_batch_processing(self):
        """Test batch message processing scenario."""
        # Create batch of messages
        messages = []
        for i in range(5):
            headers = MessageHeaders()
            headers.correlation_id = f"batch-{i}"
            headers.priority = MessagePriority.NORMAL

            message = Message(
                body={"batch_id": "batch-123", "item_id": f"item-{i}", "data": f"data-{i}"},
                headers=headers,
            )
            messages.append(message)

        # Process batch
        completed_messages = []
        failed_messages = []

        for message in messages:
            message.mark_processing()

            # Simulate some failures (items 1 and 3)
            if message.body["item_id"] in ["item-1", "item-3"]:
                message.mark_failed()
                failed_messages.append(message)
            else:
                message.mark_completed()
                completed_messages.append(message)

        # Verify batch results
        assert len(completed_messages) == 3
        assert len(failed_messages) == 2

        # All messages should have correct correlation IDs
        for _i, msg in enumerate(completed_messages):
            assert msg.headers.correlation_id.startswith("batch-")

        # Failed messages should be available for retry
        for msg in failed_messages:
            assert msg.should_retry() is True
            assert msg.status == MessageStatus.FAILED

    def test_complex_message_routing_simulation(self):
        """Test complex message routing scenario."""
        # Create different types of messages
        messages = [
            {
                "body": {"event": "user.created", "user_id": 123},
                "routing_key": "user.events",
                "priority": MessagePriority.NORMAL,
            },
            {
                "body": {"event": "order.placed", "order_id": "order-456"},
                "routing_key": "order.events",
                "priority": MessagePriority.HIGH,
            },
            {
                "body": {"event": "payment.failed", "payment_id": "pay-789"},
                "routing_key": "payment.events",
                "priority": MessagePriority.CRITICAL,
            },
        ]

        # Create and route messages
        routed_messages = {"user.events": [], "order.events": [], "payment.events": []}

        for msg_data in messages:
            headers = MessageHeaders()
            headers.routing_key = msg_data["routing_key"]
            headers.priority = msg_data["priority"]

            message = Message(body=msg_data["body"], headers=headers)

            # Simulate routing based on routing key
            routing_key = message.headers.routing_key
            if routing_key in routed_messages:
                routed_messages[routing_key].append(message)

        # Verify routing
        assert len(routed_messages["user.events"]) == 1
        assert len(routed_messages["order.events"]) == 1
        assert len(routed_messages["payment.events"]) == 1

        # Verify message content
        user_msg = routed_messages["user.events"][0]
        assert user_msg.body["event"] == "user.created"
        assert user_msg.priority == MessagePriority.NORMAL

        payment_msg = routed_messages["payment.events"][0]
        assert payment_msg.body["event"] == "payment.failed"
        assert payment_msg.priority == MessagePriority.CRITICAL
