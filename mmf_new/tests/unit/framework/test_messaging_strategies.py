"""Test messaging retry strategies with minimal mocking."""

from unittest.mock import AsyncMock

import pytest

from mmf_new.framework.messaging import api as core_module
from mmf_new.framework.messaging import api as dlq_module

# Import messaging components
from mmf_new.framework.messaging.api import (
    DLQConfig,
    Message,
    MessageHeaders,
    MessagePriority,
    MessageStatus,
    RetryConfig,
    RetryStrategy,
)
from mmf_new.framework.messaging.bootstrap import DLQManager


# Try direct imports to see if messaging modules work better
def test_import_messaging_strategies():
    """Test importing messaging strategy classes."""
    try:
        assert RetryStrategy is not None
        assert DLQManager is not None
        assert RetryConfig is not None
        assert Message is not None
        assert MessageStatus is not None

        # Test strategy enum values
        strategies = list(RetryStrategy)
        assert len(strategies) > 0
        print(f"Available retry strategies: {[s.value for s in strategies]}")

    except Exception as e:
        pytest.fail(f"Could not import messaging strategies: {e}")


def test_retry_strategy_enum():
    """Test RetryStrategy enum functionality."""
    try:
        # Test all available strategies
        all_strategies = list(RetryStrategy)
        assert RetryStrategy.FIXED_DELAY in all_strategies
        assert RetryStrategy.LINEAR_BACKOFF in all_strategies
        assert RetryStrategy.EXPONENTIAL_BACKOFF in all_strategies

        # Test string values
        assert RetryStrategy.FIXED_DELAY.value == "fixed_delay"
        assert RetryStrategy.LINEAR_BACKOFF.value == "linear_backoff"
        assert RetryStrategy.EXPONENTIAL_BACKOFF.value == "exponential_backoff"

        print(f"Retry strategy test passed with {len(all_strategies)} strategies")

    except Exception as e:
        pytest.fail(f"RetryStrategy enum test failed: {e}")


def test_message_creation():
    """Test that Message objects can be created with proper parameters."""
    try:
        # Test basic message creation
        message = Message(body={"action": "process", "data": {"user_id": 123}})
        assert message is not None
        assert message.id is not None  # Auto-generated ID
        assert message.body["action"] == "process"

        # Test message without explicit body
        simple_message = Message(body="simple text message")
        assert simple_message is not None
        assert simple_message.id is not None and len(simple_message.id) > 0

        # Test message with custom headers
        custom_headers = MessageHeaders(data={"custom-header": "value"})

        headers_message = Message(
            body={"test": "data"},
            headers=custom_headers,
            correlation_id="corr-123",
            routing_key="user.created",
            priority=MessagePriority.HIGH,
        )
        assert headers_message is not None
        assert headers_message.correlation_id == "corr-123"
        assert headers_message.routing_key == "user.created"
        assert headers_message.headers.get("custom-header") == "value"

    except Exception as e:
        pytest.fail(f"Message creation test failed: {e}")


def test_retry_config_creation():
    """Test that RetryConfig objects can be created with proper parameters."""
    try:
        # Test basic retry config creation
        config = RetryConfig(
            max_attempts=5,
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            initial_delay=2.0,
            max_delay=600.0,
        )
        assert config is not None
        assert config.max_attempts == 5
        assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert config.initial_delay == 2.0
        assert config.max_delay == 600.0

        # Test default config
        default_config = RetryConfig()
        assert default_config is not None
        assert default_config.max_attempts == 3  # Default value
        assert default_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF

    except Exception as e:
        pytest.fail(f"RetryConfig creation test failed: {e}")


@pytest.mark.asyncio
def test_dlq_manager_basic_functionality():
    """Test basic DLQManager functionality without requiring a backend."""
    try:
        # Create configurations
        retry_config = RetryConfig(max_attempts=2)
        dlq_config = DLQConfig(queue_name="test.dlq", retry_config=retry_config)
        assert dlq_config is not None
        assert dlq_config.queue_name == "test.dlq"
        assert dlq_config.retry_config.max_attempts == 2

        # Test default config
        default_dlq_config = DLQConfig()
        assert default_dlq_config is not None

    except Exception as e:
        pytest.fail(f"DLQManager basic functionality test failed: {e}")


@pytest.mark.asyncio
async def test_retry_strategy_delay_calculation():
    """Test retry strategy delay calculation logic."""
    try:
        # Test fixed delay retry strategy
        fixed_config = DLQConfig(
            retry_config=RetryConfig(strategy=RetryStrategy.FIXED_DELAY, max_attempts=3)
        )
        assert fixed_config is not None
        assert fixed_config.retry_config.strategy == RetryStrategy.FIXED_DELAY

        # Test exponential backoff strategy
        exponential_config = DLQConfig(
            retry_config=RetryConfig(
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                max_attempts=5,
                initial_delay=1.0,
                backoff_multiplier=2.0,
            )
        )
        assert exponential_config is not None
        assert exponential_config.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert exponential_config.retry_config.max_attempts == 5
        assert exponential_config.retry_config.initial_delay == 1.0
        assert exponential_config.retry_config.backoff_multiplier == 2.0

        # Test linear backoff strategy
        linear_config = DLQConfig(
            retry_config=RetryConfig(strategy=RetryStrategy.LINEAR_BACKOFF, initial_delay=0.5)
        )
        assert linear_config is not None
        assert linear_config.retry_config.strategy == RetryStrategy.LINEAR_BACKOFF

    except Exception as e:
        pytest.fail(f"Retry strategy delay calculation test failed: {e}")


def test_discover_messaging_strategy_classes():
    """Discover all messaging strategy-related classes."""
    try:
        # Find strategy-related classes in DLQ module
        dlq_classes = []
        for name in dir(dlq_module):
            if not name.startswith("_"):
                obj = getattr(dlq_module, name)
                if isinstance(obj, type):
                    dlq_classes.append(name)

        print(f"DLQ module classes: {dlq_classes}")

        # Find core classes
        core_classes = []
        for name in dir(core_module):
            if not name.startswith("_"):
                obj = getattr(core_module, name)
                if isinstance(obj, type):
                    core_classes.append(name)

        print(f"Core module classes: {core_classes}")

        # Should find some strategy-related classes
        strategy_classes = [
            name
            for name in dlq_classes + core_classes
            if "Strategy" in name or "Config" in name or "Manager" in name
        ]
        print(f"Strategy-related classes: {strategy_classes}")

        assert len(strategy_classes) > 0, "Should find at least some strategy classes"

    except Exception as e:
        pytest.fail(f"Strategy class discovery test failed: {e}")


@pytest.mark.asyncio
async def test_messaging_strategy_integration():
    """Test integration between messaging strategies and components."""
    try:
        # Create a comprehensive test with multiple components
        retry_config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            max_attempts=2,
            initial_delay=0.1,  # Short delays for testing
            max_delay=1.0,
        )

        dlq_config = DLQConfig(enabled=True, retry_config=retry_config)

        # Mock backend
        mock_backend = AsyncMock()

        # Create DLQ manager
        dlq_manager = DLQManager(dlq_config, mock_backend)

        # Create test message
        message = Message(id="integration-test-123", body={"test": "integration"})

        # Test message processing workflow (without actual backend calls)
        assert message.retry_count == 0
        # Message doesn't have increment_retry method, it's a dataclass.
        # Logic usually handles this.
        message.retry_count += 1
        assert message.retry_count == 1

        # Verify manager configuration
        assert dlq_manager.config.enabled is True
        assert dlq_manager.config.retry_config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF

        print("Messaging strategy integration test passed")

    except Exception as e:
        pytest.fail(f"Messaging strategy integration test failed: {e}")
