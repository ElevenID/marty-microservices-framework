"""
Unit tests for framework message bus.

Tests the MessageBus class and message handling without external dependencies.
"""

import asyncio
from unittest.mock import patch

import pytest

from marty_msf.framework.messaging import Message, MessageBus, MessageHandler


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessage:
    """Test suite for Message class."""

    def test_message_creation(self):
        """Test message creation with required fields."""
        message = Message(id="test-123", type="user.created", data={"user_id": 123, "name": "John"})

        assert message.id == "test-123"
        assert message.type == "user.created"
        assert message.data == {"user_id": 123, "name": "John"}
        assert message.timestamp is not None
        assert message.retry_count == 0

    def test_message_creation_with_optional_fields(self):
        """Test message creation with optional fields."""
        message = Message(
            id="test-456",
            type="order.shipped",
            data={"order_id": 456},
            correlation_id="corr-789",
            source="order-service",
            destination="notification-service",
        )

        assert message.correlation_id == "corr-789"
        assert message.source == "order-service"
        assert message.destination == "notification-service"

    def test_message_to_dict(self):
        """Test message serialization to dictionary."""
        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        message_dict = message.to_dict()

        assert message_dict["id"] == "test-123"
        assert message_dict["type"] == "user.created"
        assert message_dict["data"] == {"user_id": 123}
        assert "timestamp" in message_dict
        assert message_dict["retry_count"] == 0

    def test_message_from_dict(self):
        """Test message creation from dictionary."""
        message_dict = {
            "id": "test-456",
            "type": "order.created",
            "data": {"order_id": 456},
            "timestamp": "2024-01-01T12:00:00Z",
            "retry_count": 1,
        }

        message = Message.from_dict(message_dict)

        assert message.id == "test-456"
        assert message.type == "order.created"
        assert message.data == {"order_id": 456}
        assert message.retry_count == 1

    def test_message_increment_retry(self):
        """Test message retry count increment."""
        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        assert message.retry_count == 0

        message.increment_retry()
        assert message.retry_count == 1

        message.increment_retry()
        assert message.retry_count == 2

    def test_message_is_expired(self):
        """Test message expiration check."""
        # This would test TTL functionality if implemented
        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        # Assuming messages don't expire by default
        assert not message.is_expired()

    def test_message_equality(self):
        """Test message equality comparison."""
        message1 = Message(id="test-123", type="user.created", data={"user_id": 123})

        message2 = Message(id="test-123", type="user.created", data={"user_id": 123})

        message3 = Message(id="test-456", type="user.created", data={"user_id": 123})

        assert message1 == message2
        assert message1 != message3


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessageHandler:
    """Test suite for MessageHandler class."""

    async def test_message_handler_creation(self):
        """Test message handler creation."""

        async def handler_func(message: Message) -> bool:
            return True

        handler = MessageHandler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        assert handler.name == "test-handler"
        assert handler.message_type == "user.created"
        assert handler.handler_func == handler_func
        assert handler.max_retries == 3
        assert handler.retry_delay == 1.0

    async def test_message_handler_with_custom_config(self):
        """Test message handler with custom configuration."""

        async def handler_func(message: Message) -> bool:
            return True

        handler = MessageHandler(
            name="custom-handler",
            message_type="order.created",
            handler_func=handler_func,
            max_retries=5,
            retry_delay=2.0,
            timeout=30.0,
        )

        assert handler.max_retries == 5
        assert handler.retry_delay == 2.0
        assert handler.timeout == 30.0

    async def test_message_handler_execution_success(self):
        """Test successful message handler execution."""
        executed_messages = []

        async def handler_func(message: Message) -> bool:
            executed_messages.append(message)
            return True

        handler = MessageHandler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        result = await handler.execute(message)

        assert result is True
        assert len(executed_messages) == 1
        assert executed_messages[0] == message

    async def test_message_handler_execution_failure(self):
        """Test message handler execution with failure."""

        async def handler_func(message: Message) -> bool:
            raise ValueError("Handler failed")

        handler = MessageHandler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        result = await handler.execute(message)

        assert result is False

    async def test_message_handler_matches_type(self):
        """Test message handler type matching."""

        async def handler_func(message: Message) -> bool:
            return True

        handler = MessageHandler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        matching_message = Message(id="test-123", type="user.created", data={"user_id": 123})

        non_matching_message = Message(id="test-456", type="order.created", data={"order_id": 456})

        assert handler.matches(matching_message) is True
        assert handler.matches(non_matching_message) is False


@pytest.mark.unit
@pytest.mark.asyncio
class TestMessageBus:
    """Test suite for MessageBus class."""

    def test_message_bus_creation(self):
        """Test message bus creation."""
        bus = MessageBus(service_name="test-service")

        assert bus.service_name == "test-service"
        assert len(bus.handlers) == 0
        assert bus.is_running is False

    def test_message_bus_register_handler(self):
        """Test registering message handlers."""
        bus = MessageBus(service_name="test-service")

        async def handler_func(message: Message) -> bool:
            return True

        handler = bus.register_handler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        assert len(bus.handlers) == 1
        assert handler.name == "test-handler"
        assert handler.message_type == "user.created"

    def test_message_bus_register_duplicate_handler(self):
        """Test registering duplicate handler names."""
        bus = MessageBus(service_name="test-service")

        async def handler_func(message: Message) -> bool:
            return True

        bus.register_handler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        with pytest.raises(ValueError, match="Handler 'test-handler' already registered"):
            bus.register_handler(
                name="test-handler", message_type="order.created", handler_func=handler_func
            )

    def test_message_bus_unregister_handler(self):
        """Test unregistering message handlers."""
        bus = MessageBus(service_name="test-service")

        async def handler_func(message: Message) -> bool:
            return True

        bus.register_handler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        assert len(bus.handlers) == 1

        bus.unregister_handler("test-handler")
        assert len(bus.handlers) == 0

    def test_message_bus_unregister_nonexistent_handler(self):
        """Test unregistering non-existent handler."""
        bus = MessageBus(service_name="test-service")

        with pytest.raises(ValueError, match="Handler 'nonexistent' not found"):
            bus.unregister_handler("nonexistent")

    async def test_message_bus_publish_message(self):
        """Test publishing messages to the bus."""
        bus = MessageBus(service_name="test-service")
        executed_messages = []

        async def handler_func(message: Message) -> bool:
            executed_messages.append(message)
            return True

        bus.register_handler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        await bus.publish(message)

        # Give some time for async processing
        await asyncio.sleep(0.1)

        assert len(executed_messages) == 1
        assert executed_messages[0] == message

    async def test_message_bus_publish_no_matching_handlers(self):
        """Test publishing message with no matching handlers."""
        bus = MessageBus(service_name="test-service")

        async def handler_func(message: Message) -> bool:
            return True

        bus.register_handler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        message = Message(
            id="test-123",
            type="order.created",  # No handler for this type
            data={"order_id": 123},
        )

        # Should not raise an exception
        await bus.publish(message)

    async def test_message_bus_publish_multiple_handlers(self):
        """Test publishing message to multiple handlers."""
        bus = MessageBus(service_name="test-service")
        executed_by_handler1 = []
        executed_by_handler2 = []

        async def handler1_func(message: Message) -> bool:
            executed_by_handler1.append(message)
            return True

        async def handler2_func(message: Message) -> bool:
            executed_by_handler2.append(message)
            return True

        bus.register_handler(
            name="handler-1", message_type="user.created", handler_func=handler1_func
        )

        bus.register_handler(
            name="handler-2", message_type="user.created", handler_func=handler2_func
        )

        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        await bus.publish(message)

        # Give some time for async processing
        await asyncio.sleep(0.1)

        assert len(executed_by_handler1) == 1
        assert len(executed_by_handler2) == 1
        assert executed_by_handler1[0] == message
        assert executed_by_handler2[0] == message

    async def test_message_bus_start_stop(self):
        """Test starting and stopping the message bus."""
        bus = MessageBus(service_name="test-service")

        assert bus.is_running is False

        await bus.start()
        assert bus.is_running is True

        await bus.stop()
        assert bus.is_running is False

    async def test_message_bus_middleware(self):
        """Test message bus middleware functionality."""
        bus = MessageBus(service_name="test-service")
        middleware_calls = []

        async def test_middleware(message: Message, next_handler):
            middleware_calls.append(f"before:{message.id}")
            result = await next_handler(message)
            middleware_calls.append(f"after:{message.id}")
            return result

        async def handler_func(message: Message) -> bool:
            middleware_calls.append(f"handler:{message.id}")
            return True

        bus.add_middleware(test_middleware)
        bus.register_handler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        await bus.publish(message)
        await asyncio.sleep(0.1)

        assert "before:test-123" in middleware_calls
        assert "handler:test-123" in middleware_calls
        assert "after:test-123" in middleware_calls

    async def test_message_bus_error_handling(self):
        """Test message bus error handling and retry logic."""
        bus = MessageBus(service_name="test-service")
        call_count = 0

        async def failing_handler(message: Message) -> bool:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("Temporary failure")
            return True

        bus.register_handler(
            name="failing-handler",
            message_type="user.created",
            handler_func=failing_handler,
            max_retries=3,
        )

        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        await bus.publish(message)
        await asyncio.sleep(0.1)

        # Should have been called 3 times (initial + 2 retries)
        assert call_count == 3

    @patch("src.framework.messaging.logger")
    async def test_message_bus_logging(self, mock_logger):
        """Test message bus logging functionality."""
        bus = MessageBus(service_name="test-service")

        async def handler_func(message: Message) -> bool:
            return True

        bus.register_handler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        await bus.publish(message)
        await asyncio.sleep(0.1)

        # Verify logging calls were made
        mock_logger.info.assert_called()
        mock_logger.debug.assert_called()

    async def test_message_bus_metrics_collection(self):
        """Test message bus metrics collection."""
        bus = MessageBus(service_name="test-service")

        async def handler_func(message: Message) -> bool:
            return True

        bus.register_handler(
            name="test-handler", message_type="user.created", handler_func=handler_func
        )

        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        await bus.publish(message)
        await asyncio.sleep(0.1)

        metrics = bus.get_metrics()

        assert "messages_published" in metrics
        assert "messages_processed" in metrics
        assert "handler_execution_time" in metrics
        assert metrics["messages_published"] >= 1

    async def test_message_bus_dead_letter_queue(self):
        """Test message bus dead letter queue functionality."""
        bus = MessageBus(service_name="test-service")

        async def always_failing_handler(message: Message) -> bool:
            raise ValueError("Always fails")

        bus.register_handler(
            name="failing-handler",
            message_type="user.created",
            handler_func=always_failing_handler,
            max_retries=2,
        )

        message = Message(id="test-123", type="user.created", data={"user_id": 123})

        await bus.publish(message)
        await asyncio.sleep(0.1)

        # Message should be in dead letter queue after max retries
        dead_letters = bus.get_dead_letter_messages()
        assert len(dead_letters) == 1
        assert dead_letters[0].id == "test-123"
